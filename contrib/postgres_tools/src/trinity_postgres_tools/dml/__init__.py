"""DML (INSERT, UPDATE, DELETE, REPLACE) processing module."""

from trinity_postgres_tools.dml.escape_handler import (
    ConvertedString,
    StringStyle,
    convert_string_content,
    convert_string_escapes,
    escape_for_postgres,
    needs_escape_string_style,
)
from trinity_postgres_tools.dml.literal_converter import (
    convert_backticks_to_double_quotes,
    convert_charset_introducer,
    convert_hex_literal,
    convert_hex_literals_in_sql,
    remove_backticks,
)
from trinity_postgres_tools.dml.tokenizer import (
    MySQLTokenizer,
    Token,
    TokenType,
    tokenize,
)
from trinity_postgres_tools.dml.user_variables import (
    expand_user_variables,
    get_variable_definitions,
    has_user_variables,
)

__all__ = [
    # Tokenizer
    "MySQLTokenizer",
    "Token",
    "TokenType",
    "tokenize",
    # Escape handler
    "ConvertedString",
    "StringStyle",
    "convert_string_escapes",
    "convert_string_content",
    "escape_for_postgres",
    "needs_escape_string_style",
    # Literal converter
    "convert_hex_literal",
    "convert_hex_literals_in_sql",
    "convert_charset_introducer",
    "convert_backticks_to_double_quotes",
    "remove_backticks",
    # User variables
    "expand_user_variables",
    "get_variable_definitions",
    "has_user_variables",
]
