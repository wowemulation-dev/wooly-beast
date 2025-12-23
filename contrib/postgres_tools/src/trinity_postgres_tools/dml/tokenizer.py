"""
MySQL string tokenizer for DML statements.

This tokenizer handles MySQL string literals with proper escape sequence
recognition, enabling safe transformation of string content without
corrupting the SQL structure.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Types of tokens in MySQL DML."""

    STRING = auto()  # Single-quoted string: 'value'
    HEX_LITERAL = auto()  # Hex literal: 0xDEADBEEF
    BACKTICK_ID = auto()  # Backtick identifier: `column`
    DOUBLE_QUOTED = auto()  # Double-quoted string: "value"
    NUMERIC = auto()  # Number: 123, -45.67
    KEYWORD = auto()  # SQL keyword/identifier
    OPERATOR = auto()  # Operators: =, (, ), ,
    WHITESPACE = auto()  # Spaces, tabs, newlines
    COMMENT = auto()  # -- or /* */ comments
    TEXT = auto()  # Any other text


@dataclass
class Token:
    """A token from MySQL SQL."""

    type: TokenType
    value: str
    start: int
    end: int

    @property
    def length(self) -> int:
        """Length of the token in source."""
        return self.end - self.start


class MySQLTokenizer:
    """
    Tokenizes MySQL DML statements with proper escape handling.

    This tokenizer correctly handles:
    - Single-quoted strings with escape sequences
    - MySQL's backslash escapes: \\', \\\\, \\n, \\r, \\t, \\"
    - Doubled quote escapes: ''
    - Hex literals: 0x...
    - Backtick identifiers: `column`
    """

    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.pos = 0
        self.length = len(sql)

    def tokenize(self) -> Iterator[Token]:
        """
        Tokenize the SQL into tokens.

        Yields:
            Token objects for each recognized element
        """
        while self.pos < self.length:
            token = self._next_token()
            if token:
                yield token

    def _next_token(self) -> Token | None:
        """Get the next token from current position."""
        if self.pos >= self.length:
            return None

        char = self.sql[self.pos]

        # Single-quoted string
        if char == "'":
            return self._read_single_quoted_string()

        # Double-quoted string
        if char == '"':
            return self._read_double_quoted_string()

        # Backtick identifier
        if char == "`":
            return self._read_backtick_identifier()

        # Hex literal (0x...)
        if char == "0" and self.pos + 1 < self.length and self.sql[self.pos + 1] in "xX":
            return self._read_hex_literal()

        # Number (including negative)
        if char.isdigit() or (char == "-" and self._peek_digit()):
            return self._read_number()

        # Whitespace
        if char.isspace():
            return self._read_whitespace()

        # Comment
        if char == "-" and self._peek_char("-"):
            return self._read_line_comment()
        if char == "/" and self._peek_char("*"):
            return self._read_block_comment()

        # Operators and punctuation
        if char in "(),;=<>!+-*/":
            return self._read_operator()

        # Keywords and identifiers
        if char.isalpha() or char == "_":
            return self._read_keyword()

        # Anything else
        return self._read_text()

    def _read_single_quoted_string(self) -> Token:
        """
        Read a single-quoted string with escape handling.

        MySQL escape sequences:
        - \\' = literal single quote
        - \\\\ = literal backslash
        - '' = literal single quote (SQL standard)
        - \\n, \\r, \\t = whitespace characters
        """
        start = self.pos
        self.pos += 1  # Skip opening quote
        content = ["'"]

        while self.pos < self.length:
            char = self.sql[self.pos]

            if char == "\\":
                # Escape sequence - take backslash and next char
                content.append(char)
                self.pos += 1
                if self.pos < self.length:
                    content.append(self.sql[self.pos])
                    self.pos += 1
            elif char == "'":
                # Check for doubled quote escape
                if self.pos + 1 < self.length and self.sql[self.pos + 1] == "'":
                    content.append("''")
                    self.pos += 2
                else:
                    # End of string
                    content.append("'")
                    self.pos += 1
                    break
            else:
                content.append(char)
                self.pos += 1

        return Token(
            type=TokenType.STRING, value="".join(content), start=start, end=self.pos
        )

    def _read_double_quoted_string(self) -> Token:
        """Read a double-quoted string."""
        start = self.pos
        self.pos += 1  # Skip opening quote
        content = ['"']

        while self.pos < self.length:
            char = self.sql[self.pos]

            if char == "\\":
                # Escape sequence
                content.append(char)
                self.pos += 1
                if self.pos < self.length:
                    content.append(self.sql[self.pos])
                    self.pos += 1
            elif char == '"':
                # Check for doubled quote
                if self.pos + 1 < self.length and self.sql[self.pos + 1] == '"':
                    content.append('""')
                    self.pos += 2
                else:
                    content.append('"')
                    self.pos += 1
                    break
            else:
                content.append(char)
                self.pos += 1

        return Token(
            type=TokenType.DOUBLE_QUOTED,
            value="".join(content),
            start=start,
            end=self.pos,
        )

    def _read_backtick_identifier(self) -> Token:
        """Read a backtick-quoted identifier."""
        start = self.pos
        self.pos += 1  # Skip opening backtick
        content = ["`"]

        while self.pos < self.length:
            char = self.sql[self.pos]
            if char == "`":
                # Check for doubled backtick
                if self.pos + 1 < self.length and self.sql[self.pos + 1] == "`":
                    content.append("``")
                    self.pos += 2
                else:
                    content.append("`")
                    self.pos += 1
                    break
            else:
                content.append(char)
                self.pos += 1

        return Token(
            type=TokenType.BACKTICK_ID,
            value="".join(content),
            start=start,
            end=self.pos,
        )

    def _read_hex_literal(self) -> Token:
        """Read a hex literal (0x...)."""
        start = self.pos
        self.pos += 2  # Skip '0x'
        content = ["0x"]

        while self.pos < self.length:
            char = self.sql[self.pos]
            if char in "0123456789abcdefABCDEF":
                content.append(char)
                self.pos += 1
            else:
                break

        return Token(
            type=TokenType.HEX_LITERAL,
            value="".join(content),
            start=start,
            end=self.pos,
        )

    def _read_number(self) -> Token:
        """Read a numeric literal."""
        start = self.pos
        content = []

        # Handle negative sign
        if self.sql[self.pos] == "-":
            content.append("-")
            self.pos += 1

        # Integer part
        while self.pos < self.length and self.sql[self.pos].isdigit():
            content.append(self.sql[self.pos])
            self.pos += 1

        # Decimal part
        if self.pos < self.length and self.sql[self.pos] == ".":
            content.append(".")
            self.pos += 1
            while self.pos < self.length and self.sql[self.pos].isdigit():
                content.append(self.sql[self.pos])
                self.pos += 1

        # Scientific notation
        if self.pos < self.length and self.sql[self.pos] in "eE":
            content.append(self.sql[self.pos])
            self.pos += 1
            if self.pos < self.length and self.sql[self.pos] in "+-":
                content.append(self.sql[self.pos])
                self.pos += 1
            while self.pos < self.length and self.sql[self.pos].isdigit():
                content.append(self.sql[self.pos])
                self.pos += 1

        return Token(
            type=TokenType.NUMERIC, value="".join(content), start=start, end=self.pos
        )

    def _read_whitespace(self) -> Token:
        """Read whitespace."""
        start = self.pos
        content = []

        while self.pos < self.length and self.sql[self.pos].isspace():
            content.append(self.sql[self.pos])
            self.pos += 1

        return Token(
            type=TokenType.WHITESPACE,
            value="".join(content),
            start=start,
            end=self.pos,
        )

    def _read_line_comment(self) -> Token:
        """Read a line comment (-- ...)."""
        start = self.pos
        content = []

        while self.pos < self.length and self.sql[self.pos] != "\n":
            content.append(self.sql[self.pos])
            self.pos += 1

        return Token(
            type=TokenType.COMMENT, value="".join(content), start=start, end=self.pos
        )

    def _read_block_comment(self) -> Token:
        """Read a block comment (/* ... */)."""
        start = self.pos
        content = []

        while self.pos < self.length:
            if (
                self.sql[self.pos] == "*"
                and self.pos + 1 < self.length
                and self.sql[self.pos + 1] == "/"
            ):
                content.append("*/")
                self.pos += 2
                break
            content.append(self.sql[self.pos])
            self.pos += 1

        return Token(
            type=TokenType.COMMENT, value="".join(content), start=start, end=self.pos
        )

    def _read_operator(self) -> Token:
        """Read an operator or punctuation."""
        start = self.pos
        char = self.sql[self.pos]
        self.pos += 1

        # Multi-character operators
        if self.pos < self.length:
            next_char = self.sql[self.pos]
            if (char, next_char) in [
                ("<", "="),
                (">", "="),
                ("!", "="),
                ("<", ">"),
            ]:
                self.pos += 1
                return Token(
                    type=TokenType.OPERATOR,
                    value=char + next_char,
                    start=start,
                    end=self.pos,
                )

        return Token(type=TokenType.OPERATOR, value=char, start=start, end=self.pos)

    def _read_keyword(self) -> Token:
        """Read a keyword or identifier."""
        start = self.pos
        content = []

        while self.pos < self.length:
            char = self.sql[self.pos]
            if char.isalnum() or char == "_":
                content.append(char)
                self.pos += 1
            else:
                break

        return Token(
            type=TokenType.KEYWORD, value="".join(content), start=start, end=self.pos
        )

    def _read_text(self) -> Token:
        """Read any other text."""
        start = self.pos
        self.pos += 1
        return Token(
            type=TokenType.TEXT, value=self.sql[start], start=start, end=self.pos
        )

    def _peek_char(self, expected: str) -> bool:
        """Check if next character matches expected."""
        return self.pos + 1 < self.length and self.sql[self.pos + 1] == expected

    def _peek_digit(self) -> bool:
        """Check if next character is a digit."""
        return self.pos + 1 < self.length and self.sql[self.pos + 1].isdigit()


def tokenize(sql: str) -> list[Token]:
    """
    Convenience function to tokenize SQL into a list.

    Args:
        sql: MySQL SQL to tokenize

    Returns:
        List of tokens
    """
    return list(MySQLTokenizer(sql).tokenize())
