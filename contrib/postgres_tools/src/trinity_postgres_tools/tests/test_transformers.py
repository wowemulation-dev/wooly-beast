"""Tests for AST transformers."""

import sqlglot
from sqlglot import exp

from trinity_postgres_tools.pipeline.context import ConversionContext, ConversionOptions
from trinity_postgres_tools.transformers.base import BaseTransformer, transform_tree
from trinity_postgres_tools.transformers.registry import TransformerRegistry
from trinity_postgres_tools.transformers.schema import (
    CharsetRemover,
    EngineRemover,
    get_schema_transformers,
)
from trinity_postgres_tools.transformers.types import TypeTransformer


class TestTransformerRegistry:
    """Test transformer registry functionality."""

    def test_register_and_get(self):
        """Can register and retrieve transformers."""
        registry = TransformerRegistry()

        class DummyTransformer(BaseTransformer):
            @property
            def name(self) -> str:
                return "dummy"

            def can_transform(self, node: exp.Expression) -> bool:
                return False

            def transform(
                self, node: exp.Expression, ctx: ConversionContext
            ) -> exp.Expression | None:
                return node

        transformer = DummyTransformer()
        registry.register(transformer)

        assert registry.get("dummy") is transformer
        assert registry.get("nonexistent") is None

    def test_register_factory(self):
        """Can register factory functions."""
        registry = TransformerRegistry()
        created = []

        def factory():
            class LazyTransformer(BaseTransformer):
                @property
                def name(self) -> str:
                    return "lazy"

                def can_transform(self, node: exp.Expression) -> bool:
                    return False

                def transform(
                    self, node: exp.Expression, ctx: ConversionContext
                ) -> exp.Expression | None:
                    return node

            t = LazyTransformer()
            created.append(t)
            return t

        registry.register_factory("lazy", factory)

        # Factory not called yet
        assert len(created) == 0

        # Get triggers factory
        result = registry.get("lazy")
        assert len(created) == 1
        assert result is created[0]

        # Second get returns same instance
        result2 = registry.get("lazy")
        assert len(created) == 1
        assert result2 is result

    def test_get_all(self):
        """Can get all transformers."""
        registry = TransformerRegistry()

        class T1(BaseTransformer):
            @property
            def name(self) -> str:
                return "t1"

            def can_transform(self, node: exp.Expression) -> bool:
                return False

            def transform(
                self, node: exp.Expression, ctx: ConversionContext
            ) -> exp.Expression | None:
                return node

        class T2(BaseTransformer):
            @property
            def name(self) -> str:
                return "t2"

            def can_transform(self, node: exp.Expression) -> bool:
                return False

            def transform(
                self, node: exp.Expression, ctx: ConversionContext
            ) -> exp.Expression | None:
                return node

        registry.register(T1())
        registry.register(T2())

        all_transformers = registry.get_all()
        assert len(all_transformers) == 2

    def test_names(self):
        """Can get all transformer names."""
        registry = TransformerRegistry()

        class T1(BaseTransformer):
            @property
            def name(self) -> str:
                return "transformer_a"

            def can_transform(self, node: exp.Expression) -> bool:
                return False

            def transform(
                self, node: exp.Expression, ctx: ConversionContext
            ) -> exp.Expression | None:
                return node

        registry.register(T1())
        registry.register_factory("transformer_b", lambda: T1())

        names = registry.names()
        assert "transformer_a" in names
        assert "transformer_b" in names


class TestTypeTransformer:
    """Test type transformation."""

    def test_can_transform_data_type(self):
        """TypeTransformer handles DataType nodes."""
        transformer = TypeTransformer()
        data_type = exp.DataType(this=exp.DataType.Type.INT)
        assert transformer.can_transform(data_type)

    def test_ignores_other_nodes(self):
        """TypeTransformer ignores non-DataType nodes."""
        transformer = TypeTransformer()
        literal = exp.Literal.number(42)
        assert not transformer.can_transform(literal)


class TestSchemaTransformers:
    """Test schema-level transformers."""

    def test_engine_remover_removes_engine(self):
        """EngineRemover returns None to remove ENGINE."""
        transformer = EngineRemover()
        ctx = ConversionContext()

        engine_prop = exp.EngineProperty(this=exp.Literal.string("InnoDB"))

        result = transformer.transform(engine_prop, ctx)
        assert result is None
        assert ctx.stats.artifacts_removed.get("ENGINE", 0) == 1

    def test_engine_remover_respects_option(self):
        """EngineRemover respects remove_engine_specs option."""
        transformer = EngineRemover()
        options = ConversionOptions(remove_engine_specs=False)
        ctx = ConversionContext(options=options)

        engine_prop = exp.EngineProperty(this=exp.Literal.string("InnoDB"))

        result = transformer.transform(engine_prop, ctx)
        assert result is engine_prop  # Not removed

    def test_charset_remover_removes_charset(self):
        """CharsetRemover returns None to remove CHARACTER SET."""
        transformer = CharsetRemover()
        ctx = ConversionContext()

        charset_prop = exp.CharacterSetProperty(this=exp.Literal.string("utf8mb4"))

        result = transformer.transform(charset_prop, ctx)
        assert result is None
        assert ctx.stats.artifacts_removed.get("CHARACTER SET", 0) == 1

    def test_get_schema_transformers(self):
        """get_schema_transformers returns all schema transformers."""
        transformers = get_schema_transformers()
        assert len(transformers) >= 4  # ENGINE, CHARSET, COLLATE, COMMENT, etc.

        names = [t.name for t in transformers]
        assert "engine_remover" in names
        assert "charset_remover" in names
        assert "collate_remover" in names


class TestTransformTree:
    """Test the transform_tree function."""

    def test_applies_transformers(self):
        """transform_tree applies matching transformers."""
        ctx = ConversionContext()

        # Create a simple tree
        parsed = sqlglot.parse_one(
            "CREATE TABLE t (id INT) ENGINE=InnoDB", dialect="mysql"
        )

        # Apply schema transformers
        transformers = get_schema_transformers()
        result = transform_tree(parsed, transformers, ctx)

        # ENGINE should be removed
        assert result is not None
        result_sql = result.sql(dialect="postgres")
        assert "ENGINE" not in result_sql.upper()

    def test_handles_empty_transformers(self):
        """transform_tree works with no transformers."""
        ctx = ConversionContext()
        parsed = sqlglot.parse_one("SELECT 1")

        result = transform_tree(parsed, [], ctx)
        assert result is parsed


class TestSqlglotParsing:
    """Test sqlglot parsing of MySQL statements."""

    def test_parse_simple_create(self):
        """Can parse simple CREATE TABLE."""
        sql = "CREATE TABLE test (id INT PRIMARY KEY)"
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        assert parsed is not None
        assert isinstance(parsed, exp.Create)

    def test_parse_create_with_engine(self):
        """Can parse CREATE TABLE with ENGINE."""
        sql = "CREATE TABLE test (id INT) ENGINE=InnoDB"
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        assert parsed is not None

    def test_parse_create_with_charset(self):
        """Can parse CREATE TABLE with CHARACTER SET."""
        sql = "CREATE TABLE test (id INT) DEFAULT CHARSET=utf8mb4"
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        assert parsed is not None

    def test_transpile_simple(self):
        """Can transpile simple statement to PostgreSQL."""
        sql = "SELECT * FROM test WHERE id = 1"
        result = sqlglot.transpile(sql, read="mysql", write="postgres")[0]
        assert result is not None
        assert "SELECT" in result

    def test_transpile_types(self):
        """Transpilation converts some types."""
        sql = "CREATE TABLE test (data LONGTEXT)"
        result = sqlglot.transpile(sql, read="mysql", write="postgres")[0]
        # sqlglot should convert LONGTEXT to TEXT
        assert "TEXT" in result.upper()
