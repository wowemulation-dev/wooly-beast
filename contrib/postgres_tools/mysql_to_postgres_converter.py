#!/usr/bin/env python3
"""
MySQL to PostgreSQL Schema Converter for TrinityCore
"""

import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional

class MySQLToPostgreSQLConverter:
    def __init__(self, debug=False, use_copy_format=False):
        self.debug = debug
        self.use_copy_format = use_copy_format

        # Tables that commonly need CASCADE on DROP due to foreign keys
        self.cascade_tables = {
            'account', 'characters', 'guild', 'account_data', 'character_account_data',
            'item_instance', 'mail', 'petition', 'rbac_permissions', 'creature',
            'gameobject', 'quest_template'
        }

        # Track tables with ON UPDATE CURRENT_TIMESTAMP columns for trigger generation
        self.tables_needing_update_triggers = []

        # Track ENUM definitions for CHECK constraint generation
        self.enum_definitions = {}

        # Track converted views to be appended at the end
        self._converted_views = []

    def log_debug(self, message: str):
        """Log debug message if debug mode is enabled"""
        if self.debug:
            print(f"DEBUG: {message}", file=sys.stderr)

    def convert_invalid_dates(self, content: str) -> str:
        """Convert MySQL invalid dates to valid PostgreSQL dates.

        MySQL allows '0000-00-00' and '0000-00-00 00:00:00' as date/datetime values,
        but PostgreSQL doesn't accept these. Convert them to Unix epoch (1970-01-01).

        Based on mysql2postgres gem approach.
        """
        self.log_debug("Converting invalid MySQL dates...")

        # Convert '0000-00-00 00:00:00' datetime values
        datetime_zero_count = len(re.findall(r"'0000-00-00 00:00:00'", content))
        content = re.sub(r"'0000-00-00 00:00:00'", "'1970-01-01 00:00:00'", content)
        if datetime_zero_count > 0:
            self.log_debug(f"Converted {datetime_zero_count} zero datetime values to 1970-01-01 00:00:00")

        # Convert '0000-00-00' date values
        date_zero_count = len(re.findall(r"'0000-00-00'", content))
        content = re.sub(r"'0000-00-00'", "'1970-01-01'", content)
        if date_zero_count > 0:
            self.log_debug(f"Converted {date_zero_count} zero date values to 1970-01-01")

        return content

    def convert_enum_to_check_constraint(self, match) -> str:
        """Convert MySQL ENUM type to VARCHAR with CHECK constraint.

        MySQL: column_name ENUM('val1', 'val2', 'val3')
        PostgreSQL: column_name VARCHAR(max_length) CHECK (column_name IN ('val1', 'val2', 'val3'))

        Based on mysql2postgres gem approach which preserves data integrity.
        """
        # Parse the match - expects (column_name, enum_values_with_parens, rest_of_line)
        column_name = match.group(1)
        enum_values = match.group(2)  # e.g., 'val1', 'val2', 'val3'

        # Extract individual enum values to find max length
        values = re.findall(r"'([^']*)'", enum_values)
        max_length = max(len(v) for v in values) if values else 255

        # Build the CHECK constraint
        # Use the enum values exactly as they appear
        check_values = ', '.join(f"'{v}'" for v in values)

        # PostgreSQL syntax: varchar(max_length) CHECK (column IN (values))
        result = f"{column_name} varchar({max_length}) CHECK ({column_name} IN ({check_values}))"

        self.log_debug(f"Converted ENUM column {column_name} with {len(values)} values")
        return result

    def generate_update_timestamp_triggers(self) -> str:
        """Generate PostgreSQL trigger functions for ON UPDATE CURRENT_TIMESTAMP columns.

        MySQL's ON UPDATE CURRENT_TIMESTAMP is not natively supported in PostgreSQL.
        We need to create a trigger function and apply it to each table/column.
        """
        if not self.tables_needing_update_triggers:
            return ""

        self.log_debug(f"Generating triggers for {len(self.tables_needing_update_triggers)} tables")

        trigger_sql = [
            "",
            "-- Trigger function for ON UPDATE CURRENT_TIMESTAMP behavior",
            "CREATE OR REPLACE FUNCTION update_timestamp_column()",
            "RETURNS TRIGGER AS $$",
            "BEGIN",
            "    NEW.%s = CURRENT_TIMESTAMP;",
            "    RETURN NEW;",
            "END;",
            "$$ LANGUAGE plpgsql;",
            ""
        ]

        # Generate trigger for each table/column pair
        for table_name, column_name in self.tables_needing_update_triggers:
            trigger_name = f"update_{table_name}_{column_name}_timestamp"
            trigger_sql.extend([
                f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};",
                f"CREATE TRIGGER {trigger_name}",
                f"    BEFORE UPDATE ON {table_name}",
                f"    FOR EACH ROW",
                f"    EXECUTE FUNCTION update_timestamp_column();",
                ""
            ])

        return '\n'.join(trigger_sql)

    def extract_and_convert_views(self, content: str) -> tuple:
        """Extract VIEW definitions from MySQL conditional comments and convert to PostgreSQL.

        Returns:
            tuple: (content_without_views, list_of_converted_views)
        """
        converted_views = []

        # Pattern to match VIEW definitions in mysqldump conditional comments
        # Format: /*!50001 VIEW `view_name` AS select ... */;
        view_pattern = re.compile(
            r"/\*!50001\s+VIEW\s+`(\w+)`\s+AS\s+(.*?)\s*\*/;",
            re.IGNORECASE | re.DOTALL
        )

        for match in view_pattern.finditer(content):
            view_name = match.group(1)
            view_definition = match.group(2).strip()

            # Convert MySQL view definition to PostgreSQL
            pg_view = self._convert_view_to_postgres(view_name, view_definition)
            if pg_view:
                converted_views.append(pg_view)
                self.log_debug(f"Converted view: {view_name}")

        # Remove the "Temporary view structure" blocks entirely
        # These contain DROP TABLE, DROP VIEW, and placeholder CREATE VIEW statements
        # The actual views are converted from the Final view structure section
        # Match from the comment header to the final SET statement of each block
        # Format: -- Temporary view structure... DROP TABLE... DROP VIEW... SET... CREATE VIEW... SET
        content = re.sub(
            r"--\n--\s*Temporary view structure for view\s+`\w+`\s*\n--\n.*?SET character_set_client = @saved_cs_client;",
            '', content, flags=re.IGNORECASE | re.DOTALL
        )

        # Remove the "Final view structure" blocks including all SET statements
        content = re.sub(
            r"--\s*Final view structure for view.*?/\*!50001\s+SET\s+collation_connection.*?\*/;",
            '', content, flags=re.IGNORECASE | re.DOTALL
        )

        # Remove DROP VIEW statements in conditional comments
        content = re.sub(
            r"/\*!\d+\s+DROP\s+VIEW\s+IF\s+EXISTS\s+`?\w+`?\s*\*/;",
            '', content, flags=re.IGNORECASE
        )

        return content, converted_views

    def _convert_view_to_postgres(self, view_name: str, definition: str) -> str:
        """Convert a single MySQL view definition to PostgreSQL syntax."""
        # Remove backticks
        definition = definition.replace('`', '')

        # Convert MySQL functions to PostgreSQL
        # from_unixtime() -> TO_TIMESTAMP()
        definition = re.sub(
            r'\bfrom_unixtime\s*\(([^)]+)\)',
            r'TO_TIMESTAMP(\1)',
            definition, flags=re.IGNORECASE
        )

        # ifnull() -> COALESCE()
        definition = re.sub(
            r'\bifnull\s*\(',
            'COALESCE(',
            definition, flags=re.IGNORECASE
        )

        # count(0) -> count(*)
        definition = re.sub(
            r'\bcount\s*\(\s*0\s*\)',
            'count(*)',
            definition, flags=re.IGNORECASE
        )

        # Quote column aliases that contain spaces
        # Pattern: AS word word -> AS "word word"
        # IMPORTANT: Don't consume SQL keywords (FROM, WHERE, ORDER, etc.) as part of the alias
        # The previous regex would match "Comment from conditions" as a single alias
        # This version explicitly stops at SQL keywords
        sql_keywords = r'(?:from|where|order|group|having|limit|union|join|left|right|inner|outer|on|and|or)'
        definition = re.sub(
            rf'\bAS\s+([A-Za-z_][A-Za-z0-9_]*(?:\s+(?!{sql_keywords}\b)[A-Za-z_][A-Za-z0-9_]*)+)(?=\s*,|\s*\b{sql_keywords}\b|\s*$)',
            lambda m: f'AS "{m.group(1)}"',
            definition, flags=re.IGNORECASE
        )

        # PostgreSQL requires consistent types in CASE expressions
        # MySQL views often have CASE that returns string labels with else returning the original integer
        # Pattern: else table.column end) AS Column -> else table.column::text end) AS Column
        # This casts the else clause to text for type consistency
        # Use \w+ for word chars (includes underscores) and [A-Za-z0-9_]+ for columns with mixed case
        definition = re.sub(
            r'\belse\s+([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s+end\)',
            r'else \1::text end)',
            definition, flags=re.IGNORECASE
        )

        # Remove any remaining MySQL-specific syntax
        # Clean up extra whitespace
        definition = re.sub(r'\s+', ' ', definition).strip()

        return f"CREATE OR REPLACE VIEW {view_name} AS {definition};"

    def preprocess_mysqldump(self, content: str) -> str:
        """Remove MySQL-specific dump artifacts before conversion"""
        self.log_debug("Preprocessing mysqldump content...")

        # FIRST: Extract and convert views before removing conditional comments
        # Only extract if we haven't already (makes preprocessing idempotent)
        if not self._converted_views:
            content, self._converted_views = self.extract_and_convert_views(content)
            if self._converted_views:
                self.log_debug(f"Extracted and converted {len(self._converted_views)} views")

        # Remove MySQL conditional comments /*!xxxxx ... */
        # These contain MySQL-specific settings like character set, time zone, etc.
        original_len = len(content)
        content = re.sub(r'/\*!\d+[^*]*\*/', '', content)
        if len(content) < original_len:
            self.log_debug(f"Removed MySQL conditional comments ({original_len - len(content)} chars)")

        # Remove UNLOCK TABLES first to avoid LOCK matching inside UNLOCK
        unlock_count = len(re.findall(r'\bUNLOCK\s+TABLES\b', content, flags=re.IGNORECASE))
        content = re.sub(r'\bUNLOCK\s+TABLES\s*;?\s*\n?', '', content, flags=re.IGNORECASE)
        if unlock_count > 0:
            self.log_debug(f"Removed {unlock_count} UNLOCK TABLES statements")

        # Remove LOCK TABLES ... WRITE; statements
        lock_count = len(re.findall(r'\bLOCK\s+TABLES\b', content, flags=re.IGNORECASE))
        content = re.sub(r'\bLOCK\s+TABLES\s+.+?;\s*\n?', '', content, flags=re.IGNORECASE | re.DOTALL)
        if lock_count > 0:
            self.log_debug(f"Removed {lock_count} LOCK TABLES statements")

        # Remove SET statements for MySQL session variables
        set_count = len(re.findall(r'^SET\s+(?:@\w+\s*=|NAMES|character_set|collation).*?;', content, flags=re.MULTILINE | re.IGNORECASE))
        content = re.sub(r'^SET\s+(?:@\w+\s*=|NAMES|character_set|collation).*?;\s*\n?', '', content, flags=re.MULTILINE | re.IGNORECASE)
        if set_count > 0:
            self.log_debug(f"Removed {set_count} SET statements")

        return content

    def extract_mysql_variables(self, content: str) -> Dict[str, str]:
        """Extract MySQL variable declarations (SET @VAR = value) - only real variables, not comments"""
        variables = {}

        # Pattern to match SET @VARIABLE = value or SET @VARIABLE := value
        # Only match lines that are actual SET statements, not comments
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Skip comments and MySQL directives
            if line.startswith('--') or line.startswith('/*') or line.startswith('*/') or '/*!' in line:
                continue

            # Look for actual SET statements
            match = re.match(r'SET\s+@(\w+)\s*:?=\s*([^;]+);', line)
            if match:
                var_name, value = match.groups()
                value = value.strip()
                variables[var_name] = value
                self.log_debug(f"Found variable: @{var_name} = {value}")

        return variables

    def convert_mysql_variables_to_do_block(self, content: str, variables: Dict[str, str]) -> str:
        """Convert content with MySQL variables to PostgreSQL DO block"""
        if not variables:
            return content

        # Apply SQL conversions to content BEFORE creating DO block
        content = self.convert_sql_content(content)

        # Build the DO block
        do_block = "DO $$\nDECLARE\n"

        # Add variable declarations
        for var_name, value in variables.items():
            # Determine type based on value
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                var_type = "INTEGER"
            elif re.match(r'^\d+\.\d+$', value):
                var_type = "DECIMAL"
            elif value.startswith("'") and value.endswith("'"):
                var_type = "TEXT"
            else:
                # Complex expression, try to infer
                if '@' in value:  # References another variable
                    var_type = "INTEGER"  # Most common case
                else:
                    var_type = "TEXT"

            do_block += f"    {var_name} {var_type} := {value};\n"

        do_block += "BEGIN\n"

        # Remove SET statements from content (after conversions are applied)
        for var_name in variables:
            content = re.sub(rf'SET\s+@{var_name}\s*:?=\s*[^;]+;\s*\n?', '', content)

        # Replace @variable with just variable name in the content
        for var_name in variables:
            content = re.sub(rf'@{var_name}\b', var_name, content)

        # Indent the SQL statements
        lines = content.strip().split('\n')
        indented_statements = []
        for line in lines:
            if line.strip():
                if not line.strip().startswith('--'):  # Preserve comments
                    indented_statements.append('    ' + line)
                else:
                    indented_statements.append(line)
            else:
                indented_statements.append(line)

        do_block += '\n'.join(indented_statements)
        if not do_block.rstrip().endswith(';'):
            do_block += ';'
        do_block += "\nEND $$;\n"

        return do_block

    def convert_sql_content(self, content: str) -> str:
        """Convert SQL content by applying all transformations"""

        # First, preprocess mysqldump content to remove artifacts
        content = self.preprocess_mysqldump(content)

        # Remove MySQL-specific directives and conditional comments
        self.log_debug("Removing MySQL-specific directives...")
        content = re.sub(r'/\*!\d+.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'^\s*/\*!.*?\*/;?\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*;\s*$', '', content, flags=re.MULTILINE)

        # Remove LOCK/UNLOCK TABLES - UNLOCK must be processed BEFORE LOCK to avoid
        # "LOCK TABLES" matching inside "UNLOCK TABLES" and leaving "UN" behind
        content = re.sub(r'\bUNLOCK\s+TABLES\s*;?\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\bLOCK\s+TABLES\s+.+?;\s*\n?', '', content, flags=re.IGNORECASE | re.DOTALL)

        # Remove MySQL dump headers and footers
        content = re.sub(r'-- MySQL dump.*?\n', '', content)
        content = re.sub(r'-- Host:.*?\n', '', content)
        content = re.sub(r'-- Server version.*?\n', '', content)
        content = re.sub(r'-- Dump completed.*?\n', '', content)

        # Basic conversions that can be done globally
        self.log_debug("Applying basic conversions...")

        # Enhanced backtick removal - proper SQL grammar handling
        # MySQL uses backticks for identifier quoting: `table_name`, `column_name`
        # PostgreSQL uses double quotes for the same purpose (or unquoted for simple names)
        self.log_debug("Removing MySQL backticks...")

        backtick_count_before = len(re.findall(r'`', content))

        # Step 1: Remove matching backtick pairs around identifiers
        # This handles properly quoted identifiers like `table_name`
        content = re.sub(r'`([^`]+)`', r'\1', content)

        # Step 2: Clean up any orphaned backticks that may remain
        # This can happen if earlier processing steps (like conditional comment removal)
        # partially consume backtick-quoted identifiers
        backtick_count_after = len(re.findall(r'`', content))
        if backtick_count_after > 0:
            self.log_debug(f"Found {backtick_count_after} orphaned backticks, removing...")
            content = content.replace('`', '')

        pairs_removed = (backtick_count_before - backtick_count_after) // 2
        if backtick_count_before > 0:
            self.log_debug(f"Removed {pairs_removed} backtick pairs, {backtick_count_after} orphaned")

        # Convert MySQL functions - comprehensive handling
        self.log_debug("Converting MySQL functions...")

        # UNIX_TIMESTAMP() variations
        content = re.sub(r'UNIX_TIMESTAMP\(\)', 'extract(epoch from now())', content)

        # FROM_UNIXTIME() function - convert to to_timestamp()
        content = re.sub(r'FROM_UNIXTIME\s*\(\s*([^)]+)\s*\)', r'to_timestamp(\1)', content, flags=re.IGNORECASE)

        # DATEDIFF() function - convert to date arithmetic
        content = re.sub(r'DATEDIFF\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', r'(\1::date - \2::date)', content, flags=re.IGNORECASE)

        # NOW() function
        content = re.sub(r'NOW\(\)', 'NOW()', content)

        # CONCAT() function - convert to || operator
        def convert_concat(match):
            args = match.group(1)
            # Split arguments, handling nested functions and quoted strings
            arg_parts = []
            paren_depth = 0
            quote_char = None
            current_arg = ""

            for char in args:
                if quote_char:
                    current_arg += char
                    if char == quote_char and (len(current_arg) == 0 or current_arg[-2] != '\\'):
                        quote_char = None
                elif char in ("'", '"'):
                    quote_char = char
                    current_arg += char
                elif char == '(':
                    paren_depth += 1
                    current_arg += char
                elif char == ')':
                    paren_depth -= 1
                    current_arg += char
                elif char == ',' and paren_depth == 0:
                    arg_parts.append(current_arg.strip())
                    current_arg = ""
                else:
                    current_arg += char

            if current_arg.strip():
                arg_parts.append(current_arg.strip())

            if len(arg_parts) > 1:
                return ' || '.join(arg_parts)
            elif len(arg_parts) == 1:
                return arg_parts[0]
            else:
                return 'NULL'

        content = re.sub(r'CONCAT\s*\(([^)]+)\)', convert_concat, content, flags=re.IGNORECASE)

        # Fix update paths (mysql -> postgresql)
        original_path_count = len(re.findall(r"'\$/sql/updates/([^/]+)/3\.3\.5/mysql'", content))
        content = re.sub(r"'\$/sql/updates/([^/]+)/3\.3\.5/mysql'", r"'$/sql/updates/\1/3.3.5/postgresql'", content)
        if original_path_count > 0:
            self.log_debug(f"Fixed {original_path_count} update path references")

        # Handle CASCADE for DROP TABLE statements
        def add_cascade_if_needed(match):
            table_name = match.group(1)
            if table_name in self.cascade_tables:
                self.log_debug(f"Adding CASCADE to DROP TABLE {table_name}")
                return f'DROP TABLE IF EXISTS {table_name} CASCADE'
            else:
                return f'DROP TABLE IF EXISTS {table_name}'

        content = re.sub(r'DROP TABLE IF EXISTS (\w+)', add_cascade_if_needed, content)

        # IMPORTANT: Convert AUTO_INCREMENT BEFORE type conversion
        # AUTO_INCREMENT patterns need to match MySQL types (int, bigint, etc.)
        self.log_debug("Converting AUTO_INCREMENT to SERIAL...")

        # Handle various AUTO_INCREMENT patterns - must happen before type conversion
        serial_patterns = [
            # Match: column_name int/tinyint/smallint/mediumint [unsigned] AUTO_INCREMENT
            (r'(\w+)\s+(?:tiny|small|medium)?int\s*(?:\(\d+\))?\s+(?:unsigned\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT', r'\1 SERIAL'),
            # Match: column_name bigint [unsigned] AUTO_INCREMENT
            (r'(\w+)\s+bigint\s*(?:\(\d+\))?\s+(?:unsigned\s+)?(?:NOT\s+NULL\s+)?AUTO_INCREMENT', r'\1 BIGSERIAL'),
            # Remove table-level AUTO_INCREMENT = value
            (r'AUTO_INCREMENT\s*=\s*\d+', ''),
        ]

        for pattern, replacement in serial_patterns:
            matches = len(re.findall(pattern, content, flags=re.IGNORECASE))
            if matches > 0:
                self.log_debug(f"Converting {matches} AUTO_INCREMENT patterns")
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

        # Convert MySQL bitwise NOT operator
        # MySQL: value &~ mask (bitwise AND with NOT)
        # PostgreSQL: value & ~mask (requires space before ~)
        self.log_debug("Converting bitwise operators...")
        bitwise_count = len(re.findall(r'&~', content))
        if bitwise_count > 0:
            content = re.sub(r'&~', '& ~', content)
            self.log_debug(f"Converted {bitwise_count} bitwise &~ operators to & ~")

        # Remove column-level CHARACTER SET and COLLATE declarations
        # These appear on individual columns: `column_name text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`
        self.log_debug("Removing column-level CHARACTER SET/COLLATE...")
        charset_count = len(re.findall(r'\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?', content, flags=re.IGNORECASE))
        content = re.sub(r'\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?', '', content, flags=re.IGNORECASE)
        if charset_count > 0:
            self.log_debug(f"Removed {charset_count} column CHARACTER SET/COLLATE declarations")

        # Enhanced data type conversion - ONLY applied to CREATE TABLE statements
        # This prevents corrupting text in INSERT data (e.g., "intentar" -> "integerentar")
        self.log_debug("Converting data types in CREATE TABLE statements...")

        # Use markers for datetime/timestamp/time to prevent re-matching during conversion
        TIMESTAMP_MARKER = '__PG_TIMESTAMP_WTZ__'
        TIME_MARKER = '__PG_TIME_WTZ__'

        # Type conversions for MySQL -> PostgreSQL
        # IMPORTANT: Unsigned types need promotion to avoid range overflow:
        # - tinyint signed: -128 to 127, unsigned: 0 to 255 -> smallint (-32768 to 32767) handles both
        # - smallint signed: -32768 to 32767, unsigned: 0 to 65535 -> integer for unsigned
        # - int signed: -2147483648 to 2147483647, unsigned: 0 to 4294967295 -> bigint for unsigned
        # - bigint unsigned: 0 to 18446744073709551615 -> stays bigint (practical data rarely exceeds signed range)
        # Order matters: unsigned patterns must come before signed patterns
        #
        # CRITICAL: All patterns must use word boundaries on BOTH sides to avoid matching
        # within column names like "intellect" or "InteractionPauseTimer".
        # The pattern (?=\s|,|\)|$) ensures we're at a word boundary or end of type spec.
        # MySQL 8 Numeric Type Syntax Reference:
        # - INTEGER types: TYPE[(M)] [UNSIGNED] [ZEROFILL]
        #   where (M) is optional display width (deprecated in MySQL 8.0.17+)
        # - UNSIGNED can appear with or without display width
        # - Order matters: unsigned patterns must come before signed patterns
        #
        # PostgreSQL type promotions for unsigned values:
        # - tinyint unsigned (0-255) -> smallint (-32768 to 32767)
        # - smallint unsigned (0-65535) -> integer (-2147483648 to 2147483647)
        # - mediumint unsigned (0-16777215) -> integer
        # - int/integer unsigned (0-4294967295) -> bigint (-9223372036854775808 to ...)
        # - bigint unsigned -> bigint (practical data rarely exceeds signed range)
        type_conversions = [
            # ============================================================
            # BOOLEAN TYPES (MySQL aliases for TINYINT(1))
            # ============================================================
            # BOOL and BOOLEAN are synonyms for TINYINT(1) in MySQL
            (r'\bbool(?:ean)?\b', 'boolean'),

            # ============================================================
            # INTEGER TYPES - Unsigned patterns first (require larger types)
            # ============================================================
            # tinyint: signed -128 to 127, unsigned 0-255 -> smallint handles both
            (r'\btinyint(?:\s*\(\d+\))?\s+unsigned\b', 'smallint'),
            (r'\btinyint(?:\s*\(\d+\))?\s+zerofill\b', 'smallint'),  # ZEROFILL implies UNSIGNED
            (r'\btinyint\s*\(\d+\)(?=\s|,|\)|$)', 'smallint'),
            (r'\btinyint\b(?!\s*\()', 'smallint'),

            # smallint: signed -32768 to 32767, unsigned 0-65535 -> integer for unsigned
            (r'\bsmallint(?:\s*\(\d+\))?\s+unsigned\b', 'integer'),
            (r'\bsmallint(?:\s*\(\d+\))?\s+zerofill\b', 'integer'),
            (r'\bsmallint\s*\(\d+\)(?=\s|,|\)|$)', 'smallint'),
            (r'\bsmallint\b(?!\s*\()', 'smallint'),

            # mediumint: signed -8388608 to 8388607, unsigned 0-16777215 -> integer for both
            (r'\bmediumint(?:\s*\(\d+\))?\s+unsigned\b', 'integer'),
            (r'\bmediumint(?:\s*\(\d+\))?\s+zerofill\b', 'integer'),
            (r'\bmediumint\s*\(\d+\)(?=\s|,|\)|$)', 'integer'),
            (r'\bmediumint\b(?!\s*\()', 'integer'),

            # int/integer: signed -2147483648 to 2147483647, unsigned 0-4294967295 -> bigint for unsigned
            # INTEGER is a SQL standard synonym for INT
            # Use negative lookahead to avoid matching "into", "integer", "interval", "internal", etc.
            (r'\binteger(?:\s*\(\d+\))?\s+unsigned\b', 'bigint'),
            (r'\binteger(?:\s*\(\d+\))?\s+zerofill\b', 'bigint'),
            (r'\binteger\s*\(\d+\)(?=\s|,|\)|$)', 'integer'),
            (r'\binteger\b(?!\s*\()', 'integer'),
            # INT patterns - careful lookahead to avoid matching "into", "interval", etc.
            (r'\bint(?!o\b|eger|ernal|erval|eract|ellect)(?:\s*\(\d+\))?\s+unsigned\b', 'bigint'),
            (r'\bint(?!o\b|eger|ernal|erval|eract|ellect)(?:\s*\(\d+\))?\s+zerofill\b', 'bigint'),
            (r'\bint(?!o\b|eger|ernal|erval|eract|ellect)\s*\(\d+\)(?=\s|,|\)|$)', 'integer'),
            (r'\bint\b(?!\s*\()(?!o\b|eger|ernal|erval|eract|ellect)', 'integer'),

            # bigint: signed -9223372036854775808 to 9223372036854775807
            # unsigned stays bigint (practical data rarely exceeds signed range)
            (r'\bbigint(?:\s*\(\d+\))?\s+unsigned\b', 'bigint'),
            (r'\bbigint(?:\s*\(\d+\))?\s+zerofill\b', 'bigint'),
            (r'\bbigint\s*\(\d+\)(?=\s|,|\)|$)', 'bigint'),
            (r'\bbigint\b(?!\s*\()', 'bigint'),

            # ============================================================
            # FLOATING-POINT TYPES
            # ============================================================
            # IMPORTANT: Pattern order matters! Since patterns are applied sequentially,
            # we must process REAL before FLOAT to avoid double-conversion:
            # float -> real (by float pattern) -> double precision (by real pattern)
            #
            # Also, DOUBLE PRECISION must be matched before plain DOUBLE to prevent
            # "double precision" from becoming "double precision precision".

            # DOUBLE PRECISION (exact match) - must come before DOUBLE
            (r'\bdouble\s+precision(?:\s*\(\d+(?:,\s*\d+)?\))?(?:\s+unsigned)?(?:\s+zerofill)?', 'double precision'),
            # REAL: synonym for DOUBLE (unless REAL_AS_FLOAT SQL mode) - must come before FLOAT
            # IMPORTANT: Use negative lookahead (?![a-zA-Z0-9_]) to prevent matching "realm", "realmlist", etc.
            (r'\breal(?![a-zA-Z0-9_])(?:\s*\(\d+(?:,\s*\d+)?\))?(?:\s+unsigned)?(?:\s+zerofill)?', 'double precision'),
            # DOUBLE (but not "double precision" - use negative lookahead)
            # Also prevent matching "doubled", "doublecheck" etc.
            (r'\bdouble(?![a-zA-Z0-9_])(?!\s+precision)(?:\s*\(\d+(?:,\s*\d+)?\))?(?:\s+unsigned)?(?:\s+zerofill)?', 'double precision'),
            # FLOAT: single precision (4 bytes) - comes after REAL to avoid re-conversion
            # FLOAT(p) where p=0-24 is FLOAT, p=25-53 is DOUBLE (we treat all as real)
            # Prevent matching "floating", "floated", etc.
            (r'\bfloat(?![a-zA-Z0-9_])(?:\s*\(\d+(?:,\s*\d+)?\))?(?:\s+unsigned)?(?:\s+zerofill)?', 'real'),

            # ============================================================
            # FIXED-POINT TYPES (exact numeric values)
            # ============================================================
            # DECIMAL, DEC, NUMERIC, FIXED are all synonyms
            # Preserve precision/scale: DECIMAL(M,D) -> DECIMAL(M,D)
            (r'\bdecimal\s*\((\d+),\s*(\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1,\2)'),
            (r'\bdecimal\s*\((\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1)'),
            (r'\bdecimal\b(?!\s*\()(?:\s+unsigned)?(?:\s+zerofill)?', 'decimal'),
            (r'\bdec\s*\((\d+),\s*(\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1,\2)'),
            (r'\bdec\s*\((\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1)'),
            (r'\bdec\b(?!\s*\()(?:\s+unsigned)?(?:\s+zerofill)?', 'decimal'),
            (r'\bnumeric\s*\((\d+),\s*(\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'numeric(\1,\2)'),
            (r'\bnumeric\s*\((\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'numeric(\1)'),
            (r'\bnumeric\b(?!\s*\()(?:\s+unsigned)?(?:\s+zerofill)?', 'numeric'),
            (r'\bfixed\s*\((\d+),\s*(\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1,\2)'),
            (r'\bfixed\s*\((\d+)\)(?:\s+unsigned)?(?:\s+zerofill)?', r'decimal(\1)'),
            (r'\bfixed\b(?!\s*\()(?:\s+unsigned)?(?:\s+zerofill)?', 'decimal'),

            # ============================================================
            # DATE/TIME TYPES
            # ============================================================
            (r'\bdate\b', 'date'),
            (r'\byear(?:\s*\(\d+\))?', 'smallint'),  # YEAR(2) or YEAR(4)

            # ============================================================
            # BIT TYPE
            # ============================================================
            (r'\bbit\s*\((\d+)\)', r'bit(\1)'),
            (r'\bbit\b(?!\s*\()', 'bit(1)'),

            # ============================================================
            # STRING TYPES
            # ============================================================
            # MySQL CHAR doesn't pad on retrieval, but PostgreSQL character() does
            # Use varchar to avoid trailing space issues
            # IMPORTANT: Require parentheses to avoid matching column names like character_guid
            (r'\bchar\s*\((\d+)\)', r'varchar(\1)'),
            (r'\bvarchar(\s*\(\d+\))?', r'varchar\1'),
            (r'\btinytext\b', 'text'),
            (r'\bmediumtext\b', 'text'),
            (r'\blongtext\b', 'text'),
            (r'\btext\b', 'text'),

            # ============================================================
            # BINARY/BLOB TYPES
            # ============================================================
            (r'\btinyblob\b', 'bytea'),
            (r'\bmediumblob\b', 'bytea'),
            (r'\blongblob\b', 'bytea'),
            (r'\bblob\b', 'bytea'),
            (r'\bbinary(?:\s*\(\d+\))?', 'bytea'),
            (r'\bvarbinary(?:\s*\(\d+\))?', 'bytea'),

            # ============================================================
            # ENUM and SET (handled separately with CHECK constraints)
            # ============================================================
            (r'\bset\s*\([^)]+\)', 'text'),  # SET converted to text (array not worth complexity)
        ]

        def apply_type_conversions(create_table_block: str) -> str:
            """Apply all type conversions to a single CREATE TABLE statement."""
            result = create_table_block

            # Convert ENUM columns to varchar with CHECK constraint
            # Pattern: column_name ENUM('val1', 'val2', ...)
            enum_pattern = re.compile(
                r'(\w+)\s+ENUM\s*\(([^)]+)\)',
                re.IGNORECASE
            )
            result = enum_pattern.sub(self.convert_enum_to_check_constraint, result)

            # First, handle datetime/timestamp/time types with markers
            # datetime type - don't match when followed by datetime (column name case)
            datetime_pattern = r'\bdatetime\b(?!\s+datetime\b)'
            result = re.sub(datetime_pattern, TIMESTAMP_MARKER, result, flags=re.IGNORECASE)

            # timestamp type - don't match column name followed by type
            timestamp_pattern = (
                r'\btimestamp\b'
                r'(?!\s+(?:timestamp|datetime|' + TIMESTAMP_MARKER + '))'
                r'(?!\s+(?:tiny|small|medium|big)?int)'
                r'(?!\s+unsigned)'
                r'(?!\s+integer)'
            )
            result = re.sub(timestamp_pattern, TIMESTAMP_MARKER, result, flags=re.IGNORECASE)

            # time type - don't match column name followed by type
            time_pattern = (
                r'\btime\b'
                r'(?!\s+(?:tiny|small|medium|big)?int)'
                r'(?!\s+unsigned)'
                r'(?!\s+integer)'
                r'(?!\s+timestamp)'
                r'(?!\s+datetime)'
                r'(?!\s+' + TIMESTAMP_MARKER + ')'
            )
            result = re.sub(time_pattern, TIME_MARKER, result, flags=re.IGNORECASE)

            # Apply general type conversions
            for mysql_type, pg_type in type_conversions:
                result = re.sub(mysql_type, pg_type, result, flags=re.IGNORECASE)

            # Replace markers with actual PostgreSQL types
            result = result.replace(TIMESTAMP_MARKER, 'timestamp without time zone')
            result = result.replace(TIME_MARKER, 'time without time zone')

            return result

        # Find and convert only CREATE TABLE statements
        # Use a function to properly handle nested parentheses (e.g., varchar(255), int(10))
        def find_create_table_blocks(text: str) -> list:
            """Find all CREATE TABLE statement positions (start, end)."""
            blocks = []
            # Pattern to find the start of CREATE TABLE
            start_pattern = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?\w+`?\s*\(', re.IGNORECASE)

            pos = 0
            while pos < len(text):
                match = start_pattern.search(text, pos)
                if not match:
                    break

                start = match.start()
                # Find the matching closing paren by counting parens
                paren_count = 1
                i = match.end()  # Position after the opening (
                while i < len(text) and paren_count > 0:
                    if text[i] == '(':
                        paren_count += 1
                    elif text[i] == ')':
                        paren_count -= 1
                    i += 1

                if paren_count == 0:
                    # Find the semicolon after the closing paren
                    while i < len(text) and text[i] != ';':
                        i += 1
                    if i < len(text):
                        i += 1  # Include the semicolon
                    blocks.append((start, i))

                pos = i if i > pos else pos + 1

            return blocks

        # Process CREATE TABLE blocks in reverse order to preserve positions
        blocks = find_create_table_blocks(content)
        conversion_count = 0

        for start, end in reversed(blocks):
            original = content[start:end]
            converted = apply_type_conversions(original)
            if original != converted:
                conversion_count += 1
                content = content[:start] + converted + content[end:]

        if conversion_count > 0:
            self.log_debug(f"Converted data types in {conversion_count} CREATE TABLE statements")

        # Remove any remaining 'unsigned' keywords (e.g., real unsigned, double precision unsigned)
        # This handles cases where unsigned wasn't captured in the type conversion patterns
        self.log_debug("Removing remaining 'unsigned' keywords...")
        unsigned_count = len(re.findall(r'\b(real|double precision|decimal|numeric|smallint|integer|bigint)\s+unsigned\b', content, flags=re.IGNORECASE))
        content = re.sub(r'\b(real|double precision|decimal|numeric|smallint|integer|bigint)\s+unsigned\b', r'\1', content, flags=re.IGNORECASE)
        if unsigned_count > 0:
            self.log_debug(f"Removed {unsigned_count} remaining 'unsigned' keywords")

        # Remove inline column COMMENT (MySQL-specific, PostgreSQL uses separate COMMENT ON statement)
        self.log_debug("Removing inline column COMMENT clauses...")
        # Match COMMENT 'text' on column definitions (must be after column type and before comma/closing paren)
        column_comment_count = len(re.findall(r"\s+COMMENT\s+'[^']*'", content, flags=re.IGNORECASE))
        content = re.sub(r"\s+COMMENT\s+'[^']*'", '', content, flags=re.IGNORECASE)
        if column_comment_count > 0:
            self.log_debug(f"Removed {column_comment_count} inline column COMMENT clauses")

        # Track and remove ON UPDATE CURRENT_TIMESTAMP (MySQL-specific, PostgreSQL uses triggers)
        # We track occurrences but implementing per-column triggers requires table context
        # For now, remove the clause and log a warning
        self.log_debug("Removing ON UPDATE CURRENT_TIMESTAMP clauses...")
        on_update_count = len(re.findall(r'\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP', content, flags=re.IGNORECASE))
        content = re.sub(r'\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP', '', content, flags=re.IGNORECASE)
        if on_update_count > 0:
            self.log_debug(f"Removed {on_update_count} ON UPDATE CURRENT_TIMESTAMP clauses")
            self.log_debug("NOTE: PostgreSQL equivalent requires triggers - implement manually if needed")

        # Convert MySQL KEY/INDEX syntax to PostgreSQL
        # MySQL: UNIQUE KEY idx_name (columns) or KEY idx_name (columns)
        # PostgreSQL: UNIQUE (columns) or remove KEY (indexes created separately)
        self.log_debug("Converting MySQL KEY/INDEX syntax...")

        # Convert UNIQUE KEY name (columns) to UNIQUE (columns) - keep UNIQUE constraint
        unique_key_count = len(re.findall(r'UNIQUE\s+KEY\s+\w+\s*\([^)]+\)', content, flags=re.IGNORECASE))
        content = re.sub(r'UNIQUE\s+KEY\s+\w+\s*(\([^)]+\))', r'UNIQUE \1', content, flags=re.IGNORECASE)
        if unique_key_count > 0:
            self.log_debug(f"Converted {unique_key_count} UNIQUE KEY to UNIQUE constraints")

        # Remove ASC/DESC from UNIQUE constraints (PostgreSQL doesn't support sort order in UNIQUE)
        # Pattern matches column name followed by ASC or DESC within parentheses after UNIQUE
        asc_desc_count = len(re.findall(r'UNIQUE\s*\([^)]*\s+(ASC|DESC)\s*[,)]', content, flags=re.IGNORECASE))
        content = re.sub(r'(\w+)\s+(ASC|DESC)(\s*[,)])', r'\1\3', content, flags=re.IGNORECASE)
        if asc_desc_count > 0:
            self.log_debug(f"Removed {asc_desc_count} ASC/DESC from UNIQUE constraints")

        # Remove FULLTEXT KEY declarations (PostgreSQL uses different full-text search syntax)
        fulltext_count = len(re.findall(r',?\s*FULLTEXT(?:\s+KEY)?\s+\w*\s*\([^)]+\)', content, flags=re.IGNORECASE))
        content = re.sub(r',?\s*FULLTEXT(?:\s+KEY)?\s+\w*\s*\([^)]+\)', '', content, flags=re.IGNORECASE)
        # Also remove standalone FULLTEXT word if left behind
        content = re.sub(r',?\s*FULLTEXT\s*\n', '\n', content, flags=re.IGNORECASE)
        if fulltext_count > 0:
            self.log_debug(f"Removed {fulltext_count} FULLTEXT KEY declarations (PostgreSQL uses GIN/GIST indexes)")

        # Remove standalone KEY (non-unique indexes) - these should be CREATE INDEX statements
        # For now, we'll just remove them from the table definition
        # Pattern: KEY idx_name (columns) - but NOT PRIMARY KEY or UNIQUE KEY
        # Use negative lookbehind to avoid matching PRIMARY KEY
        key_count = len(re.findall(r',?\s*(?<!PRIMARY\s)(?<!UNIQUE\s)\bKEY\s+\w+\s*\([^)]+\)', content, flags=re.IGNORECASE))
        content = re.sub(r',?\s*(?<!PRIMARY\s)(?<!UNIQUE\s)\bKEY\s+\w+\s*\([^)]+\)', '', content, flags=re.IGNORECASE)
        if key_count > 0:
            self.log_debug(f"Removed {key_count} KEY (index) declarations (need separate CREATE INDEX)")

        # Remove USING BTREE/HASH from PRIMARY KEY and UNIQUE constraints
        # PostgreSQL doesn't support this syntax in constraint definitions
        using_clause_count = len(re.findall(r'(?:PRIMARY\s+KEY|UNIQUE)\s*\([^)]+\)\s+USING\s+(?:BTREE|HASH)', content, flags=re.IGNORECASE))
        content = re.sub(r'((?:PRIMARY\s+KEY|UNIQUE)\s*\([^)]+\))\s+USING\s+(?:BTREE|HASH)', r'\1', content, flags=re.IGNORECASE)
        if using_clause_count > 0:
            self.log_debug(f"Removed {using_clause_count} USING BTREE/HASH clauses from constraints")

        # Enhanced ENGINE, CHARSET, and other MySQL-specific clause removal
        self.log_debug("Removing MySQL-specific table clauses...")
        mysql_clauses = [
            (r'\)\s*ENGINE\s*=\s*\w+[^;]*;', ');'),
            (r'\s*ENGINE\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*DEFAULT\s+CHARSET\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*COLLATE\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*COMMENT\s*=\s*[^,;)]+', ''),  # Table-level COMMENT
            (r'\s*AUTO_INCREMENT\s*=\s*\d+', ''),
            (r'\s*ROW_FORMAT\s*=\s*\w+', ''),
            (r'\s*KEY_BLOCK_SIZE\s*=\s*\d+', ''),
            (r'\s*PACK_KEYS\s*=\s*\w+', ''),
        ]

        removal_count = 0
        for pattern, replacement in mysql_clauses:
            matches = len(re.findall(pattern, content, flags=re.IGNORECASE))
            if matches > 0:
                removal_count += matches
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

        if removal_count > 0:
            self.log_debug(f"Removed {removal_count} MySQL-specific clauses")

        # Enhanced MySQL hex literal conversion
        # In MySQL dumps, 0xHEX literals are typically binary data (for bytea columns)
        # IMPORTANT: Only convert hex literals in value contexts, not inside strings
        # Value contexts are indicated by preceding: comma, open paren, equals, or start of line
        # This prevents converting "0x..." patterns that appear inside comment strings
        self.log_debug("Converting MySQL hex literals...")

        def hex_replacer(match):
            hex_value = match.group(1)
            # Use decode() for hex literals - works for bytea columns
            return f"decode('{hex_value}', 'hex')"

        # Pattern matches 0xHEX only when preceded by value context indicators
        # (?<=[,(=]) - lookbehind for comma, open paren, or equals
        hex_pattern = r"(?<=[,(=])0x([0-9A-Fa-f]+)"
        hex_count = len(re.findall(hex_pattern, content))
        content = re.sub(hex_pattern, hex_replacer, content)
        if hex_count > 0:
            self.log_debug(f"Converted {hex_count} hex literals to decode() function calls")

        # Convert invalid MySQL date values (0000-00-00) to valid PostgreSQL dates
        content = self.convert_invalid_dates(content)

        # Enhanced REPLACE INTO conversion
        self.log_debug("Converting REPLACE INTO statements...")

        # For simple REPLACE INTO without primary key info, convert to INSERT with basic ON CONFLICT
        # This handles the common pattern: REPLACE INTO table (cols) VALUES (vals)
        def convert_replace_into(match):
            table_part = match.group(1)
            values_part = match.group(2)

            # Basic conversion - would need table schema knowledge for proper ON CONFLICT clause
            replacement = f"INSERT INTO {table_part} {values_part} ON CONFLICT DO NOTHING"
            self.log_debug(f"Converting REPLACE INTO to: {replacement}")
            return replacement

        # Match REPLACE INTO table_name (columns) VALUES (values)
        content = re.sub(r'REPLACE INTO\s+(\w+(?:\s*\([^)]+\))?(?:\s+VALUES\s*\([^)]+\))*)',
                        r'INSERT INTO \1 ON CONFLICT DO NOTHING',
                        content, flags=re.IGNORECASE)

        # Enhanced ON DUPLICATE KEY UPDATE conversion
        self.log_debug("Converting ON DUPLICATE KEY UPDATE...")

        def convert_duplicate_key_update(match):
            update_clause = match.group(1)
            # Convert MySQL's UPDATE syntax to PostgreSQL's ON CONFLICT syntax
            # This is a basic conversion - full implementation would need primary key detection
            replacement = f"ON CONFLICT DO UPDATE SET {update_clause}"
            self.log_debug(f"Converting ON DUPLICATE KEY UPDATE to: {replacement}")
            return replacement

        content = re.sub(r'ON DUPLICATE KEY UPDATE\s+(.+?)(?=;|$)',
                        convert_duplicate_key_update,
                        content, flags=re.IGNORECASE | re.DOTALL)

        # Remove LIMIT from UPDATE statements (MySQL-specific, not supported in PostgreSQL)
        # For TrinityCore's use case, LIMIT 1 on UPDATE is typically used on single-row tables
        self.log_debug("Removing LIMIT from UPDATE statements...")
        limit_matches = len(re.findall(r'UPDATE\s+.+?\s+LIMIT\s+\d+', content, flags=re.IGNORECASE))
        content = re.sub(r'(\bUPDATE\s+.+?)\s+LIMIT\s+\d+', r'\1', content, flags=re.IGNORECASE)
        if limit_matches > 0:
            self.log_debug(f"Removed LIMIT from {limit_matches} UPDATE statements")

        # Convert MySQL backslash escape sequences to PostgreSQL format
        # MySQL uses backslash escaping, PostgreSQL standard strings don't interpret backslashes
        #
        # Critical: We use a placeholder approach to avoid false pattern matches.
        # Example issue: MySQL '...\\',' (string ending with literal backslash)
        #   Step 1: Convert \\ to \ gives '...\','
        #   Step 2: \' -> '' incorrectly matches, destroying the closing quote
        # Solution: Use placeholder during conversion, then restore at the end.
        self.log_debug("Converting MySQL backslash escapes...")

        # Placeholder that won't appear in SQL data (null byte surrounded by markers)
        BACKSLASH_PLACEHOLDER = "\x00BKSL\x00"

        # First: Convert escaped backslash (\\) to placeholder
        # In MySQL, \\ means a literal backslash
        escaped_backslash_count = content.count("\\\\")
        content = content.replace("\\\\", BACKSLASH_PLACEHOLDER)
        if escaped_backslash_count > 0:
            self.log_debug(f"Converted {escaped_backslash_count} escaped backslashes")

        # Second: Convert escaped double quotes (\") to regular double quotes
        # In MySQL, \" in a string means a literal double quote
        # In PostgreSQL standard strings, no escaping needed for double quotes in single-quoted strings
        escaped_dquote_count = content.count('\\"')
        content = content.replace('\\"', '"')
        if escaped_dquote_count > 0:
            self.log_debug(f"Converted {escaped_dquote_count} escaped double quotes")

        # Third: Convert escaped single quotes (\') to PostgreSQL style ('')
        escaped_quote_count = content.count("\\'")
        content = content.replace("\\'", "''")
        if escaped_quote_count > 0:
            self.log_debug(f"Converted {escaped_quote_count} escaped single quotes")

        # Finally: Restore backslashes from placeholder
        # In PostgreSQL standard strings, backslash is just a backslash (no escaping needed)
        content = content.replace(BACKSLASH_PLACEHOLDER, "\\")

        # Clean up extra whitespace and empty lines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Remove excessive blank lines

        # Fix quoted integer defaults for numeric columns
        # PostgreSQL doesn't accept DEFAULT '0' for integer/smallint/bigint columns
        # Must be DEFAULT 0 (unquoted)
        self.log_debug("Fixing quoted integer defaults for numeric columns...")
        content = self.fix_quoted_numeric_defaults(content)

        # Extract foreign key constraints and move them to the end of the file
        # This handles the case where tables are defined in alphabetical order but
        # have FKs to tables that come later in the file
        content = self.defer_foreign_keys(content)

        # Append converted views at the end of the file
        # Views must come after all tables they reference are created
        if self._converted_views:
            view_section = "\n\n-- =============================================\n"
            view_section += "-- Converted MySQL Views\n"
            view_section += "-- =============================================\n\n"
            view_section += '\n\n'.join(self._converted_views)
            content = content.rstrip() + view_section + "\n"
            self.log_debug(f"Appended {len(self._converted_views)} views to output")

        return content

    def defer_foreign_keys(self, content: str) -> str:
        """Extract FOREIGN KEY constraints from CREATE TABLE and add them at the end.

        PostgreSQL requires referenced tables to exist when creating foreign keys.
        This method extracts FK constraints and creates ALTER TABLE statements at the end.
        """
        self.log_debug("Deferring foreign key constraints...")

        # Pattern to match CONSTRAINT ... FOREIGN KEY ... in CREATE TABLE
        # Captures: constraint_name, table context (from previous CREATE TABLE)
        fk_pattern = re.compile(
            r',?\s*CONSTRAINT\s+(\w+)\s+FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)(?:\s+ON\s+DELETE\s+(\w+))?(?:\s+ON\s+UPDATE\s+(\w+))?',
            re.IGNORECASE
        )

        # Find all CREATE TABLE statements and extract their FKs
        alter_statements = []
        current_table = None

        # Split content into lines and process
        lines = content.split('\n')
        new_lines = []
        fk_count = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Track current table
            create_match = re.match(r'CREATE\s+TABLE\s+(\w+)', line, re.IGNORECASE)
            if create_match:
                current_table = create_match.group(1)

            # Check for FK constraint
            fk_match = fk_pattern.search(line)
            if fk_match and current_table:
                constraint_name = fk_match.group(1)
                columns = fk_match.group(2)
                ref_table = fk_match.group(3)
                ref_columns = fk_match.group(4)
                on_delete = fk_match.group(5)
                on_update = fk_match.group(6)

                # Build ALTER TABLE statement
                alter_stmt = f"ALTER TABLE {current_table} ADD CONSTRAINT {constraint_name} FOREIGN KEY ({columns}) REFERENCES {ref_table} ({ref_columns})"
                if on_delete:
                    alter_stmt += f" ON DELETE {on_delete}"
                if on_update:
                    alter_stmt += f" ON UPDATE {on_update}"
                alter_stmt += ";"
                alter_statements.append(alter_stmt)
                fk_count += 1

                # Remove this line (or just the FK part if there's other content)
                # For simplicity, skip the line entirely
                i += 1
                continue

            new_lines.append(line)
            i += 1

        if fk_count > 0:
            self.log_debug(f"Deferred {fk_count} foreign key constraints")

            # Join lines and clean up trailing commas before closing parens
            content = '\n'.join(new_lines)

            # Fix trailing commas before ); in CREATE TABLE statements
            # Pattern: comma followed by whitespace/newlines and then );
            content = re.sub(r',\s*\n\s*\);', '\n);', content)

            # Add ALTER TABLE statements at the end
            content += '\n\n-- Deferred foreign key constraints\n'
            content += '\n'.join(alter_statements)
            content += '\n'
        else:
            content = '\n'.join(new_lines)

        # Convert ALTER TABLE statements
        content = self.convert_alter_table_statements(content)

        return content

    def convert_alter_table_statements(self, content: str) -> str:
        """Convert MySQL ALTER TABLE statements to PostgreSQL syntax.

        MySQL-specific syntax that needs conversion:
        - DROP PRIMARY KEY -> DROP CONSTRAINT tablename_pkey
        - ADD column_name type -> ADD COLUMN column_name type
        - ADD column_name type AFTER other_column -> ADD COLUMN column_name type (remove AFTER)
        - MODIFY column_name type -> ALTER COLUMN column_name TYPE type
        - CHANGE old_name new_name type -> ALTER COLUMN ... TYPE + RENAME COLUMN
        - Remove CHARACTER SET and COLLATE clauses
        """
        self.log_debug("Converting ALTER TABLE statements...")
        lines = content.split('\n')
        new_lines = []
        alter_count = 0
        current_table = None

        for line in lines:
            original_line = line

            # Check for ALTER TABLE to track the current table name
            # IMPORTANT: Only apply ALTER TABLE conversions to actual ALTER TABLE statements,
            # not to INSERT/UPDATE/DELETE statements that may contain similar keywords in data
            alter_match = re.match(r'^\s*ALTER\s+TABLE\s+[`"]?(\w+)[`"]?', line, re.IGNORECASE)
            is_alter_line = alter_match is not None

            if alter_match:
                current_table = alter_match.group(1)

            # Skip pattern matching for INSERT/UPDATE/DELETE statements to avoid
            # modifying string literals containing keywords like "add", "modify", etc.
            is_data_statement = re.match(
                r'^\s*(INSERT|UPDATE|DELETE|SELECT|VALUES|REPLACE)\b',
                line,
                re.IGNORECASE
            ) is not None

            # Only apply ALTER TABLE conversions to actual ALTER TABLE statements
            if is_alter_line and not is_data_statement:
                # Convert DROP PRIMARY KEY to DROP CONSTRAINT tablename_pkey
                # MySQL: ALTER TABLE `tablename` DROP PRIMARY KEY;
                # PostgreSQL: ALTER TABLE tablename DROP CONSTRAINT tablename_pkey;
                if re.search(r'\bDROP\s+PRIMARY\s+KEY\b', line, re.IGNORECASE):
                    if current_table:
                        line = re.sub(
                            r'\bDROP\s+PRIMARY\s+KEY\b',
                            f'DROP CONSTRAINT {current_table}_pkey',
                            line,
                            flags=re.IGNORECASE
                        )
                        alter_count += 1
                        self.log_debug(f"Converted DROP PRIMARY KEY for table {current_table}")

                # Convert ADD column without COLUMN keyword to ADD COLUMN
                # Also handle AFTER clause removal
                # MySQL: ALTER TABLE t ADD col_name type AFTER other_col
                # PostgreSQL: ALTER TABLE t ADD COLUMN col_name type
                add_pattern = re.compile(
                    r'\bADD\s+(?!COLUMN\b|CONSTRAINT\b|PRIMARY\s+KEY\b|UNIQUE\b|INDEX\b|KEY\b|FOREIGN\b)(\w+)',
                    re.IGNORECASE
                )
                if add_pattern.search(line):
                    line = add_pattern.sub(r'ADD COLUMN \1', line)
                    alter_count += 1
                    self.log_debug("Added COLUMN keyword to ADD statement")

                # Remove AFTER clause (MySQL-specific positioning)
                # MySQL: ADD COLUMN col_name type AFTER other_col
                # PostgreSQL: ADD COLUMN col_name type (no AFTER support)
                if re.search(r'\bAFTER\s+\w+', line, re.IGNORECASE):
                    line = re.sub(r'\s+AFTER\s+\w+', '', line, flags=re.IGNORECASE)
                    alter_count += 1
                    self.log_debug("Removed AFTER clause")

                # Remove CHARACTER SET and COLLATE from ALTER statements
                if 'CHARACTER SET' in line.upper() or 'COLLATE' in line.upper():
                    line = re.sub(r'\s+CHARACTER\s+SET\s+\w+(?:\s+COLLATE\s+\w+)?', '', line, flags=re.IGNORECASE)
                    line = re.sub(r'\s+COLLATE\s+\w+', '', line, flags=re.IGNORECASE)
                    alter_count += 1
                    self.log_debug("Removed CHARACTER SET/COLLATE from ALTER")

                # Convert MODIFY COLUMN to ALTER COLUMN ... TYPE
                # MySQL: ALTER TABLE t MODIFY [COLUMN] col_name new_type
                # PostgreSQL: ALTER TABLE t ALTER COLUMN col_name TYPE new_type
                modify_pattern = re.compile(
                    r'\bMODIFY\s+(?:COLUMN\s+)?(\w+)\s+(\w+(?:\([^)]+\))?)',
                    re.IGNORECASE
                )
                modify_match = modify_pattern.search(line)
                if modify_match:
                    col_name = modify_match.group(1)
                    col_type = modify_match.group(2)
                    # Apply type conversion to the column type
                    # (basic conversion - full type mapping would require calling apply_type_conversions)
                    line = modify_pattern.sub(f'ALTER COLUMN {col_name} TYPE {col_type}', line)
                    alter_count += 1
                    self.log_debug(f"Converted MODIFY COLUMN {col_name}")

                # Convert CHANGE COLUMN (rename + type change)
                # MySQL: ALTER TABLE t CHANGE [COLUMN] old_name new_name type
                # PostgreSQL: ALTER TABLE t RENAME COLUMN old_name TO new_name, ALTER COLUMN new_name TYPE type
                change_pattern = re.compile(
                    r'\bCHANGE\s+(?:COLUMN\s+)?(\w+)\s+(\w+)\s+(\w+(?:\([^)]+\))?)',
                    re.IGNORECASE
                )
                change_match = change_pattern.search(line)
                if change_match:
                    old_name = change_match.group(1)
                    new_name = change_match.group(2)
                    col_type = change_match.group(3)
                    if old_name == new_name:
                        # Just a type change
                        line = change_pattern.sub(f'ALTER COLUMN {new_name} TYPE {col_type}', line)
                    else:
                        # Name and type change - need two operations
                        # For simplicity, we'll put them in one statement with comma separation
                        line = change_pattern.sub(
                            f'RENAME COLUMN {old_name} TO {new_name}, ALTER COLUMN {new_name} TYPE {col_type}',
                            line
                        )
                    alter_count += 1
                    self.log_debug(f"Converted CHANGE COLUMN {old_name} -> {new_name}")

            new_lines.append(line)

        if alter_count > 0:
            self.log_debug(f"Converted {alter_count} ALTER TABLE operations")

        return '\n'.join(new_lines)

    def fix_quoted_numeric_defaults(self, content: str) -> str:
        """Fix quoted integer defaults that PostgreSQL doesn't accept for numeric columns.

        MySQL accepts DEFAULT '0' for numeric columns, but PostgreSQL requires DEFAULT 0.
        This function identifies numeric column definitions and unquotes their default values.
        """
        # Pattern to match column definitions with quoted numeric defaults
        # Matches: column_name TYPE ... DEFAULT 'number'
        # Types: smallint, integer, bigint, real, double precision, decimal, numeric, SERIAL, BIGSERIAL

        numeric_types = r'(?:smallint|integer|bigint|real|double precision|decimal|numeric|SERIAL|BIGSERIAL)'

        # Match column definition with quoted numeric default
        # This regex captures: (column_name) (type) (middle part) DEFAULT '(number)'
        pattern = re.compile(
            rf"(\w+\s+{numeric_types}(?:\([^)]+\))?\s*(?:NOT\s+NULL\s*)?)"  # column + type + optional NOT NULL
            rf"(DEFAULT\s+)'(-?\d+(?:\.\d+)?)'",  # DEFAULT 'number'
            re.IGNORECASE
        )

        def unquote_numeric_default(match):
            prefix = match.group(1)
            default_keyword = match.group(2)
            number = match.group(3)
            return f"{prefix}{default_keyword}{number}"

        original_len = len(content)
        content = pattern.sub(unquote_numeric_default, content)

        # Also fix cases where the type comes before DEFAULT without NOT NULL
        pattern2 = re.compile(
            rf"(\w+\s+{numeric_types}(?:\([^)]+\))?)\s+(DEFAULT\s+)'(-?\d+(?:\.\d+)?)'",
            re.IGNORECASE
        )
        content = pattern2.sub(unquote_numeric_default, content)

        if len(content) != original_len:
            self.log_debug("Fixed quoted numeric defaults")

        return content

    def convert_sql_file(self, input_file: Path, output_file: Optional[Path] = None) -> str:
        """Convert a complete SQL file from MySQL to PostgreSQL format"""
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.log_debug(f"Converting file: {input_file}")

        # Preprocess mysqldump content FIRST to remove artifacts
        # This must happen before variable extraction to avoid picking up
        # MySQL dump session variables like @saved_cs_client
        content = self.preprocess_mysqldump(content)

        # Extract MySQL variables (from actual user SQL, not dump artifacts)
        variables = self.extract_mysql_variables(content)

        if variables:
            self.log_debug(f"Found {len(variables)} MySQL variables - creating DO block")
            # Convert the entire content as a DO block
            result = self.convert_mysql_variables_to_do_block(content, variables)
        else:
            # No variables, do standard conversion
            self.log_debug("No MySQL variables found - doing standard conversion")
            result = self.convert_sql_content(content)

        # Add PostgreSQL header
        header = [
            '-- PostgreSQL database schema converted from MySQL',
            '-- Generated by TrinityCore MySQL to PostgreSQL converter (final integrated)',
            '-- All fixes integrated: variables, CASCADE, paths, types, functions',
            ''
        ]

        result = '\n'.join(header) + '\n' + result

        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            self.log_debug(f"Output written to: {output_file}")

        return result

def main():
    parser = argparse.ArgumentParser(
        description='Convert MySQL schema to PostgreSQL',
        epilog='Based on mysql2postgres gem conversion patterns for robust schema/data conversion.'
    )
    parser.add_argument('input_file', help='Input MySQL SQL file')
    parser.add_argument('output_file', nargs='?', help='Output PostgreSQL SQL file (optional, defaults to stdout)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--copy-format', action='store_true', dest='use_copy',
                        help='Use COPY format for bulk data (faster loading, not yet implemented)')

    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file) if args.output_file else None

    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    if args.use_copy:
        print("Warning: COPY format not yet implemented, using INSERT format", file=sys.stderr)

    converter = MySQLToPostgreSQLConverter(debug=args.debug, use_copy_format=args.use_copy)

    try:
        result = converter.convert_sql_file(input_path, output_path)

        if not output_path:
            print(result)

    except Exception as e:
        print(f"Error converting file: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()