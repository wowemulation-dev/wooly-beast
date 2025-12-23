"""
Concrete pipeline stages for MySQL to PostgreSQL conversion.

Each stage implements a specific transformation step:
- PreprocessingStage: Remove mysqldump artifacts
- SplittingStage: Split into individual statements
- TransformationStage: Route and convert DDL/DML statements
- PostprocessingStage: Final cleanup
"""

import re

import sqlglot
from sqlglot.errors import ParseError

from trinity_postgres_tools.dml.literal_converter import (
    convert_hex_literals_in_sql,
    remove_backticks,
)
from trinity_postgres_tools.parsing.classifier import (
    classify_statement,
)
from trinity_postgres_tools.parsing.splitter import split_statements
from trinity_postgres_tools.pipeline.context import ConversionContext, StatementType
from trinity_postgres_tools.pipeline.pipeline import BasePipelineStage
from trinity_postgres_tools.preprocessing.artifacts import remove_mysqldump_artifacts


class PreprocessingStage(BasePipelineStage):
    """Remove mysqldump artifacts before processing."""

    @property
    def name(self) -> str:
        return "preprocessing"

    def process(self, ctx: ConversionContext) -> ConversionContext:
        """Remove mysqldump artifacts from the input."""
        sql = ctx.current_statement or ""
        ctx.current_statement = remove_mysqldump_artifacts(sql, ctx)
        return ctx


class SplittingStage(BasePipelineStage):
    """Split SQL content into individual statements."""

    @property
    def name(self) -> str:
        return "splitting"

    def process(self, ctx: ConversionContext) -> ConversionContext:
        """Split into statements and store in context."""
        sql = ctx.current_statement or ""
        statements = split_statements(sql, ctx)

        # Store statements for transformation stage
        ctx.input_statements = [stmt.sql for stmt in statements if not stmt.is_comment_only]
        return ctx


class TransformationStage(BasePipelineStage):
    """Route statements to appropriate converters."""

    @property
    def name(self) -> str:
        return "transformation"

    def process(self, ctx: ConversionContext) -> ConversionContext:
        """Convert each statement based on its type."""
        for stmt in ctx.input_statements:
            classified = classify_statement(stmt)

            if classified.statement_type == StatementType.DDL:
                ctx.stats.ddl_count += 1
                converted = self._convert_ddl(stmt, ctx)
            elif classified.statement_type == StatementType.DML:
                ctx.stats.dml_count += 1
                converted = self._convert_dml(stmt, ctx)
            elif classified.statement_type == StatementType.EMPTY:
                continue
            else:
                ctx.stats.other_count += 1
                converted = self._convert_other(stmt, ctx)

            if converted and converted.strip():
                ctx.output_statements.append(converted)

        return ctx

    def _convert_ddl(self, sql: str, ctx: ConversionContext) -> str:
        """Convert DDL using sqlglot with pre/post processing."""
        sql = self._preprocess_ddl(sql)

        try:
            results = sqlglot.transpile(sql, read="mysql", write="postgres")
            if results:
                return self._postprocess_ddl(results[0])
            return sql
        except ParseError as e:
            ctx.log_debug(f"sqlglot error on DDL: {e}")
            ctx.stats.sqlglot_errors += 1
            # Fall back to DML-style regex conversion
            return self._convert_dml(sql, ctx)

    def _preprocess_ddl(self, sql: str) -> str:
        """Preprocess DDL for sqlglot compatibility."""
        # Convert AUTO_INCREMENT to SERIAL
        sql = re.sub(
            r"(\w+)\s+(?:tiny|small|medium)?int\s*(?:\(\d+\))?\s+(?:unsigned\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT",
            r"\1 SERIAL",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r"(\w+)\s+bigint\s*(?:\(\d+\))?\s+(?:unsigned\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT",
            r"\1 BIGSERIAL",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove table-level AUTO_INCREMENT = value
        sql = re.sub(r"AUTO_INCREMENT\s*=\s*\d+", "", sql, flags=re.IGNORECASE)

        # Remove unsigned from float/double/decimal
        sql = re.sub(
            r"\b(float|double|decimal|numeric)(\s*\([^)]+\))?\s+unsigned\b",
            r"\1\2",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove column-level CHARACTER SET and COLLATE
        sql = re.sub(
            r"\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove ENGINE clause
        sql = re.sub(r"\)\s*ENGINE\s*=\s*\w+[^;]*$", ")", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*ENGINE\s*=\s*\w+(?:\s+[^,;)]*)?", "", sql, flags=re.IGNORECASE)

        # Remove DEFAULT CHARSET, COLLATE, ROW_FORMAT, etc.
        sql = re.sub(r"\s*DEFAULT\s+CHARSET\s*=\s*\w+(?:\s+[^,;)]*)?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*COLLATE\s*=\s*\w+(?:\s+[^,;)]*)?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*ROW_FORMAT\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*KEY_BLOCK_SIZE\s*=\s*\d+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*PACK_KEYS\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*COMMENT\s*=\s*'[^']*'", "", sql, flags=re.IGNORECASE)

        # Remove ASC/DESC from index columns
        sql = re.sub(r"(`\w+`)\s+(ASC|DESC)(?=\s*[,)])", r"\1", sql, flags=re.IGNORECASE)

        return sql

    def _postprocess_ddl(self, sql: str) -> str:
        """Postprocess sqlglot output."""
        # Remove backticks
        sql = re.sub(r"`([^`]+)`", r"\1", sql)

        # Fix sqlglot's unsigned types
        sql = re.sub(r"\bUTINYINT\b", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUSMALLINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUMEDIUMINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUINT\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUBIGINT\(\d+\)", "BIGINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUBIGINT\b", "BIGINT", sql, flags=re.IGNORECASE)

        # Fix INT with size specifier
        sql = re.sub(r"\bINT\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\b", "INTEGER", sql, flags=re.IGNORECASE)

        # Convert ENUM/SET to TEXT
        sql = re.sub(r"\bENUM\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bSET\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)

        # Fix BYTEA size modifier
        sql = re.sub(r"\bBYTEA\s*\(\d+\)", "BYTEA", sql, flags=re.IGNORECASE)

        # Fix SMALLINT/TINYINT size specifier
        sql = re.sub(r"\bSMALLINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)

        # Clean up constraint names
        sql = re.sub(r'\bUNIQUE\s+"[^"]+"\s*\(', r"UNIQUE (", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bCONSTRAINT\s+"[^"]+"\s+UNIQUE\s*\(', r"UNIQUE (", sql, flags=re.IGNORECASE)

        # Remove inline INDEX/KEY definitions
        sql = re.sub(r',\s*INDEX\s+"[^"]+"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)
        sql = re.sub(r',\s*KEY\s+"[^"]+"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        # Remove FOREIGN KEY constraints
        sql = re.sub(
            r',\s*CONSTRAINT\s+"[^"]+"\s+FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+"[^"]+"\s*\([^)]+\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION))*',
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove USING BTREE/HASH and COLLATE
        sql = re.sub(r"\s+USING\s+(?:BTREE|HASH)", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s+COLLATE\s+\w+", "", sql, flags=re.IGNORECASE)

        # Remove FULLTEXT INDEX
        sql = re.sub(r',\s*FULLTEXT\s+INDEX\s+"[^"]+"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        return sql

    def _convert_dml(self, sql: str, ctx: ConversionContext) -> str:
        """Convert DML using tokenizer and escape handling."""
        # Remove backticks
        sql = remove_backticks(sql)

        # Convert escape sequences (inline, placeholder technique)
        # Protect escaped backslashes with placeholder
        placeholder = "\x00ESCAPED_BACKSLASH\x00"
        sql = sql.replace("\\\\", placeholder)
        # Convert escaped quotes: MySQL \' -> PostgreSQL ''
        sql = sql.replace("\\'", "''")
        # Remove escaped double quotes: MySQL \" -> PostgreSQL "
        sql = sql.replace('\\"', '"')
        # Restore escaped backslashes
        sql = sql.replace(placeholder, "\\\\")

        # Convert hex literals
        sql = convert_hex_literals_in_sql(sql)

        # Convert unsigned overflow values (inline)
        # MySQL BIGINT UNSIGNED max (18446744073709551615) -> -1
        sql = sql.replace("18446744073709551615", "-1")
        # MySQL INT UNSIGNED max (4294967295) -> -1
        sql = sql.replace("4294967295", "-1")

        # Convert large unsigned values to signed equivalents
        def convert_unsigned_to_signed(match: re.Match[str]) -> str:
            val = int(match.group(0))
            # Convert unsigned 64-bit values > BIGINT_MAX to signed
            if val > 9223372036854775807:
                return str(val - 18446744073709551616)
            # Convert unsigned 32-bit values > INT_MAX to signed
            if val > 2147483647:
                return str(val - 4294967296)
            return match.group(0)

        sql = re.sub(r"\b\d{10,}\b", convert_unsigned_to_signed, sql)

        # REPLACE INTO -> INSERT INTO
        sql = re.sub(r"\bREPLACE\s+INTO\b", "INSERT INTO", sql, flags=re.IGNORECASE)

        # Remove LIMIT from UPDATE/DELETE
        sql = re.sub(r"(\bUPDATE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE)
        sql = re.sub(r"(\bDELETE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE)

        # ON DUPLICATE KEY UPDATE -> ON CONFLICT DO UPDATE SET
        sql = re.sub(
            r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+(.+?)$",
            r"ON CONFLICT DO UPDATE SET \1",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    def _convert_other(self, sql: str, ctx: ConversionContext) -> str:
        """Convert other statements."""
        sql = remove_backticks(sql)

        # Basic function conversions
        sql = re.sub(r"\bUNIX_TIMESTAMP\(\)", "EXTRACT(EPOCH FROM NOW())", sql)
        sql = re.sub(
            r"\bFROM_UNIXTIME\s*\(\s*([^)]+)\s*\)",
            r"TO_TIMESTAMP(\1)",
            sql,
            flags=re.IGNORECASE,
        )

        # Fix update paths
        sql = re.sub(
            r"'\$/sql/updates/([^/]+)/(3\.3\.5|cata_classic)/mysql'",
            r"'$/sql/updates/\1/\2/postgresql'",
            sql,
        )

        return sql


class PostprocessingStage(BasePipelineStage):
    """Final cleanup of converted statements."""

    @property
    def name(self) -> str:
        return "postprocessing"

    def process(self, ctx: ConversionContext) -> ConversionContext:
        """Clean up any remaining issues."""
        cleaned = []
        for stmt in ctx.output_statements:
            # Remove any remaining backticks
            cleaned_stmt = re.sub(r"`([^`]+)`", r"\1", stmt)
            # Clean up excessive whitespace
            cleaned_stmt = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_stmt)
            cleaned.append(cleaned_stmt.strip())

        ctx.output_statements = cleaned
        return ctx
