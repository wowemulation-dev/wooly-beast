#!/usr/bin/env python3
"""
MySQL to PostgreSQL Schema Converter for TrinityCore

Uses a hybrid approach:
- sqlglot for DDL (CREATE, ALTER, DROP) - proper parsing preserves strings
- Fast regex for DML (INSERT, UPDATE, DELETE) - no string corruption risk
"""

import argparse
import re
import sys
import traceback
from pathlib import Path

import sqlglot
from sqlglot.errors import ParseError


class MySQLToPostgreSQLConverter:
    """
    Converts MySQL SQL to PostgreSQL format.

    Hybrid approach for performance and correctness:
    - DDL statements use sqlglot for proper SQL parsing
    - DML statements use fast regex (strings are safe in VALUES)
    """

    # Statement types that should use sqlglot (schema definitions)
    DDL_KEYWORDS = frozenset(["CREATE", "ALTER", "DROP", "TRUNCATE"])

    # Statement types that use fast regex (data manipulation)
    DML_KEYWORDS = frozenset(["INSERT", "UPDATE", "DELETE", "REPLACE"])

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.stats = {
            "ddl_statements": 0,
            "dml_statements": 0,
            "other_statements": 0,
            "sqlglot_errors": 0,
        }

    def log_debug(self, message: str) -> None:
        """Log debug message if debug mode is enabled."""
        if self.debug:
            print(f"DEBUG: {message}", file=sys.stderr)

    def preprocess_dump(self, content: str) -> str:
        """
        Remove mysqldump artifacts before processing.

        These artifacts confuse both sqlglot and aren't needed for PostgreSQL.
        """
        self.log_debug("Removing mysqldump artifacts...")

        # Remove MySQL conditional comments /*!xxxxx ... */
        content = re.sub(r"/\*!\d+[^*]*\*/", "", content)

        # Remove LOCK/UNLOCK TABLES
        # Must use word boundary \b to avoid matching "LOCK TABLES" inside "UNLOCK TABLES"
        content = re.sub(r"UNLOCK TABLES;\s*\n?", "", content, flags=re.IGNORECASE)
        content = re.sub(
            r"\bLOCK TABLES\b.*?;\s*\n?", "", content, flags=re.IGNORECASE | re.DOTALL
        )

        # Remove SET statements for MySQL session variables
        content = re.sub(
            r"^SET\s+(?:@\w+\s*=|NAMES|character_set|collation).*?;\s*\n?",
            "",
            content,
            flags=re.MULTILINE | re.IGNORECASE,
        )

        # Remove MySQL dump headers
        content = re.sub(r"-- MySQL dump.*?\n", "", content)
        content = re.sub(r"-- Host:.*?\n", "", content)
        content = re.sub(r"-- Server version.*?\n", "", content)
        content = re.sub(r"-- Dump completed.*?\n", "", content)

        return content

    def preprocess_ddl(self, sql: str) -> str:
        """
        Preprocess DDL statement to fix constructs sqlglot can't handle.
        """
        # Convert AUTO_INCREMENT to SERIAL (must happen before sqlglot)
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

        # Remove unsigned from float/double/decimal (sqlglot can't parse)
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
        sql = re.sub(
            r"\s*ENGINE\s*=\s*\w+(?:\s+[^,;)]*)?", "", sql, flags=re.IGNORECASE
        )

        # Remove DEFAULT CHARSET
        sql = re.sub(
            r"\s*DEFAULT\s+CHARSET\s*=\s*\w+(?:\s+[^,;)]*)?",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove COLLATE =
        sql = re.sub(
            r"\s*COLLATE\s*=\s*\w+(?:\s+[^,;)]*)?", "", sql, flags=re.IGNORECASE
        )

        # Remove ROW_FORMAT, KEY_BLOCK_SIZE, PACK_KEYS
        sql = re.sub(r"\s*ROW_FORMAT\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*KEY_BLOCK_SIZE\s*=\s*\d+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*PACK_KEYS\s*=\s*\w+", "", sql, flags=re.IGNORECASE)

        # Remove COMMENT = 'xxx' (table-level)
        sql = re.sub(r"\s*COMMENT\s*=\s*'[^']*'", "", sql, flags=re.IGNORECASE)

        # Remove ASC/DESC from index column definitions (MySQL 8.0+ syntax sqlglot can't parse)
        # Matches: `column` DESC or `column` ASC followed by comma or closing paren
        sql = re.sub(r"(`\w+`)\s+(ASC|DESC)(?=\s*[,)])", r"\1", sql, flags=re.IGNORECASE)

        return sql

    def postprocess_ddl(self, sql: str) -> str:
        """
        Post-process sqlglot output to fix remaining MySQL-isms.
        """
        # Remove backticks that sqlglot preserves
        sql = re.sub(r"`([^`]+)`", r"\1", sql)

        # Fix sqlglot's unsigned integer type outputs
        sql = re.sub(r"\bUTINYINT\b", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUSMALLINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUMEDIUMINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUINT\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUINT\b", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUBIGINT\(\d+\)", "BIGINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUBIGINT\b", "BIGINT", sql, flags=re.IGNORECASE)

        # Fix INT with size specifier - PostgreSQL doesn't use them
        sql = re.sub(r"\bINT\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINT\b", "INTEGER", sql, flags=re.IGNORECASE)

        # Convert MySQL ENUM to TEXT (PostgreSQL requires CREATE TYPE for enums)
        sql = re.sub(r"\bENUM\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)

        # Convert MySQL SET to TEXT
        sql = re.sub(r"\bSET\s*\([^)]+\)", "TEXT", sql, flags=re.IGNORECASE)

        # Fix BYTEA - PostgreSQL doesn't allow size modifier
        sql = re.sub(r"\bBYTEA\s*\(\d+\)", "BYTEA", sql, flags=re.IGNORECASE)

        # Fix SMALLINT/TINYINT with size specifier
        sql = re.sub(r"\bSMALLINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTINYINT\s*\(\d+\)", "SMALLINT", sql, flags=re.IGNORECASE)

        # Fix UNIQUE constraint syntax: UNIQUE "name" (cols) -> UNIQUE (cols)
        # We drop the constraint name to avoid conflicts
        # (PostgreSQL constraint names are schema-scoped)
        sql = re.sub(
            r'\bUNIQUE\s+"[^"]+"\s*\(',
            r'UNIQUE (',
            sql,
            flags=re.IGNORECASE,
        )
        # Also handle CONSTRAINT "name" UNIQUE -> UNIQUE (anonymous)
        sql = re.sub(
            r'\bCONSTRAINT\s+"[^"]+"\s+UNIQUE\s*\(',
            r'UNIQUE (',
            sql,
            flags=re.IGNORECASE,
        )

        # Remove INDEX definitions from CREATE TABLE (PostgreSQL doesn't support inline INDEX)
        # Pattern: , INDEX "name" (columns...)
        sql = re.sub(
            r',\s*INDEX\s+"[^"]+"\s*\([^)]+\)',
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Also handle KEY (MySQL synonym for INDEX)
        sql = re.sub(
            r',\s*KEY\s+"[^"]+"\s*\([^)]+\)',
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove FOREIGN KEY constraints to avoid table ordering issues
        # TrinityCore handles referential integrity at application level
        sql = re.sub(
            r',\s*CONSTRAINT\s+"[^"]+"\s+FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+"[^"]+"\s*\([^)]+\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION))*',
            "",
            sql,
            flags=re.IGNORECASE,
        )

        # Remove USING BTREE/HASH from column definitions (sqlglot misplacement)
        sql = re.sub(r"\s+USING\s+(?:BTREE|HASH)", "", sql, flags=re.IGNORECASE)

        # Remove COLLATE from column definitions (PostgreSQL uses different collation names)
        sql = re.sub(r"\s+COLLATE\s+\w+", "", sql, flags=re.IGNORECASE)

        # Remove FULLTEXT INDEX definitions (PostgreSQL uses GIN indexes, created separately)
        sql = re.sub(
            r",\s*FULLTEXT\s+INDEX\s+\"[^\"]+\"\s*\([^)]+\)",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    def convert_ddl_with_sqlglot(self, sql: str) -> str:
        """
        Convert DDL statement using sqlglot for proper parsing.

        This preserves string literals correctly.
        """
        sql = self.preprocess_ddl(sql)

        try:
            results = sqlglot.transpile(sql, read="mysql", write="postgres")
            if results:
                result = results[0]
                return self.postprocess_ddl(result)
            return sql
        except ParseError as e:
            self.log_debug(f"sqlglot error on DDL: {e}")
            self.stats["sqlglot_errors"] += 1
            # Fall back to regex for this statement
            return self.convert_dml_with_regex(sql)

    def convert_dml_with_regex(self, sql: str) -> str:
        """
        Convert DML statement using fast regex.

        Safe for data statements since type keywords don't appear in VALUES.
        """
        # Remove backticks
        sql = re.sub(r"`([^`]+)`", r"\1", sql)

        # Handle MySQL escape sequences properly
        # Order matters: handle \\ first to avoid corrupting \\' sequences
        #
        # MySQL escape sequences:
        #   \\ = literal backslash
        #   \' = literal single quote
        #   \" = literal double quote
        #
        # Problem: naive \\' -> '' replacement matches the second \ from \\
        # and the ', breaking the escaped backslash.
        #
        # Solution: Use placeholder to protect \\ sequences during conversion

        # Protect escaped backslashes with placeholder
        placeholder = "\x00ESCAPED_BACKSLASH\x00"
        sql = sql.replace("\\\\", placeholder)

        # Now convert escaped quotes (safe because \\ is protected)
        # MySQL: 'Zul\'Farrak' -> PostgreSQL: 'Zul''Farrak'
        sql = sql.replace("\\'", "''")

        # Remove escaped double quotes (MySQL: \" -> PostgreSQL: ")
        sql = sql.replace('\\"', '"')

        # Restore escaped backslashes
        sql = sql.replace(placeholder, "\\\\")

        # Handle \n, \r, \t by converting to PostgreSQL E'' strings not needed
        # since we're converting literal \n in strings, not actual newlines

        # Convert MySQL hex literals to PostgreSQL bytea format
        # Using decode() function instead of '\x...' escape format to avoid
        # psql meta-command interpretation when lines wrap
        # 0x1234ABCD -> decode('1234ABCD', 'hex')
        sql = re.sub(r"\b0x([0-9A-Fa-f]+)\b", r"decode('\1', 'hex')", sql)

        # Convert MySQL unsigned max values to -1 for PostgreSQL signed types
        # BIGINT UNSIGNED max (18446744073709551615) -> -1 (commonly used as "all" bitmask)
        sql = sql.replace("18446744073709551615", "-1")
        # INT UNSIGNED max (4294967295) -> -1
        sql = sql.replace("4294967295", "-1")

        # Convert unsigned integers that overflow signed types to their signed equivalents
        def convert_unsigned_to_signed(match: re.Match[str]) -> str:
            val = int(match.group(0))
            # Convert unsigned 64-bit values > BIGINT_MAX to signed
            if val > 9223372036854775807:
                return str(val - 18446744073709551616)
            # Convert unsigned 32-bit values > INT_MAX to signed
            if val > 2147483647:
                return str(val - 4294967296)
            return match.group(0)

        # Match large numbers (10+ digits) that might overflow
        sql = re.sub(r"\b\d{10,}\b", convert_unsigned_to_signed, sql)

        # REPLACE INTO -> INSERT INTO (simplified)
        sql = re.sub(r"\bREPLACE\s+INTO\b", "INSERT INTO", sql, flags=re.IGNORECASE)

        # Remove LIMIT from UPDATE/DELETE (MySQL-specific)
        sql = re.sub(
            r"(\bUPDATE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE
        )
        sql = re.sub(
            r"(\bDELETE\s+.+?)\s+LIMIT\s+\d+", r"\1", sql, flags=re.IGNORECASE
        )

        # ON DUPLICATE KEY UPDATE -> ON CONFLICT DO UPDATE SET (simplified)
        sql = re.sub(
            r"ON\s+DUPLICATE\s+KEY\s+UPDATE\s+(.+?)$",
            r"ON CONFLICT DO UPDATE SET \1",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    def convert_other_with_regex(self, sql: str) -> str:
        """
        Convert other statements (SELECT, etc.) using regex.
        """
        # Remove backticks
        sql = re.sub(r"`([^`]+)`", r"\1", sql)

        # Basic function conversions
        sql = re.sub(r"\bUNIX_TIMESTAMP\(\)", "EXTRACT(EPOCH FROM NOW())", sql)
        sql = re.sub(
            r"\bFROM_UNIXTIME\s*\(\s*([^)]+)\s*\)",
            r"TO_TIMESTAMP(\1)",
            sql,
            flags=re.IGNORECASE,
        )

        # Fix update paths (mysql -> postgresql)
        # Support both 3.3.5 and cata_classic version paths
        sql = re.sub(
            r"'\$/sql/updates/([^/]+)/(3\.3\.5|cata_classic)/mysql'",
            r"'$/sql/updates/\1/\2/postgresql'",
            sql,
        )

        return sql

    def get_statement_type(self, sql: str) -> str:
        """
        Determine the type of SQL statement.

        Returns: 'DDL', 'DML', or 'OTHER'
        """
        # Get first word (skip comments and whitespace)
        cleaned = re.sub(r"^\s*--[^\n]*\n", "", sql)  # Remove line comments
        cleaned = cleaned.strip()

        match = re.match(r"^(\w+)", cleaned, re.IGNORECASE)
        if match:
            keyword = match.group(1).upper()
            if keyword in self.DDL_KEYWORDS:
                return "DDL"
            if keyword in self.DML_KEYWORDS:
                return "DML"
        return "OTHER"

    def is_comment_only(self, sql: str) -> bool:
        """
        Check if a statement contains only comments and whitespace.
        """
        lines = sql.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):
                return False
        return True

    def convert_statement(self, sql: str) -> str:
        """
        Convert a single SQL statement using the appropriate method.
        """
        sql = sql.strip()
        if not sql:
            return sql

        # Skip comment-only blocks - they cause --;  syntax errors
        if self.is_comment_only(sql):
            return ""

        stmt_type = self.get_statement_type(sql)

        if stmt_type == "DDL":
            self.stats["ddl_statements"] += 1
            return self.convert_ddl_with_sqlglot(sql)
        elif stmt_type == "DML":
            self.stats["dml_statements"] += 1
            return self.convert_dml_with_regex(sql)
        else:
            self.stats["other_statements"] += 1
            return self.convert_other_with_regex(sql)

    def split_statements(self, content: str) -> list[str]:
        """
        Split SQL content into individual statements.

        Handles quoted strings properly to avoid splitting inside strings.
        """
        statements = []
        current = []
        in_string = False
        string_char = None
        i = 0

        while i < len(content):
            char = content[i]

            # Handle escape sequences
            if in_string and char == "\\" and i + 1 < len(content):
                current.append(char)
                current.append(content[i + 1])
                i += 2
                continue

            # Handle string literals
            if char in ("'", '"'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                current.append(char)
            elif char == ";" and not in_string:
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(char)

            i += 1

        # Handle last statement without semicolon
        stmt = "".join(current).strip()
        if stmt:
            statements.append(stmt)

        return statements

    def convert(self, content: str) -> str:
        """
        Convert MySQL SQL content to PostgreSQL.
        """
        # Step 1: Remove mysqldump artifacts
        content = self.preprocess_dump(content)

        # Step 2: Split and convert statements
        statements = self.split_statements(content)
        self.log_debug(f"Processing {len(statements)} statements...")

        converted = []
        for i, stmt in enumerate(statements):
            if i > 0 and i % 10000 == 0:
                self.log_debug(f"Processed {i} statements...")

            converted_stmt = self.convert_statement(stmt)
            if converted_stmt.strip():
                converted.append(converted_stmt)

        # Join with semicolons
        result = ";\n".join(converted)
        if result and not result.endswith(";"):
            result += ";"

        # Final cleanup: remove any remaining backticks
        result = re.sub(r"`([^`]+)`", r"\1", result)

        # Clean up whitespace
        result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)

        return result

    def convert_file(
        self, input_file: Path, output_file: Path | None = None
    ) -> str:
        """
        Convert a MySQL SQL file to PostgreSQL.
        """
        self.log_debug(f"Converting file: {input_file}")

        with input_file.open(encoding="utf-8") as f:
            content = f.read()

        self.log_debug(f"Read {len(content)} bytes")

        # Reset stats
        self.stats = {
            "ddl_statements": 0,
            "dml_statements": 0,
            "other_statements": 0,
            "sqlglot_errors": 0,
        }

        result = self.convert(content)

        # Add header
        header = """\
-- PostgreSQL database schema converted from MySQL
-- Generated by TrinityCore MySQL to PostgreSQL converter
-- Hybrid approach: sqlglot for DDL, regex for DML

"""
        result = header + result

        if output_file:
            with output_file.open("w", encoding="utf-8") as f:
                f.write(result)
            self.log_debug(f"Output written to: {output_file}")

        self.log_debug(f"Stats: {self.stats}")

        return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert MySQL schema to PostgreSQL for TrinityCore"
    )
    parser.add_argument("input_file", help="Input MySQL SQL file")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output PostgreSQL SQL file (optional, defaults to stdout)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file) if args.output_file else None

    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    converter = MySQLToPostgreSQLConverter(debug=args.debug)

    try:
        result = converter.convert_file(input_path, output_path)

        if not output_path:
            print(result)

        if args.debug:
            print(f"\nConversion stats: {converter.stats}", file=sys.stderr)

    except Exception as e:
        print(f"Error converting file: {e}", file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
