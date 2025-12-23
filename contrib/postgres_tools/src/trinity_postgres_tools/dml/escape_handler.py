"""
MySQL to PostgreSQL escape sequence conversion.

This module handles the critical task of converting MySQL's backslash-based
escape sequences to PostgreSQL's format.

MySQL escape sequences:
- \\' = literal single quote → PostgreSQL: ''
- \\\\ = literal backslash → PostgreSQL: \\\\
- \\n = newline → PostgreSQL: E'\\n' or chr(10)
- \\r = carriage return → PostgreSQL: E'\\r'
- \\t = tab → PostgreSQL: E'\\t'
- \\" = double quote → PostgreSQL: "
- \\0 = NUL → PostgreSQL: E'\\x00'

CRITICAL: Order of operations matters!
The sequence \\\\' must be handled as (escaped backslash)(end quote),
not as (backslash)(escaped quote).
"""

from dataclasses import dataclass
from enum import Enum, auto


class StringStyle(Enum):
    """PostgreSQL string style."""

    STANDARD = auto()  # 'regular string'
    ESCAPE = auto()  # E'string with \\n escapes'


@dataclass
class ConvertedString:
    """Result of converting a MySQL string to PostgreSQL."""

    value: str
    style: StringStyle
    had_special_escapes: bool = False


# Placeholder for protecting escaped backslashes during conversion
ESCAPED_BACKSLASH_PLACEHOLDER = "\x00ESCAPED_BACKSLASH\x00"


def convert_string_escapes(mysql_string: str) -> ConvertedString:
    """
    Convert MySQL string escapes to PostgreSQL format.

    This is the core function that handles the tricky escape sequence
    conversions, including the critical \\\\' edge case.

    Args:
        mysql_string: MySQL string literal including quotes

    Returns:
        ConvertedString with PostgreSQL-compatible value
    """
    if not mysql_string or len(mysql_string) < 2:
        return ConvertedString(value=mysql_string, style=StringStyle.STANDARD)

    # Remove surrounding quotes
    if mysql_string.startswith("'") and mysql_string.endswith("'"):
        content = mysql_string[1:-1]
    else:
        # Not a standard string literal
        return ConvertedString(value=mysql_string, style=StringStyle.STANDARD)

    # Step 1: Protect escaped backslashes with placeholder
    # This prevents \\' from being mishandled
    content = content.replace("\\\\", ESCAPED_BACKSLASH_PLACEHOLDER)

    # Step 2: Convert escaped quotes
    # MySQL: \' → PostgreSQL: ''
    content = content.replace("\\'", "''")

    # Step 3: Check for special escape sequences that need E'' string style
    has_special_escapes = False
    special_escapes = ["\\n", "\\r", "\\t", "\\0"]

    for esc in special_escapes:
        if esc in content:
            has_special_escapes = True
            break

    # Step 4: Handle escaped double quotes
    # MySQL: \" → PostgreSQL: "
    content = content.replace('\\"', '"')

    # Step 5: Restore escaped backslashes
    content = content.replace(ESCAPED_BACKSLASH_PLACEHOLDER, "\\\\")

    # Step 6: Determine string style
    if has_special_escapes:
        # Need E'' string style for PostgreSQL to interpret escapes
        return ConvertedString(
            value=f"E'{content}'",
            style=StringStyle.ESCAPE,
            had_special_escapes=True,
        )
    else:
        return ConvertedString(
            value=f"'{content}'",
            style=StringStyle.STANDARD,
            had_special_escapes=False,
        )


def convert_string_content(content: str) -> tuple[str, bool]:
    """
    Convert just the content of a string (without quotes).

    This is useful when you've already extracted the string content.

    Args:
        content: String content without surrounding quotes

    Returns:
        Tuple of (converted content, needs_escape_string)
    """
    # Protect escaped backslashes
    result = content.replace("\\\\", ESCAPED_BACKSLASH_PLACEHOLDER)

    # Convert escaped quotes
    result = result.replace("\\'", "''")

    # Check for special escapes
    has_special = any(esc in result for esc in ["\\n", "\\r", "\\t", "\\0"])

    # Handle escaped double quotes
    result = result.replace('\\"', '"')

    # Restore escaped backslashes
    result = result.replace(ESCAPED_BACKSLASH_PLACEHOLDER, "\\\\")

    return result, has_special


def needs_escape_string_style(content: str) -> bool:
    """
    Check if a string needs PostgreSQL E'' escape string style.

    Args:
        content: String content (with or without quotes)

    Returns:
        True if the string contains escapes that need E'' style
    """
    # These escapes require E'' string style in PostgreSQL
    special_escapes = ["\\n", "\\r", "\\t", "\\0", "\\b", "\\f"]
    return any(esc in content for esc in special_escapes)


def escape_for_postgres(value: str) -> str:
    """
    Escape a raw Python string value for PostgreSQL.

    This is for creating new string literals, not converting MySQL strings.

    Args:
        value: Raw Python string value

    Returns:
        PostgreSQL string literal
    """
    # Check if we need E'' style
    if any(c in value for c in "\n\r\t\x00"):
        # Use E'' style with proper escapes
        escaped = value.replace("\\", "\\\\")
        escaped = escaped.replace("'", "''")
        escaped = escaped.replace("\n", "\\n")
        escaped = escaped.replace("\r", "\\r")
        escaped = escaped.replace("\t", "\\t")
        escaped = escaped.replace("\x00", "\\x00")
        return f"E'{escaped}'"
    else:
        # Standard style
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
