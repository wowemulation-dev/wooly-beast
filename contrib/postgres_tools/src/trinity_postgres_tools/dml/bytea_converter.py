"""
BYTEA column hex literal converter.

Handles conversion of hex literals in INSERT statements for tables
with binary (BYTEA) columns. These need decode('hex', 'hex') format
instead of integer conversion.

MySQL:      INSERT INTO build_auth_key VALUES (12340, 'Win', 0xDEADBEEF...);
PostgreSQL: INSERT INTO build_auth_key VALUES (12340, 'Win', decode('DEADBEEF', 'hex'));
"""

import re
from typing import Match

from trinity_postgres_tools.config.bytea_tables import (
    get_bytea_column_indices,
    is_bytea_table,
)


def convert_hex_to_decode(hex_literal: str) -> str:
    """
    Convert a MySQL hex literal to PostgreSQL decode() call.

    Args:
        hex_literal: MySQL hex literal (e.g., '0xDEADBEEF')

    Returns:
        PostgreSQL decode() call (e.g., "decode('DEADBEEF', 'hex')")
    """
    if not hex_literal.lower().startswith("0x"):
        return hex_literal

    # Extract hex digits (skip '0x')
    hex_digits = hex_literal[2:].upper()

    # Handle empty hex
    if not hex_digits:
        return "decode('', 'hex')"

    return f"decode('{hex_digits}', 'hex')"


def _parse_insert_table_and_columns(sql: str) -> tuple[str | None, list[str] | None]:
    """
    Parse an INSERT statement to extract table name and column list.

    Args:
        sql: The INSERT statement

    Returns:
        Tuple of (table_name, [column_names]) or (None, None) if not parseable
    """
    # Pattern: INSERT INTO table_name (col1, col2, ...) VALUES
    # Also handles INSERT INTO table_name VALUES (no column list)
    pattern = r"""
        INSERT\s+INTO\s+
        [`"]?(\w+)[`"]?\s*               # table name (group 1)
        (?:\(([^)]+)\))?\s*              # optional column list (group 2)
        VALUES
    """

    match = re.search(pattern, sql, flags=re.IGNORECASE | re.VERBOSE)
    if not match:
        return None, None

    table_name = match.group(1)
    columns_str = match.group(2)

    if columns_str:
        # Parse column names, removing quotes and whitespace
        columns = [
            col.strip().strip('`"').lower()
            for col in columns_str.split(",")
        ]
    else:
        # No explicit column list - we can't determine column positions
        # Return empty list to indicate column positions are unknown
        columns = []

    return table_name, columns


def _convert_values_with_bytea(
    values_str: str,
    bytea_indices: set[int],
) -> str:
    """
    Convert hex literals to decode() for specified column indices.

    Args:
        values_str: The VALUES clause content (without parentheses)
        bytea_indices: Set of 0-based column indices that are BYTEA

    Returns:
        Converted values string
    """
    # Parse the values respecting string literals and nested parentheses
    values: list[str] = []
    current = []
    depth = 0
    in_string = False
    string_char = None
    i = 0

    while i < len(values_str):
        char = values_str[i]

        if in_string:
            current.append(char)
            if char == "\\" and i + 1 < len(values_str):
                # Escaped character
                current.append(values_str[i + 1])
                i += 2
                continue
            elif char == string_char:
                # Check for doubled quote escape
                if i + 1 < len(values_str) and values_str[i + 1] == string_char:
                    current.append(values_str[i + 1])
                    i += 2
                    continue
                in_string = False
        else:
            if char in ("'", '"'):
                in_string = True
                string_char = char
                current.append(char)
            elif char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                # End of value
                values.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        i += 1

    # Don't forget the last value
    if current:
        values.append("".join(current).strip())

    # Convert hex literals in BYTEA columns
    converted = []
    for idx, val in enumerate(values):
        if idx in bytea_indices:
            # Check if this is a hex literal
            if re.match(r"0[xX][0-9a-fA-F]+", val):
                val = convert_hex_to_decode(val)
        converted.append(val)

    return ", ".join(converted)


def convert_bytea_hex_in_insert(sql: str) -> str:
    """
    Convert hex literals to decode() for BYTEA columns in INSERT statements.

    This function processes INSERT statements for known BYTEA tables and
    converts hex literals in binary columns to PostgreSQL decode() format.

    Args:
        sql: The SQL statement (may or may not be an INSERT)

    Returns:
        Converted SQL with hex literals as decode() for BYTEA columns
    """
    # Quick check - only process INSERTs
    # Use re.search because comments may precede the INSERT statement
    if not re.search(r"\bINSERT\s+INTO\s+", sql, re.IGNORECASE):
        return sql

    # Parse table and columns
    table_name, columns = _parse_insert_table_and_columns(sql)
    if not table_name:
        return sql

    # Check if this table has BYTEA columns
    if not is_bytea_table(table_name):
        return sql

    # If no explicit column list, we can't determine positions
    # For these tables, we need to handle it differently
    if not columns:
        # Try to infer from table structure
        # For now, handle known tables with specific patterns
        return _convert_bytea_no_column_list(sql, table_name)

    # Get the indices of BYTEA columns
    bytea_indices = get_bytea_column_indices(table_name, columns)
    if not bytea_indices:
        return sql

    # Find and convert VALUES
    # Pattern matches VALUES followed by one or more value tuples
    def convert_values_match(match: Match[str]) -> str:
        full_match = match.group(0)

        # Find all value tuples
        result_parts = ["VALUES"]
        rest = full_match[6:].strip()  # Skip "VALUES"

        # Process each value tuple
        tuple_pattern = r"\(([^)]+)\)"
        pos = 0
        first = True

        for tuple_match in re.finditer(tuple_pattern, rest):
            # Add any text before this tuple (commas, whitespace)
            if not first:
                result_parts.append(",")
            first = False

            values_str = tuple_match.group(1)
            converted = _convert_values_with_bytea(values_str, bytea_indices)
            result_parts.append(f"({converted})")
            pos = tuple_match.end()

        # Add any trailing content
        result_parts.append(rest[pos:])

        return " ".join(result_parts)

    # Apply the conversion
    converted = re.sub(
        r"VALUES\s*\([^;]+",
        convert_values_match,
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return converted


def _convert_bytea_no_column_list(sql: str, table_name: str) -> str:
    """
    Handle BYTEA tables without explicit column lists.

    For INSERT INTO table VALUES (...) without column names, we need to
    rely on knowing the table structure.

    Args:
        sql: The INSERT statement
        table_name: The table name (already validated as BYTEA table)

    Returns:
        Converted SQL
    """
    table_lower = table_name.lower()

    # Known table structures - column positions (0-based)
    # These are based on the actual CREATE TABLE definitions
    known_structures: dict[str, set[int]] = {
        # build_auth_key (build, platform, arch, type, key)
        # key is at index 4
        "build_auth_key": {4},

        # build_executable_hash (build, platform, executableHash)
        # executableHash is at index 2
        "build_executable_hash": {2},

        # warden_checks (id, type, data, result, address, length, str, comment)
        # data is at index 2, result is at index 3
        "warden_checks": {2, 3},
    }

    if table_lower not in known_structures:
        return sql

    bytea_indices = known_structures[table_lower]

    # Process VALUES tuples
    def convert_tuple(match: Match[str]) -> str:
        values_str = match.group(1)
        converted = _convert_values_with_bytea(values_str, bytea_indices)
        return f"({converted})"

    # Find VALUES and convert each tuple
    # First, split on VALUES
    values_match = re.search(r"\bVALUES\s*", sql, re.IGNORECASE)
    if not values_match:
        return sql

    before_values = sql[:values_match.end()]
    after_values = sql[values_match.end():]

    # Convert each tuple in the VALUES clause
    converted_after = re.sub(r"\(([^)]+)\)", convert_tuple, after_values)

    return before_values + converted_after
