"""
MySQL literal conversion for DML statements.

This module handles conversion of MySQL-specific literals:
- Hex literals: 0xDEADBEEF → 3735928559 (integer)
- Unsigned integer overflow values
- Binary string notation

Note: In TrinityCore's SQL, hex literals are primarily used for integer
flag/mask values (e.g., unit_flags = 0x02000000). We convert them to
decimal integers for PostgreSQL compatibility.
"""

import re


def convert_hex_literal(hex_value: str) -> str:
    """
    Convert MySQL hex literal to PostgreSQL integer.

    MySQL: 0xDEADBEEF (used as integer in value contexts)
    PostgreSQL: 3735928559 (decimal integer)

    In TrinityCore SQL, hex literals are used for flags/masks which are
    stored in integer columns. PostgreSQL doesn't auto-convert hex to int,
    so we convert explicitly to decimal.

    Args:
        hex_value: MySQL hex literal (e.g., '0xDEADBEEF')

    Returns:
        Decimal integer string
    """
    if not hex_value.lower().startswith("0x"):
        return hex_value

    # Extract hex digits (skip '0x')
    hex_digits = hex_value[2:]

    # Handle empty hex
    if not hex_digits:
        return "0"

    # Convert hex to integer
    int_value = int(hex_digits, 16)
    return str(int_value)


def convert_hex_literals_in_sql(sql: str) -> str:
    """
    Convert all hex literals in SQL to decimal integers.

    This function is string-aware: hex literals inside single-quoted or
    double-quoted strings are NOT converted, as they are text content,
    not binary data.

    For example:
        0x02000000                    -> 33554432
        0xDEADBEEF                    -> 3735928559
        'Code injection at 0x40100A' -> 'Code injection at 0x40100A' (unchanged)

    Args:
        sql: SQL containing MySQL hex literals

    Returns:
        SQL with hex literals converted to decimal integers (only outside strings)
    """
    # Find all string literal spans to exclude them from conversion
    # Pattern for single-quoted strings (handles '' escapes and \' escapes)
    # Pattern for double-quoted strings (handles "" escapes and \" escapes)
    string_spans: list[tuple[int, int]] = []

    i = 0
    while i < len(sql):
        if sql[i] == "'" or sql[i] == '"':
            quote_char = sql[i]
            start = i
            i += 1
            # Find the end of the string
            while i < len(sql):
                if sql[i] == "\\" and i + 1 < len(sql):
                    # Skip escaped character
                    i += 2
                elif sql[i] == quote_char:
                    if i + 1 < len(sql) and sql[i + 1] == quote_char:
                        # Escaped quote by doubling ('' or "")
                        i += 2
                    else:
                        # End of string
                        i += 1
                        break
                else:
                    i += 1
            string_spans.append((start, i))
        else:
            i += 1

    def is_in_string(pos: int) -> bool:
        """Check if position is inside a string literal."""
        for start, end in string_spans:
            if start <= pos < end:
                return True
        return False

    # Pattern matches 0x followed by hex digits
    pattern = r"\b0[xX]([0-9a-fA-F]+)\b"

    def replace_hex(match: re.Match[str]) -> str:
        # Only convert if not inside a string literal
        if is_in_string(match.start()):
            return match.group(0)  # Return unchanged
        hex_digits = match.group(1)
        # Convert to decimal integer
        int_value = int(hex_digits, 16)
        return str(int_value)

    return re.sub(pattern, replace_hex, sql)


def handle_unsigned_overflow(value: str, target_type: str = "bigint") -> str:
    """
    Handle unsigned integer values that exceed signed type range.

    MySQL allows unsigned integers up to 2^64-1, but PostgreSQL's BIGINT
    is signed with max 2^63-1. Values exceeding this need special handling.

    Args:
        value: Integer value as string
        target_type: Target PostgreSQL type

    Returns:
        Converted value (possibly as NUMERIC)
    """
    try:
        int_value = int(value)
    except ValueError:
        return value

    # PostgreSQL BIGINT range: -9223372036854775808 to 9223372036854775807
    bigint_max = 9223372036854775807

    if int_value > bigint_max:
        # Value exceeds BIGINT range, return as-is (will need NUMERIC column)
        return value

    return value


def convert_mysql_null(sql: str) -> str:
    """
    Normalize MySQL NULL handling.

    MySQL accepts both NULL and \\N for null values in certain contexts.

    Args:
        sql: SQL with MySQL null notation

    Returns:
        SQL with standardized NULL
    """
    # Replace \\N with NULL in value contexts
    # This is primarily for LOAD DATA and mysqldump output
    return sql.replace("\\N", "NULL")


def convert_binary_string_literal(binary_literal: str) -> str:
    """
    Convert MySQL binary string literal to PostgreSQL bytea.

    MySQL: b'101010' or B'101010'
    PostgreSQL: B'101010' (bit string) or convert to bytea

    Args:
        binary_literal: MySQL binary string literal

    Returns:
        PostgreSQL equivalent
    """
    # MySQL and PostgreSQL both support B'...' for bit strings
    # No conversion needed for bit string literals
    return binary_literal


def convert_charset_introducer(sql: str) -> str:
    """
    Remove MySQL character set introducers.

    MySQL: _utf8'string' or _latin1'string'
    PostgreSQL: 'string'

    Args:
        sql: SQL with charset introducers

    Returns:
        SQL with introducers removed
    """
    # Pattern: _charset followed by a string literal
    pattern = r"_[a-zA-Z0-9]+('(?:[^'\\]|\\.)*')"

    def replace_introducer(match: re.Match) -> str:
        return match.group(1)

    return re.sub(pattern, replace_introducer, sql)


def convert_backticks_to_double_quotes(identifier: str) -> str:
    """
    Convert MySQL backtick identifier to PostgreSQL double-quoted.

    MySQL: `column_name`
    PostgreSQL: "column_name"

    Args:
        identifier: Backtick-quoted identifier

    Returns:
        Double-quoted identifier
    """
    if identifier.startswith("`") and identifier.endswith("`"):
        # Extract identifier name
        name = identifier[1:-1]
        # Handle escaped backticks (`` -> `)
        name = name.replace("``", "`")
        # PostgreSQL escapes double quotes by doubling
        name = name.replace('"', '""')
        return f'"{name}"'
    return identifier


# SQL reserved keywords that need to stay double-quoted in PostgreSQL
# These are common SQL keywords used as column/table names in TrinityCore
SQL_RESERVED_KEYWORDS = frozenset({
    "all", "and", "any", "array", "as", "asc", "between", "by", "case",
    "check", "column", "constraint", "create", "cross", "current", "default",
    "delete", "desc", "distinct", "drop", "else", "end", "exists", "false",
    "fetch", "for", "foreign", "from", "full", "grant", "group", "having",
    "in", "index", "inner", "insert", "into", "is", "join", "key", "left",
    "like", "limit", "natural", "not", "null", "offset", "on", "or", "order",
    "outer", "primary", "references", "right", "select", "set", "table",
    "then", "to", "true", "type", "union", "unique", "update", "using",
    "values", "when", "where", "with",
})


def remove_backticks(sql: str) -> str:
    """
    Remove backtick quoting from identifiers and lowercase them.

    PostgreSQL normalizes unquoted identifiers to lowercase. To ensure
    consistency between DDL and DML, we lowercase all identifiers.

    For simple identifiers that don't need quoting, just remove backticks
    and lowercase. For reserved words, convert to double quotes.

    Args:
        sql: SQL with backtick identifiers

    Returns:
        SQL with backticks removed/converted and identifiers lowercased
    """
    # Pattern matches backtick-quoted identifiers
    pattern = r"`([a-zA-Z_][a-zA-Z0-9_]*)`"

    def replace_backtick(match: re.Match) -> str:
        name = match.group(1).lower()
        # Reserved keywords need to stay quoted in PostgreSQL
        if name in SQL_RESERVED_KEYWORDS:
            return f'"{name}"'
        return name

    return re.sub(pattern, replace_backtick, sql)
