"""
Base classes and protocols for AST transformers.

Transformers modify sqlglot AST nodes to convert MySQL patterns
to PostgreSQL equivalents.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from sqlglot import exp

from trinity_postgres_tools.pipeline.context import ConversionContext


@runtime_checkable
class Transformer(Protocol):
    """Protocol for AST transformers."""

    @property
    def name(self) -> str:
        """Transformer name for logging and debugging."""
        ...

    def can_transform(self, node: exp.Expression) -> bool:
        """
        Check if this transformer should handle the given node.

        Args:
            node: AST node to check

        Returns:
            True if this transformer should process the node
        """
        ...

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """
        Transform the node.

        Args:
            node: AST node to transform
            ctx: Conversion context for stats and options

        Returns:
            Transformed node, or None to remove the node
        """
        ...


class BaseTransformer(ABC):
    """Base class for AST transformers with common functionality."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Transformer name for logging."""
        pass

    @abstractmethod
    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this transformer handles this node type."""
        pass

    @abstractmethod
    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform the node."""
        pass

    def log(self, ctx: ConversionContext, message: str) -> None:
        """Log a message to the context."""
        ctx.log_debug(f"[{self.name}] {message}")


class NodeTypeTransformer(BaseTransformer):
    """Transformer that handles specific node types."""

    # Subclasses should set this to the expression type(s) they handle
    NODE_TYPES: tuple[type[exp.Expression], ...] = ()

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if node is one of our handled types."""
        return isinstance(node, self.NODE_TYPES)


class ExpressionVisitor:
    """
    Visitor for traversing and transforming expression trees.

    Applies transformers to matching nodes in a depth-first manner.
    """

    def __init__(self, transformers: list[Transformer]) -> None:
        """
        Initialize with a list of transformers.

        Args:
            transformers: Transformers to apply during traversal
        """
        self.transformers = transformers

    def visit(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """
        Visit a node and its children, applying transformers.

        Args:
            node: Root node to visit
            ctx: Conversion context

        Returns:
            Transformed node tree, or None if removed
        """
        # First, recursively transform children
        children_to_process = list(node.iter_expressions())
        for child in children_to_process:
            transformed = self.visit(child, ctx)
            if transformed is None:
                # Child was removed - use pop if available, otherwise replace
                try:
                    child.pop()
                except (AttributeError, KeyError):
                    # If pop doesn't work, try replace with None (may not work)
                    pass
            elif transformed is not child:
                # Child was transformed
                child.replace(transformed)

        # Then transform this node
        for transformer in self.transformers:
            if transformer.can_transform(node):
                result = transformer.transform(node, ctx)
                if result is None or result is not node:
                    return result

        return node


def transform_tree(
    tree: exp.Expression,
    transformers: list[Transformer],
    ctx: ConversionContext,
) -> exp.Expression | None:
    """
    Apply transformers to an expression tree.

    Args:
        tree: Root expression to transform
        transformers: Transformers to apply
        ctx: Conversion context

    Returns:
        Transformed tree, or None if removed
    """
    visitor = ExpressionVisitor(transformers)
    return visitor.visit(tree, ctx)
