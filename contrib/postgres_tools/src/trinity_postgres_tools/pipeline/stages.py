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
            # Extract identifier and lowercase it
            identifier = sql[start + 1 : i - 1] if i > start + 1 else ""
            result.append(identifier.lower())
            continue

        # Regular character - append as-is
        result.append(char)
        i += 1

    return "".join(result)

import sqlglot
from sqlglot.errors import ParseError

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
        ddl_sql = self._preprocess_ddl(ddl_sql)

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
            # Fall back to DML-style regex conversion
            return self._convert_dml(sql, ctx)

    def _preprocess_ddl(self, sql: str) -> str:
        """Preprocess DDL for sqlglot compatibility."""
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
        # This handles column renames with type changes
        def convert_change_column(m: re.Match[str]) -> str:
            table = m.group(1).lower().strip('`"')
            old_col = m.group(2).lower().strip('`"')
            new_col = m.group(3).lower().strip('`"')
            col_type = m.group(4).strip()
            # Extract base type for TYPE clause
            type_match = re.match(r"(\w+(?:\s*\([^)]+\))?)", col_type)
            base_type = type_match.group(1) if type_match else col_type.split()[0]
            if old_col == new_col:
                # No rename needed, just type change
                return f"ALTER TABLE {table} ALTER COLUMN {new_col} TYPE {base_type}"
            else:
                # Both rename and type change
                return f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}; ALTER TABLE {table} ALTER COLUMN {new_col} TYPE {base_type}"

        sql = re.sub(
            r"ALTER\s+TABLE\s+([`\"]?\w+[`\"]?)\s+CHANGE\s+(?:COLUMN\s+)?([`\"]?\w+[`\"]?)\s+([`\"]?\w+[`\"]?)\s+(.+?)(?=\s*[,;]|$)",
            convert_change_column,
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

        # Remove table options (ENGINE, CHARSET, COLLATE, COMMENT, etc.)
        # Must handle COMMENT='...' which contains parentheses
        # Order matters: remove COMMENT first to avoid regex conflicts
        sql = re.sub(r"\s*COMMENT\s*=\s*'[^']*'", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*DEFAULT\s+CHARSET\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*COLLATE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*ROW_FORMAT\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*KEY_BLOCK_SIZE\s*=\s*\d+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*PACK_KEYS\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        # Remove ENGINE clause (after other options are gone)
        sql = re.sub(r"\)\s*ENGINE\s*=\s*\w+\s*;", ");", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*ENGINE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove ASC/DESC from index columns
        sql = re.sub(r"(`\w+`)\s+(ASC|DESC)(?=\s*[,)])", r"\1", sql, flags=re.IGNORECASE)

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

        # Lowercase double-quoted identifiers (sqlglot produces these)
        # This ensures column names like "CreatureId" become "creatureid"
        sql = re.sub(r'"([^"]+)"', lambda m: m.group(1).lower(), sql)

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

    def _convert_dml(self, sql: str, ctx: ConversionContext) -> str:
        """Convert DML using tokenizer and escape handling."""
        # Note: User variable expansion is done in PreprocessingStage before splitting

        # Remove backticks
        sql = remove_backticks(sql)

        # Convert MySQL double-quoted strings to PostgreSQL single-quoted strings
        # MySQL allows both 'string' and "string" for string literals
        # PostgreSQL only uses single quotes for strings (double quotes are identifiers)
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

        # Convert escape sequences (inline, placeholder technique)
        # Protect escaped backslashes with placeholder
        placeholder = "\x00ESCAPED_BACKSLASH\x00"
        sql = sql.replace("\\\\", placeholder)
        # Convert escaped quotes: MySQL \' -> PostgreSQL ''
        sql = sql.replace("\\'", "''")
        # Restore escaped backslashes
        sql = sql.replace(placeholder, "\\\\")

        # Convert hex literals
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
