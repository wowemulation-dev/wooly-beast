"""
Constraint transformers for MySQL to PostgreSQL conversion.

Handles conversion of MySQL constraint syntax to PostgreSQL,
including foreign key options and index definitions.
"""

from sqlglot import exp

from trinity_postgres_tools.pipeline.context import ConversionContext
from trinity_postgres_tools.transformers.base import BaseTransformer


class ForeignKeyTransformer(BaseTransformer):
    """
    Transformer for foreign key constraint conversion.

    Adjusts ON UPDATE/ON DELETE actions and constraint naming.
    """

    @property
    def name(self) -> str:
        return "foreign_key"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a foreign key constraint."""
        return isinstance(node, exp.ForeignKey)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform foreign key constraint."""
        if not isinstance(node, exp.ForeignKey):
            return node

        if not ctx.options.convert_foreign_keys:
            return node

        self.log(ctx, "Processing foreign key constraint")

        # Foreign keys mostly work the same, but we might need to
        # handle specific options differently
        return node


class IndexTransformer(BaseTransformer):
    """
    Transformer for index definitions.

    Converts MySQL index syntax to PostgreSQL.
    """

    @property
    def name(self) -> str:
        return "index"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is an index definition."""
        return isinstance(node, exp.Index)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform index definition."""
        if not isinstance(node, exp.Index):
            return node

        # Most index syntax is compatible
        # Handle any MySQL-specific options here
        return node


class PrimaryKeyTransformer(BaseTransformer):
    """
    Transformer for PRIMARY KEY constraints.

    Handles inline and table-level primary key definitions.
    """

    @property
    def name(self) -> str:
        return "primary_key"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a primary key constraint."""
        return isinstance(node, exp.PrimaryKey)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform primary key constraint."""
        if not isinstance(node, exp.PrimaryKey):
            return node

        # Primary key syntax is mostly compatible
        return node


class UniqueConstraintTransformer(BaseTransformer):
    """
    Transformer for UNIQUE constraints.

    Handles both column-level and table-level unique constraints.
    """

    @property
    def name(self) -> str:
        return "unique"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a unique constraint."""
        return isinstance(node, exp.Unique)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform unique constraint."""
        if not isinstance(node, exp.Unique):
            return node

        # Unique constraint syntax is compatible
        return node


class CheckConstraintTransformer(BaseTransformer):
    """
    Transformer for CHECK constraints.

    Converts MySQL check constraint expressions to PostgreSQL.
    """

    @property
    def name(self) -> str:
        return "check"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a check constraint."""
        return isinstance(node, exp.Check)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform check constraint."""
        if not isinstance(node, exp.Check):
            return node

        # Check constraint syntax is mostly compatible
        # May need to transform MySQL functions within the expression
        return node


def get_constraint_transformers() -> list[BaseTransformer]:
    """Get all constraint-related transformers."""
    return [
        ForeignKeyTransformer(),
        IndexTransformer(),
        PrimaryKeyTransformer(),
        UniqueConstraintTransformer(),
        CheckConstraintTransformer(),
    ]
