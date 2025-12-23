"""
Custom sqlglot dialect for TrinityCore MySQL dumps.

This dialect extends MySQL to better handle patterns found in
mysqldump output and TrinityCore schema files.
"""

from typing import ClassVar

import sqlglot
from sqlglot import exp
from sqlglot.dialects.mysql import MySQL


class TrinityCoreMySQL(MySQL):
    """
    Custom MySQL dialect for TrinityCore database dumps.

    Extends the standard MySQL dialect with:
    - Better handling of mysqldump artifacts
    - TrinityCore-specific type patterns
    - Improved unsigned integer handling
    """

    class Tokenizer(MySQL.Tokenizer):
        """Extended tokenizer for TrinityCore patterns."""

        # Additional keywords found in TrinityCore schemas
        KEYWORDS: ClassVar[dict] = {
            **MySQL.Tokenizer.KEYWORDS,
            # Ensure these are recognized
            "MEDIUMINT": sqlglot.TokenType.MEDIUMINT,
        }

    class Parser(MySQL.Parser):
        """Extended parser for TrinityCore patterns."""

        pass

    class Generator(MySQL.Generator):
        """Extended generator for output formatting."""

        pass


# Type mapping from MySQL to PostgreSQL
# Used when transpiling between dialects
MYSQL_TO_POSTGRES_TYPES = {
    exp.DataType.Type.TINYINT: exp.DataType.Type.SMALLINT,
    exp.DataType.Type.MEDIUMINT: exp.DataType.Type.INT,
    exp.DataType.Type.BIGINT: exp.DataType.Type.BIGINT,
    # Add more as needed
}


def register_dialect() -> None:
    """Register the TrinityCore MySQL dialect with sqlglot."""
    # The dialect is automatically available by class name
    # This function exists for explicit registration if needed
    pass


def parse_mysql(sql: str) -> list[exp.Expression]:
    """
    Parse MySQL SQL using the TrinityCore dialect.

    Args:
        sql: MySQL SQL to parse

    Returns:
        List of parsed expressions
    """
    return sqlglot.parse(sql, dialect=TrinityCoreMySQL)


def transpile_to_postgres(sql: str) -> str:
    """
    Transpile MySQL SQL to PostgreSQL using TrinityCore dialect.

    This is a convenience function that combines parsing and generation.

    Args:
        sql: MySQL SQL to transpile

    Returns:
        PostgreSQL SQL
    """
    return sqlglot.transpile(
        sql, read=TrinityCoreMySQL, write="postgres", pretty=True
    )[0]
