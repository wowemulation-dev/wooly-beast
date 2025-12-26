"""
SQL statement classifier for routing to appropriate converters.

Classifies statements as DDL, DML, or OTHER to determine
which conversion strategy to apply.
"""

import re
from dataclasses import dataclass

from trinity_postgres_tools.pipeline.context import ConversionContext, StatementType


@dataclass
class ClassifiedStatement:
    """A statement with its classification."""

    sql: str
    statement_type: StatementType
    keyword: str  # The primary keyword (CREATE, INSERT, etc.)


# DDL keywords that should be processed by sqlglot
DDL_KEYWORDS = frozenset(
    [
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "RENAME",
    ]
)

# DML keywords that should use tokenizer-based conversion
DML_KEYWORDS = frozenset(
    [
        "INSERT",
        "UPDATE",
        "DELETE",
        "REPLACE",
    ]
)

# Keywords for statements to skip/pass through
PASSTHROUGH_KEYWORDS = frozenset(
    [
        "SELECT",
        "WITH",
    ]
)

# Keywords for statements to remove entirely
SKIP_KEYWORDS = frozenset(
    [
        "SET",
        "USE",
        "LOCK",
        "UNLOCK",
        "DELIMITER",
    ]
)


# Pattern to extract the first keyword from a statement
KEYWORD_PATTERN = re.compile(r"^\s*(\w+)", re.IGNORECASE)


def get_statement_keyword(sql: str) -> str:
    """
    Extract the first keyword from a SQL statement.

    Skips leading comments (line and block) to find the actual SQL keyword.

    Args:
        sql: SQL statement

    Returns:
        Uppercase keyword, or empty string if none found
    """
    # Strip leading whitespace
    text = sql.lstrip()

    # Skip leading line comments and block comments
    while text:
        if text.startswith("--"):
            # Skip to end of line
            newline_pos = text.find("\n")
            if newline_pos == -1:
                return ""  # Comment only, no keyword
            text = text[newline_pos + 1 :].lstrip()
        elif text.startswith("/*"):
            # Skip to end of block comment
            end_pos = text.find("*/")
            if end_pos == -1:
                return ""  # Unclosed block comment
            text = text[end_pos + 2 :].lstrip()
        else:
            break

    # Now extract the keyword from the non-comment portion
    match = KEYWORD_PATTERN.match(text)
    if match:
        return match.group(1).upper()
    return ""


def classify_statement(sql: str) -> ClassifiedStatement:
    """
    Classify a SQL statement by its type.

    Args:
        sql: SQL statement to classify

    Returns:
        ClassifiedStatement with type and keyword
    """
    # Check for empty/whitespace
    stripped = sql.strip()
    if not stripped:
        return ClassifiedStatement(sql=sql, statement_type=StatementType.EMPTY, keyword="")

    # Check for comment-only
    if _is_comment_only(stripped):
        return ClassifiedStatement(sql=sql, statement_type=StatementType.OTHER, keyword="COMMENT")

    # Get the primary keyword
    keyword = get_statement_keyword(stripped)

    if keyword in DDL_KEYWORDS:
        return ClassifiedStatement(sql=sql, statement_type=StatementType.DDL, keyword=keyword)

    if keyword in DML_KEYWORDS:
        return ClassifiedStatement(sql=sql, statement_type=StatementType.DML, keyword=keyword)

    # Everything else is OTHER
    return ClassifiedStatement(sql=sql, statement_type=StatementType.OTHER, keyword=keyword)


def _is_comment_only(sql: str) -> bool:
    """Check if a statement is comment-only."""
    lines = sql.split("\n")
    for line in lines:
        stripped = line.strip()
        # Non-empty line that's not a line comment or complete block comment
        is_line_comment = stripped.startswith("--")
        is_block_comment = stripped.startswith("/*") and stripped.endswith("*/")
        if stripped and not is_line_comment and not is_block_comment:
            return False
    return True


class StatementClassifier:
    """
    Classifies SQL statements for routing through the pipeline.

    Provides batch classification and statistics tracking.
    """

    def __init__(self) -> None:
        self.ddl_count = 0
        self.dml_count = 0
        self.other_count = 0
        self.empty_count = 0

    def classify(self, sql: str) -> ClassifiedStatement:
        """Classify a single statement and update counts."""
        result = classify_statement(sql)

        if result.statement_type == StatementType.DDL:
            self.ddl_count += 1
        elif result.statement_type == StatementType.DML:
            self.dml_count += 1
        elif result.statement_type == StatementType.EMPTY:
            self.empty_count += 1
        else:
            self.other_count += 1

        return result

    def classify_batch(
        self, statements: list[str], ctx: ConversionContext | None = None
    ) -> list[ClassifiedStatement]:
        """
        Classify a batch of statements.

        Args:
            statements: List of SQL statements
            ctx: Optional context for statistics

        Returns:
            List of ClassifiedStatement objects
        """
        results = [self.classify(sql) for sql in statements]

        if ctx:
            ctx.stats.statements_ddl = self.ddl_count
            ctx.stats.statements_dml = self.dml_count
            ctx.log_debug(
                f"Classified: {self.ddl_count} DDL, {self.dml_count} DML, "
                f"{self.other_count} other, {self.empty_count} empty"
            )

        return results

    def reset_counts(self) -> None:
        """Reset classification counts."""
        self.ddl_count = 0
        self.dml_count = 0
        self.other_count = 0
        self.empty_count = 0


def classify_statements(
    statements: list[str], ctx: ConversionContext | None = None
) -> list[ClassifiedStatement]:
    """
    Convenience function to classify a list of statements.

    Args:
        statements: List of SQL statements
        ctx: Optional context for statistics

    Returns:
        List of ClassifiedStatement objects
    """
    classifier = StatementClassifier()
    return classifier.classify_batch(statements, ctx)


def is_ddl(sql: str) -> bool:
    """Check if a statement is DDL."""
    return classify_statement(sql).statement_type == StatementType.DDL


def is_dml(sql: str) -> bool:
    """Check if a statement is DML."""
    return classify_statement(sql).statement_type == StatementType.DML


def should_skip(sql: str) -> bool:
    """Check if a statement should be skipped entirely."""
    keyword = get_statement_keyword(sql)
    return keyword in SKIP_KEYWORDS
