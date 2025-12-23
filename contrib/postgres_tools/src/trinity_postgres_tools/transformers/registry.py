"""
Transformer registry for managing and accessing transformers.

The registry provides a central location for registering transformers
and retrieving appropriate transformers for different conversion tasks.
"""

from collections.abc import Callable

from trinity_postgres_tools.transformers.base import Transformer


class TransformerRegistry:
    """
    Registry for transformer instances.

    Transformers can be registered by name and retrieved for use
    in the conversion pipeline.
    """

    def __init__(self) -> None:
        self._transformers: dict[str, Transformer] = {}
        self._factories: dict[str, Callable[[], Transformer]] = {}

    def register(self, transformer: Transformer) -> None:
        """
        Register a transformer instance.

        Args:
            transformer: Transformer to register
        """
        self._transformers[transformer.name] = transformer

    def register_factory(
        self, name: str, factory: Callable[[], Transformer]
    ) -> None:
        """
        Register a factory function for lazy transformer creation.

        Args:
            name: Name for the transformer
            factory: Function that creates the transformer
        """
        self._factories[name] = factory

    def get(self, name: str) -> Transformer | None:
        """
        Get a transformer by name.

        Args:
            name: Transformer name

        Returns:
            Transformer instance, or None if not found
        """
        if name in self._transformers:
            return self._transformers[name]
        if name in self._factories:
            transformer = self._factories[name]()
            self._transformers[name] = transformer
            return transformer
        return None

    def get_all(self) -> list[Transformer]:
        """
        Get all registered transformers.

        Returns:
            List of all transformers (instantiates any lazy factories)
        """
        # Instantiate any remaining factories
        for name, factory in self._factories.items():
            if name not in self._transformers:
                self._transformers[name] = factory()

        return list(self._transformers.values())

    def get_by_category(self, category: str) -> list[Transformer]:
        """
        Get transformers matching a category prefix.

        Args:
            category: Category prefix (e.g., 'type', 'constraint')

        Returns:
            List of matching transformers
        """
        matching = []
        for name, transformer in self._transformers.items():
            if name.startswith(category):
                matching.append(transformer)
        for name, factory in self._factories.items():
            if name.startswith(category) and name not in self._transformers:
                transformer = factory()
                self._transformers[name] = transformer
                matching.append(transformer)
        return matching

    def names(self) -> list[str]:
        """Get all registered transformer names."""
        return list(set(self._transformers.keys()) | set(self._factories.keys()))


# Global registry instance
_default_registry = TransformerRegistry()


def get_default_registry() -> TransformerRegistry:
    """Get the default global transformer registry."""
    return _default_registry


def register_transformer(transformer: Transformer) -> None:
    """Register a transformer in the default registry."""
    _default_registry.register(transformer)


def get_transformer(name: str) -> Transformer | None:
    """Get a transformer from the default registry."""
    return _default_registry.get(name)


def get_all_transformers() -> list[Transformer]:
    """Get all transformers from the default registry."""
    return _default_registry.get_all()
