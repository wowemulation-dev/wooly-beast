"""SQL parsing and statement classification module."""

from trinity_postgres_tools.parsing.classifier import (
    ClassifiedStatement,
    StatementClassifier,
    classify_statement,
    classify_statements,
    get_statement_keyword,
    is_ddl,
    is_dml,
    should_skip,
)
from trinity_postgres_tools.parsing.splitter import (
    Statement,
    StatementSplitter,
    split_and_filter,
    split_statements,
)

__all__ = [
    # Splitter
    "Statement",
    "StatementSplitter",
    "split_statements",
    "split_and_filter",
    # Classifier
    "ClassifiedStatement",
    "StatementClassifier",
    "classify_statement",
    "classify_statements",
    "get_statement_keyword",
    "is_ddl",
    "is_dml",
    "should_skip",
]
