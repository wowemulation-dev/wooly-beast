"""
Concrete pipeline stages for MySQL to PostgreSQL conversion.

Each stage implements a specific transformation step:
- PreprocessingStage: Remove mysqldump artifacts
- SplittingStage: Split into individual statements
- TransformationStage: Route and convert DDL/DML statements
- PostprocessingStage: Final cleanup
"""

import re


def _lowercase_identifiers_outside_strings(sql: str) -> str:
    """
    Lowercase backtick and double-quoted identifiers, but only outside of
    single-quoted SQL string literals.

    This is critical for preserving text data that contains literal double
    quotes, such as: INSERT INTO t VALUES ('He said "hello"');

    The regex-based approach fails because it cannot distinguish between:
    - "identifier" (PostgreSQL identifier, should be lowercased)
    - 'text with "quotes"' (string content, must NOT be lowercased)

    This function uses a state machine to track string boundaries.
    """
    result = []
    i = 0
    n = len(sql)

    while i < n:
        char = sql[i]

        # Check for single-quoted string literal start
        if char == "'":
            # Find the end of the string literal
            # Handle escaped quotes: '' (PostgreSQL/SQL standard) and \' (MySQL)
            start = i
            i += 1
            while i < n:
                if sql[i] == "'":
                    # Check for escaped quote ('')
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2  # Skip both quotes
                        continue
                    else:
                        # End of string
                        i += 1
                        break
                elif sql[i] == "\\" and i + 1 < n:
                    # Skip escaped character (MySQL style)
                    i += 2
                else:
                    i += 1
            # Append the entire string literal unchanged
            result.append(sql[start:i])
            continue

        # Check for backtick-quoted identifier (MySQL style)
        if char == "`":
            start = i
            i += 1
            while i < n and sql[i] != "`":
                i += 1
            if i < n:
                i += 1  # Include closing backtick
            # Extract identifier and lowercase it
            identifier = sql[start + 1 : i - 1] if i > start + 1 else ""
            result.append(identifier.lower())
            continue

        # Check for double-quoted identifier (PostgreSQL style)
        if char == '"':
            start = i
            i += 1
            while i < n and sql[i] != '"':
                if sql[i] == "\\" and i + 1 < n:
                    i += 2  # Skip escaped character
                else:
                    i += 1
            if i < n:
                i += 1  # Include closing quote
            # Extract identifier, lowercase it, and preserve quotes for reserved words
            identifier = sql[start + 1 : i - 1] if i > start + 1 else ""
            identifier_lower = identifier.lower()
            # Import here to avoid circular dependency
            from trinity_postgres_tools.dml.literal_converter import SQL_RESERVED_KEYWORDS
            if identifier_lower in SQL_RESERVED_KEYWORDS:
                # Reserved words MUST keep double quotes
                result.append(f'"{identifier_lower}"')
            else:
                # Non-reserved identifiers can be unquoted (PostgreSQL lowercases them)
                result.append(identifier_lower)
            continue

        # Regular character - append as-is
        result.append(char)
        i += 1

    return "".join(result)

import sqlglot
from sqlglot.errors import ParseError

from trinity_postgres_tools.dml.bytea_converter import convert_bytea_hex_in_insert
from trinity_postgres_tools.dml.literal_converter import (
    convert_hex_literals_in_sql,
    remove_backticks,
)
from trinity_postgres_tools.dml.user_variables import expand_user_variables
from trinity_postgres_tools.dml.view_converter import process_views
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

        # Extract VIEW definitions BEFORE removing conditional comments
        # Views are inside conditional comments and would be lost otherwise
        sql, view_definitions = process_views(sql)
        ctx.view_definitions = view_definitions

        if view_definitions:
            ctx.log_debug(f"Extracted {len(view_definitions)} VIEW definitions")

        sql = remove_mysqldump_artifacts(sql, ctx)

        # Expand MySQL user variables (@VAR) inline BEFORE splitting
        # This must happen before splitting because variable definitions and
        # their usages are in separate statements.
        # MySQL: SET @OGUID := 94047; INSERT INTO t VALUES (@OGUID);
        # PostgreSQL: INSERT INTO t VALUES (94047);
        sql = expand_user_variables(sql)

        ctx.current_statement = sql
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
        # Extract leading comments before sqlglot processing
        # sqlglot converts -- comments to /* */ and merges lines, breaking formatting
        lines = sql.split("\n")
        comment_lines = []
        ddl_lines = []
        in_ddl = False

        for line in lines:
            stripped = line.strip()
            if not in_ddl:
                # Check if this is a comment-only line
                if stripped.startswith("--"):
                    comment_lines.append(line)
                elif stripped.startswith("/*") and stripped.endswith("*/") and ";" not in stripped:
                    # Standalone block comment (not ending statement)
                    comment_lines.append(line)
                elif stripped == "":
                    # Preserve blank lines in comment section
                    if comment_lines:
                        comment_lines.append(line)
                else:
                    # Start of actual DDL
                    in_ddl = True
                    ddl_lines.append(line)
            else:
                ddl_lines.append(line)

        ddl_sql = "\n".join(ddl_lines)
        original_ddl = ddl_sql
        ddl_sql = self._preprocess_ddl(ddl_sql)

        # Check if preprocessing already converted to PostgreSQL syntax
        # (e.g., ALTER TABLE ... ALTER COLUMN ... ADD GENERATED BY DEFAULT AS IDENTITY)
        # If so, skip sqlglot and just do postprocessing
        if "ADD GENERATED BY DEFAULT AS IDENTITY" in ddl_sql or "DROP CONSTRAINT IF EXISTS" in ddl_sql:
            # Preprocessing handled this - just do final cleanup
            converted = self._postprocess_ddl(ddl_sql)
            if comment_lines:
                return "\n".join(comment_lines) + "\n" + converted
            return converted

        try:
            results = sqlglot.transpile(ddl_sql, read="mysql", write="postgres")
            if results:
                converted = self._postprocess_ddl(results[0])
                # Reassemble with comments preserved
                if comment_lines:
                    return "\n".join(comment_lines) + "\n" + converted
                return converted
            return sql
        except ParseError as e:
            ctx.log_debug(f"sqlglot error on DDL: {e}")
            ctx.stats.sqlglot_errors += 1
            # Fall back to regex-based DDL conversion
            converted = self._convert_ddl_fallback(ddl_sql, ctx)
            if comment_lines:
                return "\n".join(comment_lines) + "\n" + converted
            return converted

    def _preprocess_ddl(self, sql: str) -> str:
        """Preprocess DDL for sqlglot compatibility."""
        # Remove backticks first - sqlglot fails to convert AUTO_INCREMENT
        # to GENERATED BY DEFAULT AS IDENTITY when backticks are present
        sql = remove_backticks(sql)

        # Remove table-level options EARLY - before we try to match ALTER TABLE operations
        # These can appear between ALTER TABLE tablename and the actual operation (CHANGE, ADD, etc.)
        # MySQL: ALTER TABLE foo ROW_FORMAT=DEFAULT, CHANGE col ...
        # We need to remove ROW_FORMAT=DEFAULT, first so CHANGE matching works
        sql = re.sub(r",?\s*ROW_FORMAT\s*=\s*\w+\s*,?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r",?\s*ENGINE\s*=\s*\w+\s*,?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r",?\s*AUTO_INCREMENT\s*=\s*\d+\s*,?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r",?\s*DEFAULT\s+CHARSET\s*=\s*\w+\s*,?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r",?\s*COLLATE\s*=\s*\w+\s*,?", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r",?\s*COMMENT\s*=\s*'[^']*'\s*,?", "", sql, flags=re.IGNORECASE)

        # Clean up any dangling newlines or commas left after removal
        sql = re.sub(r"\n\s*\n+", "\n", sql)
        sql = re.sub(r",\s*,", ",", sql)

        # Handle MySQL ALTER TABLE ... DROP PRIMARY KEY
        # PostgreSQL requires: ALTER TABLE ... DROP CONSTRAINT constraint_name
        # For primary keys, the constraint name is typically tablename_pkey
        def convert_drop_primary_key(m: re.Match[str]) -> str:
            table_name = m.group(1).lower().strip('`"')
            return f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {table_name}_pkey"

        sql = re.sub(
            r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)\s+DROP\s+PRIMARY\s+KEY",
            convert_drop_primary_key,
            sql,
            flags=re.IGNORECASE,
        )

        # Handle inline DROP PRIMARY KEY (in multi-clause ALTER TABLE)
        # This appears as just "DROP PRIMARY KEY" after the table name was already specified
        # We need context from the ALTER TABLE statement
        def convert_inline_drop_primary_key(m: re.Match[str]) -> str:
            # Try to find the table name from earlier in the statement
            # For now, use a placeholder that will need manual review
            return "-- DROP PRIMARY KEY (needs manual conversion)"

        sql = re.sub(
            r",\s*DROP\s+PRIMARY\s+KEY(?=\s*[,;]|$)",
            convert_inline_drop_primary_key,
            sql,
            flags=re.IGNORECASE,
        )

        # Handle DROP KEY/INDEX (MySQL syntax for dropping index)
        # PostgreSQL uses DROP INDEX, but inside ALTER TABLE we use DROP CONSTRAINT
        sql = re.sub(
            r"\bDROP\s+(?:KEY|INDEX)\s+([`\"]?\w+[`\"]?)(?=\s*[,;]|$)",
            lambda m: f"DROP INDEX IF EXISTS {m.group(1).lower().strip('`\"')}",
            sql,
            flags=re.IGNORECASE,
        )

        # Handle DROP column_name (MySQL shorthand without COLUMN keyword)
        # Must NOT match: DROP PRIMARY KEY, DROP KEY, DROP INDEX, DROP FOREIGN KEY, DROP CONSTRAINT
        # MySQL: ALTER TABLE t DROP col
        # PostgreSQL: ALTER TABLE t DROP COLUMN col
        sql = re.sub(
            r"\bDROP\s+(?!PRIMARY|KEY|INDEX|FOREIGN|CONSTRAINT|COLUMN)([`\"]?\w+[`\"]?)(?=\s*[,;]|$)",
            lambda m: f"DROP COLUMN {m.group(1).lower().strip('`\"')}",
            sql,
            flags=re.IGNORECASE,
        )

        # Handle ADD INDEX/KEY (MySQL syntax) - convert to CREATE INDEX
        # This needs to be a separate statement in PostgreSQL
        def convert_add_index(m: re.Match[str]) -> str:
            full_match = m.group(0)
            # Extract table name if present, otherwise use placeholder
            table_match = re.search(r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)", sql[:m.start()], re.IGNORECASE)
            table = table_match.group(1).lower().strip('`"') if table_match else "UNKNOWN_TABLE"

            # Check if index has a name
            name_match = re.match(r"ADD\s+(?:INDEX|KEY)\s+([`\"]?\w+[`\"]?)\s*\(", full_match, re.IGNORECASE)
            if name_match:
                idx_name = name_match.group(1).lower().strip('`"')
            else:
                idx_name = f"idx_{table}_auto"

            # Extract columns
            cols_match = re.search(r"\(([^)]+)\)", full_match)
            cols = cols_match.group(1) if cols_match else ""
            # Clean up column names
            cols = re.sub(r'[`"]', '', cols).lower()

            return f"; CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})"

        sql = re.sub(
            r"ADD\s+(?:INDEX|KEY)(?:\s+[`\"]?\w+[`\"]?)?\s*\([^)]+\)",
            convert_add_index,
            sql,
            flags=re.IGNORECASE,
        )

        # Handle ADD UNIQUE INDEX/KEY
        def convert_add_unique_index(m: re.Match[str]) -> str:
            full_match = m.group(0)
            table_match = re.search(r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)", sql[:m.start()], re.IGNORECASE)
            table = table_match.group(1).lower().strip('`"') if table_match else "UNKNOWN_TABLE"

            name_match = re.match(r"ADD\s+UNIQUE\s+(?:INDEX|KEY)?\s*([`\"]?\w+[`\"]?)?\s*\(", full_match, re.IGNORECASE)
            if name_match and name_match.group(1):
                idx_name = name_match.group(1).lower().strip('`"')
            else:
                idx_name = f"idx_{table}_unique"

            cols_match = re.search(r"\(([^)]+)\)", full_match)
            cols = cols_match.group(1) if cols_match else ""
            cols = re.sub(r'[`"]', '', cols).lower()

            return f"; CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})"

        sql = re.sub(
            r"ADD\s+UNIQUE\s+(?:INDEX|KEY)?(?:\s+[`\"]?\w+[`\"]?)?\s*\([^)]+\)",
            convert_add_unique_index,
            sql,
            flags=re.IGNORECASE,
        )

        # Remove AFTER column clause (MySQL-specific column positioning)
        # PostgreSQL always adds columns at the end
        sql = re.sub(
            r"\s+AFTER\s+[`\"]?\w+[`\"]?(?=\s*[,;)]|\s*$)",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove FIRST keyword (MySQL-specific column positioning)
        # PostgreSQL always adds columns at the end
        sql = re.sub(
            r"\s+FIRST(?=\s*[,;)]|\s*$)",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert RENAME TABLE old TO new → ALTER TABLE old RENAME TO new
        sql = re.sub(
            r"RENAME\s+TABLE\s+([`\"]?\w+[`\"]?)\s+TO\s+([`\"]?\w+[`\"]?)",
            r"ALTER TABLE \1 RENAME TO \2",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove ALTER TABLE ... CONVERT TO CHARACTER SET (PostgreSQL uses database-level encoding)
        sql = re.sub(
            r"ALTER\s+TABLE\s+[`\"]?\w+[`\"]?\s+CONVERT\s+TO\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?",
            "-- Removed: CONVERT TO CHARACTER SET (PostgreSQL uses database-level encoding)",
            sql,
            flags=re.IGNORECASE,
        )

        # Handle ALTER TABLE ... MODIFY COLUMN col type → ALTER TABLE ... ALTER COLUMN col TYPE type
        # This is a simplified conversion - full MODIFY COLUMN support would need more parsing
        def convert_modify_column(m: re.Match[str]) -> str:
            table = m.group(1).lower().strip('`"')
            column = m.group(2).lower().strip('`"')
            col_type = m.group(3).strip()
            # Extract base type, removing NOT NULL, DEFAULT, etc. for TYPE clause
            type_match = re.match(r"(\w+(?:\s*\([^)]+\))?)", col_type)
            base_type = type_match.group(1) if type_match else col_type.split()[0]
            return f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {base_type}"

        sql = re.sub(
            r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)\s+MODIFY\s+(?:COLUMN\s+)?([`\"]?\w+[`\"]?)\s+(.+?)(?=\s*[,;]|$)",
            convert_modify_column,
            sql,
            flags=re.IGNORECASE,
        )

        # Handle ALTER TABLE ... CHANGE old_col new_col type → RENAME COLUMN + ALTER COLUMN TYPE
        # This handles column renames with type changes, including AUTO_INCREMENT
        def convert_change_column(m: re.Match[str]) -> str:
            table = m.group(1).lower().strip('`"')
            old_col = m.group(2).lower().strip('`"')
            new_col = m.group(3).lower().strip('`"')
            col_def = m.group(4).strip()

            # Check for AUTO_INCREMENT
            has_auto_increment = bool(re.search(r"\bAUTO_INCREMENT\b", col_def, re.IGNORECASE))

            # Extract base type, removing size specifiers for int types
            # Also remove UNSIGNED, NOT NULL, DEFAULT, AUTO_INCREMENT, COMMENT
            type_match = re.match(r"(\w+)(?:\s*\(\d+\))?", col_def)
            base_type = type_match.group(1).upper() if type_match else col_def.split()[0].upper()

            # Convert MySQL types to PostgreSQL
            type_map = {
                "TINYINT": "SMALLINT",
                "SMALLINT": "SMALLINT",
                "MEDIUMINT": "INTEGER",
                "INT": "INTEGER",
                "INTEGER": "INTEGER",
                "BIGINT": "BIGINT",
            }
            pg_type = type_map.get(base_type, base_type)

            statements = []
            if old_col != new_col:
                # Rename first
                statements.append(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}")

            # Type change
            statements.append(f"ALTER TABLE {table} ALTER COLUMN {new_col} TYPE {pg_type}")

            # Add IDENTITY if AUTO_INCREMENT was specified
            if has_auto_increment:
                statements.append(f"ALTER TABLE {table} ALTER COLUMN {new_col} ADD GENERATED BY DEFAULT AS IDENTITY")

            return "; ".join(statements)

        sql = re.sub(
            r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)\s+CHANGE\s+(?:COLUMN\s+)?([`\"]?\w+[`\"]?)\s+([`\"]?\w+[`\"]?)\s+(.+?)(?=\s*[,;]|$)",
            convert_change_column,
            sql,
            flags=re.IGNORECASE,
        )

        # Handle ALTER TABLE ... ADD COLUMN col type AUTO_INCREMENT
        def convert_add_column_auto_increment(m: re.Match[str]) -> str:
            table = m.group(1).lower().strip('`"')
            col = m.group(2).lower().strip('`"')
            col_def = m.group(3).strip()

            # Extract base type
            type_match = re.match(r"(\w+)(?:\s*\(\d+\))?", col_def)
            base_type = type_match.group(1).upper() if type_match else col_def.split()[0].upper()

            # Convert MySQL types to PostgreSQL
            type_map = {
                "TINYINT": "SMALLINT",
                "SMALLINT": "SMALLINT",
                "MEDIUMINT": "INTEGER",
                "INT": "INTEGER",
                "INTEGER": "INTEGER",
                "BIGINT": "BIGINT",
            }
            pg_type = type_map.get(base_type, base_type)

            # Check for NOT NULL
            not_null = " NOT NULL" if re.search(r"\bNOT\s+NULL\b", col_def, re.IGNORECASE) else ""

            return f"ALTER TABLE {table} ADD COLUMN {col} {pg_type} GENERATED BY DEFAULT AS IDENTITY{not_null}"

        sql = re.sub(
            r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)\s+ADD\s+COLUMN\s+([`\"]?\w+[`\"]?)\s+(.+?AUTO_INCREMENT.+?)(?=\s*[,;]|$)",
            convert_add_column_auto_increment,
            sql,
            flags=re.IGNORECASE,
        )

        # Remove column-level COMMENT (MySQL-specific, not in standard CREATE TABLE)
        # PostgreSQL uses separate COMMENT ON COLUMN statements
        sql = re.sub(
            r"\s+COMMENT\s+'[^']*'",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert MySQL bitwise AND NOT operator (&~) to PostgreSQL syntax (& ~)
        # MySQL: value&~4 means "value AND NOT 4" (clear bit 4)
        # PostgreSQL: value & ~4 (needs space, ~ is unary NOT)
        sql = re.sub(
            r"&~(\d+)",
            r"& ~\1",
            sql,
        )

        # NOTE: AUTO_INCREMENT is handled by sqlglot - it converts to
        # GENERATED BY DEFAULT AS IDENTITY which is the SQL standard way

        # Clean up malformed ALTER TABLE statements with dangling commas
        # e.g., "ALTER TABLE foo," → "ALTER TABLE foo"
        sql = re.sub(r"(ALTER\s+TABLE\s+\w+)\s*,\s*$", r"\1", sql, flags=re.IGNORECASE | re.MULTILINE)

        # Clean up empty ALTER TABLE statements (when all operations were extracted)
        # e.g., "ALTER TABLE foo ;" → "" (the operations became separate CREATE INDEX statements)
        sql = re.sub(r"ALTER\s+TABLE\s+\w+\s*;", "", sql, flags=re.IGNORECASE)

        # Clean up trailing commas before semicolons
        sql = re.sub(r",\s*;", ";", sql)

        # Clean up multiple semicolons
        sql = re.sub(r";\s*;+", ";", sql)

        # Remove unsigned from float/double/decimal
        sql = re.sub(
            r"\b(float|double|decimal|numeric)(\s*\([^)]+\))?\s+unsigned\b",
            r"\1\2",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove unsigned from integer types - PostgreSQL doesn't have unsigned
        # This must happen before sqlglot for AUTO_INCREMENT to be recognized
        sql = re.sub(
            r"\b((?:tiny|small|medium|big)?int)(\s*\(\d+\))?\s+unsigned\b",
            r"\1\2",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert tinyint AUTO_INCREMENT to smallint AUTO_INCREMENT
        # sqlglot doesn't recognize tinyint AUTO_INCREMENT for IDENTITY conversion
        sql = re.sub(
            r"\btinyint(\s*\(\d+\))?\s+(NOT\s+NULL\s+)?AUTO_INCREMENT\b",
            r"smallint \2AUTO_INCREMENT",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert binary(n) to bytea - sqlglot doesn't recognize MySQL binary type
        sql = re.sub(
            r"\bbinary\s*\(\d+\)",
            "bytea",
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

        # Remove remaining table options that may appear in CREATE TABLE closing
        sql = re.sub(r"\s*KEY_BLOCK_SIZE\s*=\s*\d+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*PACK_KEYS\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        # Remove ENGINE clause at end of CREATE TABLE (after other options are gone)
        sql = re.sub(r"\)\s*ENGINE\s*=\s*\w+\s*;", ");", sql, flags=re.IGNORECASE)

        # Remove ASC/DESC from index columns (handles quoted and unquoted identifiers)
        sql = re.sub(r"(\w+)\s+(ASC|DESC)(?=\s*[,)])", r"\1", sql, flags=re.IGNORECASE)
        sql = re.sub(r"(`\w+`)\s+(ASC|DESC)(?=\s*[,)])", r"\1", sql, flags=re.IGNORECASE)
        sql = re.sub(r'("[^"]+")\s+(ASC|DESC)(?=\s*[,)])', r"\1", sql, flags=re.IGNORECASE)

        # Remove ON UPDATE CURRENT_TIMESTAMP (MySQL-specific, requires trigger in PostgreSQL)
        # This clause auto-updates a timestamp column when a row is modified
        sql = re.sub(
            r"\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\s*\(\d*\))?",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert MEDIUMINT to INTEGER before sqlglot processing
        sql = re.sub(r"\bMEDIUMINT\b", "INTEGER", sql, flags=re.IGNORECASE)

        return sql

    def _postprocess_ddl(self, sql: str) -> str:
        """Postprocess sqlglot output."""
        # Remove backticks and lowercase identifiers for PostgreSQL consistency
        # PostgreSQL normalizes unquoted identifiers to lowercase, so we must
        # lowercase all identifiers to ensure DDL and DML match
        sql = re.sub(r"`([^`]+)`", lambda m: m.group(1).lower(), sql)

        # Fix sqlglot's incorrect single-quote identifiers for reserved words
        # sqlglot outputs 'key' instead of "key" for reserved keywords
        # Convert single-quoted reserved keywords to double-quoted
        from trinity_postgres_tools.dml.literal_converter import SQL_RESERVED_KEYWORDS

        def fix_single_quoted_identifier(m: re.Match[str]) -> str:
            name = m.group(1).lower()
            if name in SQL_RESERVED_KEYWORDS:
                return f'"{name}"'
            # Not a reserved word, this might be a string literal - leave as-is
            return m.group(0)

        sql = re.sub(r"'([a-zA-Z_][a-zA-Z0-9_]*)'", fix_single_quoted_identifier, sql)

        # Lowercase double-quoted identifiers (sqlglot produces these)
        # This ensures column names like "CreatureId" become "creatureid"
        sql = re.sub(r'"([^"]+)"', lambda m: f'"{m.group(1).lower()}"', sql)

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

        # Convert BLOB to BYTEA (sqlglot outputs BLOB for MySQL blob types)
        sql = re.sub(r"\bBLOB\b", "BYTEA", sql, flags=re.IGNORECASE)

        # Convert CHAR(n) to VARCHAR(n) to avoid PostgreSQL CHAR padding issues
        # PostgreSQL pads CHAR columns with spaces to the declared length, which
        # causes problems when comparing short strings (e.g., "OSX" becomes "OSX ")
        sql = re.sub(r"\bCHAR\s*\((\d+)\)", r"VARCHAR(\1)", sql, flags=re.IGNORECASE)

        # Fix SMALLINT/TINYINT size specifier
        sql = re.sub(r"\bSMALLINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)

        # Clean up constraint names (handles both quoted and unquoted identifiers)
        # UNIQUE "name" (col) or UNIQUE name (col) -> UNIQUE (col)
        sql = re.sub(r'\bUNIQUE\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s*\(', r"UNIQUE (", sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bCONSTRAINT\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s+UNIQUE\s*\(', r"UNIQUE (", sql, flags=re.IGNORECASE)

        # Remove inline INDEX/KEY definitions (handles both quoted and unquoted identifiers)
        sql = re.sub(r',\s*INDEX\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)
        sql = re.sub(r',\s*KEY\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        # Remove FOREIGN KEY constraints (handles both quoted and unquoted identifiers)
        sql = re.sub(
            r',\s*CONSTRAINT\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s+FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s*\([^)]+\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION))*',
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove USING BTREE/HASH and COLLATE
        sql = re.sub(r"\s+USING\s+(?:BTREE|HASH)", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s+COLLATE\s+\w+", "", sql, flags=re.IGNORECASE)

        # Remove FULLTEXT INDEX (handles both quoted and unquoted identifiers)
        sql = re.sub(r',\s*FULLTEXT\s+INDEX\s+(?:"[^"]+"|[a-z_][a-z0-9_]*)\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        return sql

    def _convert_ddl_fallback(self, sql: str, ctx: ConversionContext) -> str:
        """Convert DDL using regex when sqlglot fails.

        This handles CREATE TABLE statements with complex syntax that sqlglot
        cannot parse, such as columns with CHARACTER SET or COLLATE clauses.
        """
        ctx.log_debug("Using regex fallback for DDL conversion")

        # Remove backticks and convert to lowercase identifiers
        sql = remove_backticks(sql)

        # === MySQL Data Type Conversions ===

        # Integer types with UNSIGNED (remove UNSIGNED, PostgreSQL doesn't have it)
        sql = re.sub(r"\bBIGINT\s*\(\d+\)\s+UNSIGNED\b", "BIGINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bBIGINT\s+UNSIGNED\b", "BIGINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\s*\(\d+\)\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMINT\s*\(\d+\)\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMINT\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bSMALLINT\s*\(\d+\)\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bSMALLINT\s+UNSIGNED\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s*\(\d+\)\s+UNSIGNED\b", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s+UNSIGNED\b", "SMALLINT", sql, flags=re.IGNORECASE)

        # Integer types without UNSIGNED
        sql = re.sub(r"\bBIGINT\s*\(\d+\)", "BIGINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\s*\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\b(?!\s*\()", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMINT\s*\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bSMALLINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\b", "SMALLINT", sql, flags=re.IGNORECASE)

        # Text types
        sql = re.sub(r"\bLONGTEXT\b", "TEXT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMTEXT\b", "TEXT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYTEXT\b", "TEXT", sql, flags=re.IGNORECASE)

        # Blob types
        sql = re.sub(r"\bLONGBLOB\b", "BYTEA", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bMEDIUMBLOB\b", "BYTEA", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYBLOB\b", "BYTEA", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bBLOB\b", "BYTEA", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bBINARY\s*\(\d+\)", "BYTEA", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bVARBINARY\s*\(\d+\)", "BYTEA", sql, flags=re.IGNORECASE)

        # DOUBLE and FLOAT
        sql = re.sub(r"\bDOUBLE\s+PRECISION\b", "DOUBLE PRECISION", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bDOUBLE\b(?!\s+PRECISION)", "DOUBLE PRECISION", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bFLOAT\s*\(\d+,\s*\d+\)", "REAL", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bFLOAT\s*\(\d+\)", "REAL", sql, flags=re.IGNORECASE)

        # DATETIME and TIMESTAMP
        sql = re.sub(r"\bDATETIME\s*\(\d+\)", "TIMESTAMP", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bDATETIME\b", "TIMESTAMP", sql, flags=re.IGNORECASE)

        # ENUM and SET to TEXT
        sql = re.sub(r"\bENUM\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bSET\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)

        # CHAR to VARCHAR (avoid PostgreSQL padding issues)
        sql = re.sub(r"\bCHAR\s*\((\d+)\)", r"VARCHAR(\1)", sql, flags=re.IGNORECASE)

        # === Remove MySQL-specific Column Options ===

        # Remove CHARACTER SET and COLLATE from column definitions
        sql = re.sub(
            r"\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?",
            "",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(r"\s+COLLATE\s+\w+", "", sql, flags=re.IGNORECASE)

        # Remove COMMENT clauses
        sql = re.sub(r"\s+COMMENT\s+'[^']*'", "", sql, flags=re.IGNORECASE)

        # Remove ON UPDATE CURRENT_TIMESTAMP
        sql = re.sub(
            r"\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\s*\(\d*\))?",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # === Remove MySQL-specific Table Options ===

        # Remove ENGINE clause
        sql = re.sub(r"\s*ENGINE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove DEFAULT CHARSET
        sql = re.sub(r"\s*DEFAULT\s+CHARSET\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*CHARSET\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove AUTO_INCREMENT table option
        sql = re.sub(r"\s*AUTO_INCREMENT\s*=\s*\d+", "", sql, flags=re.IGNORECASE)

        # Remove ROW_FORMAT
        sql = re.sub(r"\s*ROW_FORMAT\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove KEY_BLOCK_SIZE
        sql = re.sub(r"\s*KEY_BLOCK_SIZE\s*=\s*\d+", "", sql, flags=re.IGNORECASE)

        # Remove PACK_KEYS
        sql = re.sub(r"\s*PACK_KEYS\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove table COLLATE
        sql = re.sub(r"\s*COLLATE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove table COMMENT (including the = sign and quotes)
        sql = re.sub(r"\)\s*COMMENT\s*=\s*'[^']*'\s*;", ");", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*COMMENT\s*=\s*'[^']*'", "", sql, flags=re.IGNORECASE)

        # === Convert AUTO_INCREMENT to IDENTITY ===

        # AUTO_INCREMENT column becomes GENERATED BY DEFAULT AS IDENTITY
        def convert_auto_increment(m: re.Match[str]) -> str:
            col_def = m.group(0)
            # Remove AUTO_INCREMENT keyword
            col_def = re.sub(r"\s*AUTO_INCREMENT\b", "", col_def, flags=re.IGNORECASE)
            # Add IDENTITY clause
            col_def = col_def.rstrip(",") + " GENERATED BY DEFAULT AS IDENTITY"
            if m.group(0).rstrip().endswith(","):
                col_def += ","
            return col_def

        sql = re.sub(
            r"\b\w+\s+(?:INTEGER|BIGINT|SMALLINT)\s+[^,)]*AUTO_INCREMENT[^,)]*(?=[,)])",
            convert_auto_increment,
            sql,
            flags=re.IGNORECASE,
        )

        # === Handle Index Definitions ===

        # Remove inline INDEX/KEY definitions
        sql = re.sub(r',\s*INDEX\s+\w+\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)
        sql = re.sub(r',\s*KEY\s+\w+\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        # Remove FULLTEXT INDEX
        sql = re.sub(r',\s*FULLTEXT\s+(?:INDEX|KEY)\s+\w+\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)

        # Remove UNIQUE INDEX/KEY (keep as UNIQUE constraint)
        sql = re.sub(r'\bUNIQUE\s+(?:INDEX|KEY)\s+\w+\s*', "UNIQUE ", sql, flags=re.IGNORECASE)

        # Remove USING BTREE/HASH
        sql = re.sub(r"\s+USING\s+(?:BTREE|HASH)", "", sql, flags=re.IGNORECASE)

        # === Clean up ===

        # Remove orphaned ='value' patterns at end of CREATE TABLE
        # (leftover from COMMENT='value' when COMMENT keyword was removed separately)
        sql = re.sub(r"\)\s*=\s*'[^']*'\s*;", ");", sql, flags=re.IGNORECASE)

        # Remove extra commas before closing parenthesis
        sql = re.sub(r",\s*\)", ")", sql)

        # Remove multiple consecutive commas
        sql = re.sub(r",\s*,+", ",", sql)

        # Remove extra whitespace
        sql = re.sub(r"\n\s*\n+", "\n", sql)

        # Lowercase identifiers (for PostgreSQL consistency)
        sql = re.sub(r'\b([A-Z_][A-Z0-9_]*)\b(?!["\'])', lambda m: m.group(1).lower(), sql)

        return sql

    def _convert_dml(self, sql: str, ctx: ConversionContext) -> str:
        """Convert DML using tokenizer and escape handling."""
        # Note: User variable expansion is done in PreprocessingStage before splitting

        # IMPORTANT: Convert MySQL double-quoted strings to PostgreSQL single-quoted
        # strings BEFORE converting backticks. This order matters because:
        # 1. MySQL uses backticks for identifiers, double or single quotes for strings
        # 2. PostgreSQL uses double quotes for identifiers, single quotes for strings
        # 3. If we convert backticks first (e.g., `type` -> "type"), then the
        #    double-quote string conversion would incorrectly convert the identifier
        #    "type" to 'type' (a string literal)
        def convert_dquoted_string(match: re.Match[str]) -> str:
            inner = match.group(1)
            # Handle MySQL escaped double quotes (\") -> literal double quote
            inner = inner.replace('\\"', '"')
            # Escape any single quotes by doubling them (PostgreSQL style)
            inner = inner.replace("'", "''")
            return f"'{inner}'"

        # Pattern matches double-quoted strings handling escape sequences
        dquote_pattern = r'"((?:[^"\\]|\\.)*)"'
        sql = re.sub(dquote_pattern, convert_dquoted_string, sql)

        # NOW convert backticks to PostgreSQL identifiers
        # After double-quoted strings are converted to single-quoted,
        # backtick identifiers like `type` become "type" (double-quoted)
        sql = remove_backticks(sql)

        # Convert escape sequences (inline, placeholder technique)
        # Protect escaped backslashes with placeholder
        placeholder = "\x00ESCAPED_BACKSLASH\x00"
        sql = sql.replace("\\\\", placeholder)
        # Convert escaped quotes: MySQL \' -> PostgreSQL ''
        sql = sql.replace("\\'", "''")
        # Restore escaped backslashes
        sql = sql.replace(placeholder, "\\\\")

        # Convert hex literals in BYTEA columns to decode() format FIRST
        # This must happen before generic hex conversion, which converts to integers
        sql = convert_bytea_hex_in_insert(sql)

        # Convert remaining hex literals to integers (for flags/masks)
        sql = convert_hex_literals_in_sql(sql)

        # Convert MySQL bitwise AND NOT operator (&~) to PostgreSQL syntax (& ~)
        # MySQL: value&~4 means "value AND NOT 4" (clear bit 4)
        # PostgreSQL: value & ~4 (needs space, ~ is unary NOT)
        sql = re.sub(r"&~(\d+)", r"& ~\1", sql)

        # Convert bitwise AND in boolean context to explicit comparison
        # MySQL: WHERE col & 1  (truthy if non-zero)
        # PostgreSQL: WHERE (col & 1) <> 0  (requires explicit boolean)
        # Match: WHERE col & N at end of clause (before ; or AND/OR or end of string)
        sql = re.sub(
            r"\bWHERE\s+(\w+)\s*&\s*(\d+)\s*(?=;|$)",
            r"WHERE (\1 & \2) <> 0",
            sql,
            flags=re.IGNORECASE,
        )

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

        # Use negative lookbehind/lookahead to skip:
        # 1. Already-negative numbers (-2147483648 would become --2147483648)
        # 2. Decimal parts of floats (2238.3603515625 - the 3603515625 is NOT an integer)
        # 3. Integer parts of floats (must not have a dot after)
        sql = re.sub(r"(?<![.\-])\b\d{10,}\b(?!\.)", convert_unsigned_to_signed, sql)

        # REPLACE INTO -> INSERT INTO
        sql = re.sub(r"\bREPLACE\s+INTO\b", "INSERT INTO", sql, flags=re.IGNORECASE)

        # Remove LIMIT from UPDATE/DELETE
        sql = re.sub(r"(\bUPDATE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE)
        sql = re.sub(r"(\bDELETE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE)

        # Convert UPDATE ... ORDER BY to PostgreSQL DO block with cursor
        # MySQL allows ORDER BY in UPDATE for controlled row processing order
        # PostgreSQL doesn't support this syntax, but order matters when updating
        # primary key columns to avoid constraint violations
        sql = self._convert_update_order_by(sql)

        # ON DUPLICATE KEY UPDATE -> ON CONFLICT DO UPDATE SET
        sql = re.sub(
            r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+(.+?)$",
            r"ON CONFLICT DO UPDATE SET \1",
            sql,
            flags=re.IGNORECASE,
        )

        # Convert MySQL IFNULL to PostgreSQL COALESCE
        sql = re.sub(r"\bIFNULL\s*\(", "COALESCE(", sql, flags=re.IGNORECASE)

        return sql

    def _convert_update_order_by(self, sql: str) -> str:
        """Convert MySQL UPDATE ... ORDER BY to PostgreSQL DO block with cursor.

        MySQL allows ORDER BY in UPDATE for controlled row processing order.
        PostgreSQL doesn't support this syntax. When updating a column that's
        part of a primary key or unique constraint, the order matters to avoid
        constraint violations.

        Converts:
            UPDATE table SET col = expr ORDER BY col2 DESC;
        To:
            DO $$
            DECLARE
                rec RECORD;
            BEGIN
                FOR rec IN SELECT ctid FROM table ORDER BY col2 DESC
                LOOP
                    UPDATE table SET col = expr WHERE ctid = rec.ctid;
                END LOOP;
            END $$;
        """
        # Pattern to match UPDATE ... SET ... ORDER BY ...
        # Handles both with and without WHERE clause
        pattern = r"""
            \bUPDATE\s+
            (\w+)\s+                           # table name (group 1)
            SET\s+
            (.+?)                              # SET clause (group 2)
            (?:\s+WHERE\s+(.+?))?              # optional WHERE clause (group 3)
            \s+ORDER\s+BY\s+
            (.+?)                              # ORDER BY clause (group 4)
            (?=\s*;|\s*$)                      # lookahead for semicolon or end
        """

        match = re.search(pattern, sql, flags=re.IGNORECASE | re.VERBOSE | re.DOTALL)
        if not match:
            return sql

        table_name = match.group(1)
        set_clause = match.group(2).strip()
        where_clause = match.group(3)
        order_by_clause = match.group(4).strip()

        # Build the SELECT statement for the cursor
        select_sql = f"SELECT ctid FROM {table_name}"
        if where_clause:
            select_sql += f" WHERE {where_clause.strip()}"
        select_sql += f" ORDER BY {order_by_clause}"

        # Build the UPDATE statement inside the loop
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE ctid = rec.ctid"
        if where_clause:
            # The WHERE from original is already applied in SELECT,
            # but we add it here for correctness (ctid already filters)
            pass  # ctid is unique, no need to repeat WHERE

        # Generate PostgreSQL DO block
        do_block = f"""DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN {select_sql}
    LOOP
        {update_sql};
    END LOOP;
END $$"""

        return do_block

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
            # Remove any remaining backticks and lowercase identifiers
            # Use string-aware processing to avoid corrupting quoted text content
            cleaned_stmt = _lowercase_identifiers_outside_strings(stmt)
            # Clean up excessive whitespace
            cleaned_stmt = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_stmt)
            cleaned_stmt = cleaned_stmt.strip()
            # Skip empty statements (just semicolons or whitespace)
            if cleaned_stmt and cleaned_stmt != ";" and not re.match(r"^[;\s]*$", cleaned_stmt):
                cleaned.append(cleaned_stmt)

        # Append VIEW definitions at the end (views depend on tables)
        if ctx.view_definitions:
            # Add a section comment for views
            cleaned.append("\n-- PostgreSQL VIEW definitions")
            for view_stmt in ctx.view_definitions:
                # View definitions are already converted by view_converter.py
                cleaned.append(view_stmt)
            ctx.log_debug(f"Added {len(ctx.view_definitions)} VIEW definitions to output")

        ctx.output_statements = cleaned
        return ctx
