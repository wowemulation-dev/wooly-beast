"""
AUTO_INCREMENT to SERIAL transformer.

Converts MySQL AUTO_INCREMENT columns to PostgreSQL SERIAL types
or IDENTITY columns depending on configuration.
"""

from sqlglot import exp

from trinity_postgres_tools.pipeline.context import ConversionContext
from trinity_postgres_tools.transformers.base import BaseTransformer


class AutoIncrementTransformer(BaseTransformer):
    """
    Transformer for converting AUTO_INCREMENT to SERIAL or IDENTITY.

    MySQL:  id INT AUTO_INCREMENT PRIMARY KEY
    PostgreSQL (SERIAL): id SERIAL PRIMARY KEY
    PostgreSQL (IDENTITY): id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
    """

    @property
    def name(self) -> str:
        return "auto_increment"

    def can_transform(self, node: exp.Expression) -> bool:
        """Check if this is a column definition with AUTO_INCREMENT."""
        if not isinstance(node, exp.ColumnDef):
            return False
        return self._has_auto_increment(node)

    def _has_auto_increment(self, node: exp.ColumnDef) -> bool:
        """Check if column has AUTO_INCREMENT constraint."""
        for constraint in node.constraints or []:
            if isinstance(constraint, exp.AutoIncrementColumnConstraint):
                return True
            # Also check text representation
            if "auto_increment" in str(constraint).lower():
                return True
        return False

    def transform(
        self, node: exp.Expression, ctx: ConversionContext
    ) -> exp.Expression | None:
        """Convert AUTO_INCREMENT column to SERIAL or IDENTITY."""
        if not isinstance(node, exp.ColumnDef):
            return node

        if not ctx.options.convert_auto_increment:
            return node

        # Record the column for later reference
        table_name = self._get_table_name(node)
        column_name = node.name
        if table_name:
            if table_name not in ctx.auto_increment_columns:
                ctx.auto_increment_columns[table_name] = []
            ctx.auto_increment_columns[table_name].append(column_name)

        self.log(ctx, f"Converting AUTO_INCREMENT: {column_name}")

        if ctx.options.use_serial:
            return self._convert_to_serial(node, ctx)
        else:
            return self._convert_to_identity(node, ctx)

    def _get_table_name(self, node: exp.ColumnDef) -> str | None:
        """Get the table name from the column's parent."""
        parent = node.parent
        while parent:
            if isinstance(parent, exp.Create):
                table = parent.this
                if isinstance(table, exp.Table):
                    return table.name
            parent = parent.parent
        return None

    def _convert_to_serial(
        self, node: exp.ColumnDef, ctx: ConversionContext
    ) -> exp.ColumnDef:
        """Convert column to SERIAL type."""
        # Determine SERIAL variant based on original type
        original_type = node.kind
        serial_type = self._get_serial_type(original_type)

        ctx.stats.record_type_conversion(
            f"{original_type} AUTO_INCREMENT", serial_type
        )

        # Create new column definition with SERIAL type
        new_constraints = []
        for constraint in node.constraints or []:
            # Remove AUTO_INCREMENT constraint
            if isinstance(constraint, exp.AutoIncrementColumnConstraint):
                continue
            if "auto_increment" in str(constraint).lower():
                continue
            new_constraints.append(constraint)

        # Create SERIAL type
        serial_type_node = exp.DataType(
            this=self._serial_to_type(serial_type),
        )

        return exp.ColumnDef(
            this=node.this,
            kind=serial_type_node,
            constraints=new_constraints,
        )

    def _convert_to_identity(
        self, node: exp.ColumnDef, ctx: ConversionContext
    ) -> exp.ColumnDef:
        """Convert column to IDENTITY column."""
        # Keep the integer type, add IDENTITY constraint
        ctx.stats.record_artifact_removed("AUTO_INCREMENT")

        new_constraints = []
        for constraint in node.constraints or []:
            if isinstance(constraint, exp.AutoIncrementColumnConstraint):
                continue
            if "auto_increment" in str(constraint).lower():
                continue
            new_constraints.append(constraint)

        # Add IDENTITY constraint
        # Note: This creates the SQL syntax for GENERATED ALWAYS AS IDENTITY
        identity = exp.IdentityColumnConstraint()
        new_constraints.append(identity)

        return exp.ColumnDef(
            this=node.this,
            kind=node.kind,
            constraints=new_constraints,
        )

    def _get_serial_type(self, original_type: exp.DataType | None) -> str:
        """Determine appropriate SERIAL variant."""
        if not original_type:
            return "SERIAL"

        type_str = str(original_type).lower()

        if "bigint" in type_str:
            return "BIGSERIAL"
        elif "smallint" in type_str or "tinyint" in type_str:
            return "SMALLSERIAL"
        else:
            return "SERIAL"

    def _serial_to_type(self, serial: str) -> exp.DataType.Type:
        """Convert SERIAL variant to DataType enum."""
        if serial == "BIGSERIAL":
            return exp.DataType.Type.BIGSERIAL
        elif serial == "SMALLSERIAL":
            return exp.DataType.Type.SMALLSERIAL
        else:
            return exp.DataType.Type.SERIAL


def get_auto_increment_transformers() -> list[BaseTransformer]:
    """Get AUTO_INCREMENT related transformers."""
    return [AutoIncrementTransformer()]
