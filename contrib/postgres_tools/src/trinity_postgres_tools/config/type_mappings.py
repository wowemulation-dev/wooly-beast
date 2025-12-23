"""
Declarative type mapping registry for MySQL to PostgreSQL conversion.

This registry defines how MySQL data types map to PostgreSQL equivalents,
including handling for unsigned types and size specifiers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeMapping:
    """
    Mapping definition for a MySQL type to PostgreSQL.

    Attributes:
        postgres: The PostgreSQL type to use
        unsigned_postgres: PostgreSQL type for UNSIGNED variant (if different)
        preserve_size: Whether to preserve size specifier (e.g., VARCHAR(255))
        notes: Documentation about the conversion
    """

    postgres: str
    unsigned_postgres: str | None = None
    preserve_size: bool = False
    notes: str = ""

    def get_postgres_type(self, unsigned: bool = False) -> str:
        """Get the appropriate PostgreSQL type."""
        if unsigned and self.unsigned_postgres:
            return self.unsigned_postgres
        return self.postgres


# MySQL integer types
# Note: MySQL's UNSIGNED integers need upcasting because PostgreSQL doesn't have unsigned
# - TINYINT UNSIGNED (0-255) fits in SMALLINT (-32768 to 32767)
# - SMALLINT UNSIGNED (0-65535) fits in INTEGER
# - INT UNSIGNED (0-4294967295) fits in BIGINT
# - BIGINT UNSIGNED (0-18446744073709551615) needs NUMERIC(20,0)
INTEGER_TYPES: dict[str, TypeMapping] = {
    "tinyint": TypeMapping(
        postgres="smallint",
        unsigned_postgres="smallint",
        notes="MySQL TINYINT is -128 to 127, PostgreSQL SMALLINT is -32768 to 32767",
    ),
    "smallint": TypeMapping(
        postgres="smallint",
        unsigned_postgres="integer",
        notes="UNSIGNED needs INTEGER to hold 0-65535",
    ),
    "mediumint": TypeMapping(
        postgres="integer",
        unsigned_postgres="integer",
        notes="MySQL MEDIUMINT (-8388608 to 8388607) fits in INTEGER",
    ),
    "int": TypeMapping(
        postgres="integer",
        unsigned_postgres="bigint",
        notes="UNSIGNED needs BIGINT to hold 0-4294967295",
    ),
    "integer": TypeMapping(
        postgres="integer",
        unsigned_postgres="bigint",
        notes="Alias for INT",
    ),
    "bigint": TypeMapping(
        postgres="bigint",
        unsigned_postgres="bigint",  # Note: might overflow for very large unsigned values
        notes="UNSIGNED BIGINT may overflow; consider NUMERIC(20,0) for full range",
    ),
}

# MySQL floating-point types
FLOAT_TYPES: dict[str, TypeMapping] = {
    "float": TypeMapping(
        postgres="real",
        notes="MySQL FLOAT maps to PostgreSQL REAL (4-byte)",
    ),
    "double": TypeMapping(
        postgres="double precision",
        notes="MySQL DOUBLE maps to PostgreSQL DOUBLE PRECISION (8-byte)",
    ),
    "double precision": TypeMapping(
        postgres="double precision",
        notes="Standard SQL name",
    ),
    "real": TypeMapping(
        postgres="real",
        notes="Standard SQL name",
    ),
    "decimal": TypeMapping(
        postgres="decimal",
        preserve_size=True,
        notes="Preserves precision and scale: DECIMAL(10,2)",
    ),
    "numeric": TypeMapping(
        postgres="numeric",
        preserve_size=True,
        notes="Standard SQL name, alias for DECIMAL",
    ),
}

# MySQL string types
STRING_TYPES: dict[str, TypeMapping] = {
    "char": TypeMapping(
        postgres="char",
        preserve_size=True,
        notes="Fixed-length string: CHAR(10)",
    ),
    "varchar": TypeMapping(
        postgres="varchar",
        preserve_size=True,
        notes="Variable-length string: VARCHAR(255)",
    ),
    "tinytext": TypeMapping(
        postgres="text",
        notes="All MySQL TEXT variants become PostgreSQL TEXT",
    ),
    "text": TypeMapping(
        postgres="text",
        notes="Standard TEXT type",
    ),
    "mediumtext": TypeMapping(
        postgres="text",
        notes="PostgreSQL TEXT has no size limit",
    ),
    "longtext": TypeMapping(
        postgres="text",
        notes="PostgreSQL TEXT has no size limit",
    ),
}

# MySQL binary types
BINARY_TYPES: dict[str, TypeMapping] = {
    "binary": TypeMapping(
        postgres="bytea",
        notes="Fixed-length binary",
    ),
    "varbinary": TypeMapping(
        postgres="bytea",
        notes="Variable-length binary",
    ),
    "tinyblob": TypeMapping(
        postgres="bytea",
        notes="All BLOB variants become BYTEA",
    ),
    "blob": TypeMapping(
        postgres="bytea",
        notes="Standard BLOB",
    ),
    "mediumblob": TypeMapping(
        postgres="bytea",
        notes="PostgreSQL BYTEA has no size limit",
    ),
    "longblob": TypeMapping(
        postgres="bytea",
        notes="PostgreSQL BYTEA has no size limit",
    ),
}

# MySQL date/time types
DATETIME_TYPES: dict[str, TypeMapping] = {
    "date": TypeMapping(
        postgres="date",
        notes="Standard SQL DATE",
    ),
    "time": TypeMapping(
        postgres="time",
        notes="Standard SQL TIME",
    ),
    "datetime": TypeMapping(
        postgres="timestamp without time zone",
        notes="MySQL DATETIME becomes TIMESTAMP WITHOUT TIME ZONE",
    ),
    "timestamp": TypeMapping(
        postgres="timestamp without time zone",
        notes="MySQL TIMESTAMP also becomes TIMESTAMP WITHOUT TIME ZONE",
    ),
    "year": TypeMapping(
        postgres="smallint",
        notes="MySQL YEAR(4) stored as integer",
    ),
}

# MySQL special types
SPECIAL_TYPES: dict[str, TypeMapping] = {
    "enum": TypeMapping(
        postgres="text",
        notes="ENUM becomes TEXT; consider PostgreSQL ENUM type for strict validation",
    ),
    "set": TypeMapping(
        postgres="text",
        notes="SET becomes TEXT; consider TEXT[] for array semantics",
    ),
    "json": TypeMapping(
        postgres="jsonb",
        notes="MySQL JSON maps to PostgreSQL JSONB for indexing support",
    ),
    "bit": TypeMapping(
        postgres="bit",
        preserve_size=True,
        notes="BIT(n) preserved",
    ),
    "bool": TypeMapping(
        postgres="boolean",
        notes="MySQL BOOL/BOOLEAN (aliases for TINYINT(1))",
    ),
    "boolean": TypeMapping(
        postgres="boolean",
        notes="MySQL BOOL/BOOLEAN",
    ),
}

# Combined registry
TYPE_MAPPINGS: dict[str, TypeMapping] = {
    **INTEGER_TYPES,
    **FLOAT_TYPES,
    **STRING_TYPES,
    **BINARY_TYPES,
    **DATETIME_TYPES,
    **SPECIAL_TYPES,
}


def get_type_mapping(mysql_type: str) -> TypeMapping | None:
    """
    Look up a type mapping by MySQL type name.

    Args:
        mysql_type: MySQL type name (case-insensitive)

    Returns:
        TypeMapping if found, None otherwise
    """
    return TYPE_MAPPINGS.get(mysql_type.lower())


def convert_type(mysql_type: str, unsigned: bool = False) -> str | None:
    """
    Convert a MySQL type to PostgreSQL.

    Args:
        mysql_type: MySQL type name
        unsigned: Whether the type is UNSIGNED

    Returns:
        PostgreSQL type name, or None if no mapping exists
    """
    mapping = get_type_mapping(mysql_type)
    if mapping:
        return mapping.get_postgres_type(unsigned)
    return None
