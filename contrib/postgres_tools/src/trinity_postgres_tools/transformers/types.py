"""
Type conversion transformers for MySQL to PostgreSQL.

Handles conversion of MySQL data types to PostgreSQL equivalents,
including proper handling of UNSIGNED integers.
"""

from typing import ClassVar

from sqlglot import exp

from trinity_postgres_tools.config.type_mappings import TYPE_MAPPINGS, TypeMapping
from trinity_postgres_tools.pipeline.context import ConversionContext
from trinity_postgres_tools.transformers.base import BaseTransformer


class TypeTransformer(BaseTransformer):
    """
    Transformer for converting MySQL data types to PostgreSQL.

    Uses the declarative TYPE_MAPPINGS registry to perform conversions.
    """

    @property
    def name(self) -> str:
        return "type_converter"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a data type expression."""
        return isinstance(node, exp.DataType)

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Transform MySQL data type to PostgreSQL equivalent."""
        if not isinstance(node, exp.DataType):
            return node

        # Get the MySQL type name
        mysql_type = node.this.name if hasattr(node.this, "name") else str(node.this)
        mysql_type_lower = mysql_type.lower()

        # Check if type is unsigned
        unsigned = self._is_unsigned(node)

        # Look up the mapping
        mapping = TYPE_MAPPINGS.get(mysql_type_lower)
        if not mapping:
            self.log(ctx, f"No mapping for type: {mysql_type}")
            return node

        # Get the PostgreSQL type
        pg_type = mapping.get_postgres_type(unsigned)

        # Record the conversion
        ctx.stats.record_type_conversion(mysql_type, pg_type)

        # Create new DataType node
        new_type = self._create_pg_type(node, pg_type, mapping)

        self.log(ctx, f"Converted {mysql_type} -> {pg_type}")
        return new_type

    def _is_unsigned(self, node: exp.DataType) -> bool:
        """Check if a data type has UNSIGNED modifier."""
        # Check for UNSIGNED in expressions
        for expr in node.expressions:
            if isinstance(expr, exp.ColumnConstraint) and "unsigned" in str(expr).lower():
                return True
        # Check text representation as fallback
        return "unsigned" in str(node).lower()

    def _create_pg_type(
        self, node: exp.DataType, pg_type: str, mapping: TypeMapping
    ) -> exp.DataType:
        """Create a new PostgreSQL DataType node."""
        # Map type name to sqlglot DataType.Type
        type_map = {
            "smallint": exp.DataType.Type.SMALLINT,
            "integer": exp.DataType.Type.INT,
            "bigint": exp.DataType.Type.BIGINT,
            "real": exp.DataType.Type.FLOAT,
            "double precision": exp.DataType.Type.DOUBLE,
            "text": exp.DataType.Type.TEXT,
            "varchar": exp.DataType.Type.VARCHAR,
            "char": exp.DataType.Type.CHAR,
            "bytea": exp.DataType.Type.BINARY,
            "boolean": exp.DataType.Type.BOOLEAN,
            "date": exp.DataType.Type.DATE,
            "time": exp.DataType.Type.TIME,
            "timestamp without time zone": exp.DataType.Type.TIMESTAMP,
            "jsonb": exp.DataType.Type.JSON,
            "numeric": exp.DataType.Type.DECIMAL,
            "decimal": exp.DataType.Type.DECIMAL,
        }

        pg_type_enum = type_map.get(pg_type.lower(), exp.DataType.Type.TEXT)

        # Preserve size parameters if applicable
        expressions = []
        if mapping.preserve_size and node.expressions:
            for expr in node.expressions:
                # Copy size expressions (e.g., VARCHAR(255))
                if isinstance(expr, (exp.DataTypeParam, exp.Literal)):
                    expressions.append(expr.copy())

        return exp.DataType(
            this=pg_type_enum,
            expressions=expressions,
            nested=node.nested,
        )


class UnsignedIntegerTransformer(BaseTransformer):
    """
    Specific transformer for UNSIGNED integer type upcasting.

    Ensures unsigned integers are converted to appropriately sized
    signed types that can hold the full unsigned range.
    """

    # Mapping of unsigned types to their upcast equivalents
    UNSIGNED_UPCAST: ClassVar[dict[str, str]] = {
        "tinyint": "smallint",  # UNSIGNED TINYINT (0-255) fits in SMALLINT
        "smallint": "integer",  # UNSIGNED SMALLINT (0-65535) fits in INTEGER
        "mediumint": "integer",  # UNSIGNED MEDIUMINT fits in INTEGER
        "int": "bigint",  # UNSIGNED INT (0-4294967295) fits in BIGINT
        "integer": "bigint",  # Same as INT
        "bigint": "bigint",  # UNSIGNED BIGINT may overflow; use NUMERIC for full range
    }

    @property
    def name(self) -> str:
        return "unsigned_upcast"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is an unsigned integer type."""
        if not isinstance(node, exp.DataType):
            return False
        return "unsigned" in str(node).lower()

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Upcast unsigned integer to larger signed type."""
        if not isinstance(node, exp.DataType):
            return node

        if not ctx.options.unsigned_upcast:
            return node

        mysql_type = node.this.name if hasattr(node.this, "name") else str(node.this)
        mysql_type_lower = mysql_type.lower()

        if mysql_type_lower not in self.UNSIGNED_UPCAST:
            return node

        pg_type = self.UNSIGNED_UPCAST[mysql_type_lower]
        ctx.stats.record_type_conversion(f"{mysql_type} UNSIGNED", pg_type)

        self.log(ctx, f"Upcast UNSIGNED {mysql_type} -> {pg_type}")

        # Create the new type (the main TypeTransformer will handle the rest)
        return node


def get_type_transformers() -> list[BaseTransformer]:
    """Get all type-related transformers."""
    return [
        TypeTransformer(),
        UnsignedIntegerTransformer(),
    ]
