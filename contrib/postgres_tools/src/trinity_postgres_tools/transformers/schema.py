"""
Schema-level transformers for MySQL to PostgreSQL conversion.

Handles removal of MySQL-specific schema elements like ENGINE,
CHARACTER SET, and COLLATE specifications.
"""

from sqlglot import exp

from trinity_postgres_tools.pipeline.context import ConversionContext
from trinity_postgres_tools.transformers.base import BaseTransformer


class EngineRemover(BaseTransformer):
    """
    Transformer to remove MySQL ENGINE specifications.

    MySQL: ENGINE=InnoDB, ENGINE=MyISAM, etc.
    PostgreSQL: Not applicable (uses single storage engine)
    """

    @property
    def name(self) -> str:
        return "engine_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is an ENGINE property."""
        return bool(isinstance(node, exp.EngineProperty))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove ENGINE specification."""
        if not ctx.options.remove_engine_specs:
            return node

        ctx.stats.record_artifact_removed("ENGINE")
        self.log(ctx, "Removed ENGINE specification")
        return None  # Return None to remove the node


class CharsetRemover(BaseTransformer):
    """
    Transformer to remove MySQL CHARACTER SET specifications.

    MySQL: CHARACTER SET utf8mb4, CHARSET utf8, etc.
    PostgreSQL: Uses database/column encoding settings
    """

    @property
    def name(self) -> str:
        return "charset_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a CHARACTER SET property."""
        return bool(isinstance(node, exp.CharacterSetProperty))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove CHARACTER SET specification."""
        if not ctx.options.remove_charset_specs:
            return node

        ctx.stats.record_artifact_removed("CHARACTER SET")
        self.log(ctx, "Removed CHARACTER SET specification")
        return None


class CollateRemover(BaseTransformer):
    """
    Transformer to remove MySQL COLLATE specifications.

    MySQL: COLLATE utf8mb4_unicode_ci, etc.
    PostgreSQL: Uses database/column collation settings
    """

    @property
    def name(self) -> str:
        return "collate_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a COLLATE property."""
        return bool(isinstance(node, exp.CollateProperty))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove COLLATE specification."""
        if not ctx.options.remove_charset_specs:
            return node

        ctx.stats.record_artifact_removed("COLLATE")
        self.log(ctx, "Removed COLLATE specification")
        return None


class CommentRemover(BaseTransformer):
    """
    Transformer to handle MySQL table/column comments.

    MySQL: COMMENT 'description'
    PostgreSQL: Uses COMMENT ON command separately
    """

    @property
    def name(self) -> str:
        return "comment_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a COMMENT property."""
        return bool(isinstance(node, exp.CommentColumnConstraint))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove inline COMMENT specification."""
        ctx.stats.record_artifact_removed("COMMENT")
        self.log(ctx, "Removed inline COMMENT")
        return None


class RowFormatRemover(BaseTransformer):
    """
    Transformer to remove MySQL ROW_FORMAT specifications.

    MySQL: ROW_FORMAT=DYNAMIC, ROW_FORMAT=COMPACT, etc.
    PostgreSQL: Not applicable
    """

    @property
    def name(self) -> str:
        return "row_format_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a ROW_FORMAT property."""
        return bool(isinstance(node, exp.RowFormatProperty))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove ROW_FORMAT specification."""
        ctx.stats.record_artifact_removed("ROW_FORMAT")
        self.log(ctx, "Removed ROW_FORMAT specification")
        return None


class AutoIncrementStartRemover(BaseTransformer):
    """
    Transformer to remove MySQL AUTO_INCREMENT table option.

    MySQL: AUTO_INCREMENT=1234
    PostgreSQL: Use SETVAL to set sequence starting value
    """

    @property
    def name(self) -> str:
        return "auto_increment_start_remover"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is an AUTO_INCREMENT table option."""
        return bool(isinstance(node, exp.AutoIncrementProperty))

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Remove AUTO_INCREMENT table option."""
        ctx.stats.record_artifact_removed("AUTO_INCREMENT_START")
        self.log(ctx, "Removed AUTO_INCREMENT table option")
        return None


def get_schema_transformers() -> list[BaseTransformer]:
    """Get all schema-level transformers."""
    return [
        EngineRemover(),
        CharsetRemover(),
        CollateRemover(),
        CommentRemover(),
        RowFormatRemover(),
        AutoIncrementStartRemover(),
    ]
