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
    def __init__(self, debug=False):
        self.debug = debug

        # Tables that commonly need CASCADE on DROP due to foreign keys
        self.cascade_tables = {
            'account', 'characters', 'guild', 'account_data', 'character_account_data',
            'item_instance', 'mail', 'petition', 'rbac_permissions', 'creature',
            'gameobject', 'quest_template'
        }

    def log_debug(self, message: str):
        """Log debug message if debug mode is enabled"""
        if self.debug:
            print(f"DEBUG: {message}", file=sys.stderr)

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

        # Remove MySQL-specific directives and conditional comments
        self.log_debug("Removing MySQL-specific directives...")
        content = re.sub(r'/\*!\d+.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'^\s*/\*!.*?\*/;?\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*;\s*$', '', content, flags=re.MULTILINE)

        # Remove LOCK/UNLOCK TABLES
        content = re.sub(r'LOCK TABLES.+?;\s*\n?', '', content)
        content = re.sub(r'UNLOCK TABLES;\s*\n?', '', content)

        # Remove MySQL dump headers and footers
        content = re.sub(r'-- MySQL dump.*?\n', '', content)
        content = re.sub(r'-- Host:.*?\n', '', content)
        content = re.sub(r'-- Server version.*?\n', '', content)
        content = re.sub(r'-- Dump completed.*?\n', '', content)

        # Basic conversions that can be done globally
        self.log_debug("Applying basic conversions...")

        # Enhanced backtick removal
        self.log_debug("Removing MySQL backticks...")
        # Remove backticks around identifiers, but preserve content
        backtick_count = len(re.findall(r'`', content))
        content = re.sub(r'`([^`]+)`', r'\1', content)
        if backtick_count > 0:
            self.log_debug(f"Removed {backtick_count // 2} backtick pairs")

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

        # Enhanced data type conversion
        self.log_debug("Converting data types...")
        type_conversions = {
            r'\btinyint(\s*\(\d+\))?(\s+unsigned)?\b': 'smallint',
            r'\bsmallint(\s*\(\d+\))?(\s+unsigned)?\b': 'smallint',
            r'\bmediumint(\s*\(\d+\))?(\s+unsigned)?\b': 'integer',
            r'\bint(\s*\(\d+\))?(\s+unsigned)?\b': 'integer',
            r'\bbigint(\s*\(\d+\))?(\s+unsigned)?\b': 'bigint',
            r'\bfloat(\s*\(\d+,\s*\d+\))?\b': 'real',
            r'\bdouble(\s*\(\d+,\s*\d+\))?\b': 'double precision',
            r'\bdecimal(\s*\(\d+,\s*\d+\))?\b': 'decimal',
            r'\bnumeric(\s*\(\d+,\s*\d+\))?\b': 'numeric',
            r'\bdatetime\b': 'timestamp without time zone',
            r'\btimestamp\b': 'timestamp without time zone',
            r'\btime\b': 'time without time zone',
            r'\bdate\b': 'date',
            r'\byear(\s*\(\d+\))?\b': 'smallint',
            r'\bchar(\s*\(\d+\))?\b': 'char',
            r'\bvarchar(\s*\(\d+\))?\b': 'varchar',
            r'\btinytext\b': 'text',
            r'\btext\b': 'text',
            r'\bmediumtext\b': 'text',
            r'\blongtext\b': 'text',
            r'\btinyblob\b': 'bytea',
            r'\bblob\b': 'bytea',
            r'\bmediumblob\b': 'bytea',
            r'\blongblob\b': 'bytea',
            r'\bbinary(\s*\(\d+\))?\b': 'bytea',
            r'\bvarbinary(\s*\(\d+\))?\b': 'bytea',
            r'\benum\s*\([^)]+\)\b': 'text',
            r'\bset\s*\([^)]+\)\b': 'text',
        }

        conversion_count = 0
        for mysql_type, pg_type in type_conversions.items():
            matches = len(re.findall(mysql_type, content, flags=re.IGNORECASE))
            if matches > 0:
                conversion_count += matches
                content = re.sub(mysql_type, pg_type, content, flags=re.IGNORECASE)

        if conversion_count > 0:
            self.log_debug(f"Converted {conversion_count} data type references")

        # Enhanced AUTO_INCREMENT -> SERIAL conversion
        self.log_debug("Converting AUTO_INCREMENT to SERIAL...")

        # Handle various AUTO_INCREMENT patterns
        serial_patterns = [
            (r'(\w+)\s+(?:tiny|small|medium)?int\s*(?:\(\d+\))?\s+(?:unsigned\s+)?AUTO_INCREMENT', r'\1 SERIAL'),
            (r'(\w+)\s+bigint\s*(?:\(\d+\))?\s+(?:unsigned\s+)?AUTO_INCREMENT', r'\1 BIGSERIAL'),
            (r'AUTO_INCREMENT\s*=\s*\d+', ''),  # Remove AUTO_INCREMENT = value
        ]

        for pattern, replacement in serial_patterns:
            matches = len(re.findall(pattern, content, flags=re.IGNORECASE))
            if matches > 0:
                self.log_debug(f"Converting {matches} AUTO_INCREMENT patterns")
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

        # Enhanced ENGINE, CHARSET, and other MySQL-specific clause removal
        self.log_debug("Removing MySQL-specific table clauses...")
        mysql_clauses = [
            (r'\)\s*ENGINE\s*=\s*\w+[^;]*;', ');'),
            (r'\s*ENGINE\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*DEFAULT\s+CHARSET\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*COLLATE\s*=\s*\w+(?:\s+[^,;)]*)?', ''),
            (r'\s*COMMENT\s*=\s*[^,;)]+', ''),
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
        self.log_debug("Converting MySQL hex literals...")
        def hex_replacer(match):
            hex_value = match.group(1)
            # Convert MySQL 0x format to PostgreSQL \x format
            return f"'\\\\x{hex_value}'"

        hex_matches = len(re.findall(r"0x([0-9A-Fa-f]+)", content))
        content = re.sub(r"0x([0-9A-Fa-f]+)", hex_replacer, content)
        if hex_matches > 0:
            self.log_debug(f"Converted {hex_matches} hex literals")

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

        # Clean up extra whitespace and empty lines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Remove excessive blank lines

        return content

    def convert_sql_file(self, input_file: Path, output_file: Optional[Path] = None) -> str:
        """Convert a complete SQL file from MySQL to PostgreSQL format"""
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.log_debug(f"Converting file: {input_file}")

        # Extract MySQL variables first
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
    parser = argparse.ArgumentParser(description='Convert MySQL schema to PostgreSQL (Final Integrated)')
    parser.add_argument('input_file', help='Input MySQL SQL file')
    parser.add_argument('output_file', nargs='?', help='Output PostgreSQL SQL file (optional, defaults to stdout)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file) if args.output_file else None

    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    converter = MySQLToPostgreSQLConverter(debug=args.debug)

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