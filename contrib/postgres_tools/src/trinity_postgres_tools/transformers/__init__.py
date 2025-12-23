"""AST transformers for DDL statement conversion."""

from trinity_postgres_tools.transformers.auto_increment import (
    AutoIncrementTransformer,
    get_auto_increment_transformers,
)
from trinity_postgres_tools.transformers.base import (
    BaseTransformer,
    ExpressionVisitor,
    NodeTypeTransformer,
    Transformer,
    transform_tree,
)
from trinity_postgres_tools.transformers.constraints import (
    CheckConstraintTransformer,
    ForeignKeyTransformer,
    IndexTransformer,
    PrimaryKeyTransformer,
    UniqueConstraintTransformer,
    get_constraint_transformers,
)
from trinity_postgres_tools.transformers.registry import (
    TransformerRegistry,
    get_all_transformers,
    get_default_registry,
    get_transformer,
    register_transformer,
)
from trinity_postgres_tools.transformers.schema import (
    AutoIncrementStartRemover,
    CharsetRemover,
    CollateRemover,
    CommentRemover,
    EngineRemover,
    RowFormatRemover,
    get_schema_transformers,
)
from trinity_postgres_tools.transformers.types import (
    TypeTransformer,
    UnsignedIntegerTransformer,
    get_type_transformers,
)

__all__ = [
    # Base
    "BaseTransformer",
    "ExpressionVisitor",
    "NodeTypeTransformer",
    "Transformer",
    "transform_tree",
    # Registry
    "TransformerRegistry",
    "get_all_transformers",
    "get_default_registry",
    "get_transformer",
    "register_transformer",
    # Types
    "TypeTransformer",
    "UnsignedIntegerTransformer",
    "get_type_transformers",
    # Auto increment
    "AutoIncrementTransformer",
    "get_auto_increment_transformers",
    # Constraints
    "CheckConstraintTransformer",
    "ForeignKeyTransformer",
    "IndexTransformer",
    "PrimaryKeyTransformer",
    "UniqueConstraintTransformer",
    "get_constraint_transformers",
    # Schema
    "AutoIncrementStartRemover",
    "CharsetRemover",
    "CollateRemover",
    "CommentRemover",
    "EngineRemover",
    "RowFormatRemover",
    "get_schema_transformers",
]
