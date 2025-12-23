"""
SQL statement splitter with proper string handling.

This module splits SQL files into individual statements while
correctly handling quoted strings, comments, and escape sequences.
"""

from dataclasses import dataclass
from enum import Enum, auto

from trinity_postgres_tools.pipeline.context import ConversionContext


class SplitterState(Enum):
    """State machine states for the splitter."""

    NORMAL = auto()  # Outside any special context
    SINGLE_QUOTE = auto()  # Inside '...'
    DOUBLE_QUOTE = auto()  # Inside "..."
    BACKTICK = auto()  # Inside `...`
    LINE_COMMENT = auto()  # Inside -- ...
    BLOCK_COMMENT = auto()  # Inside /* ... */


@dataclass
class Statement:
    """A parsed SQL statement with metadata."""

    sql: str
    start_line: int
    end_line: int
    is_empty: bool = False
    is_comment_only: bool = False


class StatementSplitter:
    """
    Splits SQL content into individual statements.

    Handles:
    - Semicolon-delimited statements
    - Quoted strings (single, double, backtick)
    - Escape sequences within strings
    - Line comments (-- ...)
    - Block comments (/* ... */)
    """

    def __init__(self, sql: str) -> None:
        """
        Initialize splitter with SQL content.

        Args:
            sql: Full SQL content to split
        """
        self.sql = sql
        self.pos = 0
        self.length = len(sql)
        self.line = 1
        self.state = SplitterState.NORMAL

    def split(self) -> list[Statement]:
        """
        Split SQL into statements.

        Returns:
            List of Statement objects
        """
        statements = []
        current = []
        start_line = 1

        while self.pos < self.length:
            char = self.sql[self.pos]

            # Track line numbers
            if char == "\n":
                self.line += 1

            # State machine
            if self.state == SplitterState.NORMAL:
                if char == "'":
                    self.state = SplitterState.SINGLE_QUOTE
                    current.append(char)
                elif char == '"':
                    self.state = SplitterState.DOUBLE_QUOTE
                    current.append(char)
                elif char == "`":
                    self.state = SplitterState.BACKTICK
                    current.append(char)
                elif char == "-" and self._peek() == "-":
                    self.state = SplitterState.LINE_COMMENT
                    current.append(char)
                elif char == "/" and self._peek() == "*":
                    self.state = SplitterState.BLOCK_COMMENT
                    current.append(char)
                elif char == ";":
                    # End of statement
                    current.append(char)
                    stmt_sql = "".join(current).strip()
                    if stmt_sql:
                        statements.append(
                            Statement(
                                sql=stmt_sql,
                                start_line=start_line,
                                end_line=self.line,
                                is_empty=False,
                                is_comment_only=self._is_comment_only(stmt_sql),
                            )
                        )
                    current = []
                    start_line = self.line
                else:
                    current.append(char)

            elif self.state == SplitterState.SINGLE_QUOTE:
                current.append(char)
                if char == "\\":
                    # Escape sequence - take next char too
                    self.pos += 1
                    if self.pos < self.length:
                        current.append(self.sql[self.pos])
                elif char == "'":
                    # Check for doubled quote
                    if self._peek() == "'":
                        self.pos += 1
                        current.append("'")
                    else:
                        self.state = SplitterState.NORMAL

            elif self.state == SplitterState.DOUBLE_QUOTE:
                current.append(char)
                if char == "\\":
                    self.pos += 1
                    if self.pos < self.length:
                        current.append(self.sql[self.pos])
                elif char == '"':
                    if self._peek() == '"':
                        self.pos += 1
                        current.append('"')
                    else:
                        self.state = SplitterState.NORMAL

            elif self.state == SplitterState.BACKTICK:
                current.append(char)
                if char == "`":
                    if self._peek() == "`":
                        self.pos += 1
                        current.append("`")
                    else:
                        self.state = SplitterState.NORMAL

            elif self.state == SplitterState.LINE_COMMENT:
                current.append(char)
                if char == "\n":
                    self.state = SplitterState.NORMAL

            elif self.state == SplitterState.BLOCK_COMMENT:
                current.append(char)
                if char == "*" and self._peek() == "/":
                    self.pos += 1
                    current.append("/")
                    self.state = SplitterState.NORMAL

            self.pos += 1

        # Handle remaining content (statement without trailing semicolon)
        remaining = "".join(current).strip()
        if remaining:
            statements.append(
                Statement(
                    sql=remaining,
                    start_line=start_line,
                    end_line=self.line,
                    is_empty=False,
                    is_comment_only=self._is_comment_only(remaining),
                )
            )

        return statements

    def _peek(self) -> str:
        """Peek at the next character without advancing."""
        if self.pos + 1 < self.length:
            return self.sql[self.pos + 1]
        return ""

    def _is_comment_only(self, sql: str) -> bool:
        """Check if a statement contains only comments and whitespace."""
        lines = sql.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            # Non-empty line that's not a line comment or complete block comment
            is_line_comment = stripped.startswith("--")
            is_block_comment = stripped.startswith("/*") and stripped.endswith("*/")
            if stripped and not is_line_comment and not is_block_comment:
                return False
        return True


def split_statements(sql: str, ctx: ConversionContext | None = None) -> list[Statement]:
    """
    Convenience function to split SQL into statements.

    Args:
        sql: SQL content to split
        ctx: Optional context for statistics

    Returns:
        List of Statement objects
    """
    splitter = StatementSplitter(sql)
    statements = splitter.split()

    if ctx:
        ctx.stats.statements_total = len(statements)
        comment_only = sum(1 for s in statements if s.is_comment_only)
        ctx.log_debug(f"Split into {len(statements)} statements ({comment_only} comment-only)")

    return statements


def split_and_filter(sql: str, ctx: ConversionContext | None = None) -> list[str]:
    """
    Split SQL and filter out empty/comment-only statements.

    Args:
        sql: SQL content to split
        ctx: Optional context for statistics

    Returns:
        List of SQL strings (filtered)
    """
    statements = split_statements(sql, ctx)
    return [s.sql for s in statements if not s.is_comment_only and not s.is_empty]
