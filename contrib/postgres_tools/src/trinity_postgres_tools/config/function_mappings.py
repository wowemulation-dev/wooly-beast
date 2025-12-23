"""
Declarative function mapping registry for MySQL to PostgreSQL conversion.

This registry defines how MySQL functions map to PostgreSQL equivalents,
including argument transformation patterns.
"""

from dataclasses import dataclass
from enum import Enum, auto


class TransformType(Enum):
    """How to transform function arguments."""

    DIRECT = auto()  # Same arguments, just rename
    TEMPLATE = auto()  # Use a template string with placeholders
    CALLABLE = auto()  # Use a custom function


@dataclass(frozen=True)
class FunctionMapping:
    """
    Mapping definition for a MySQL function to PostgreSQL.

    Attributes:
        postgres: PostgreSQL function name or template
        transform: How to handle argument transformation
        template: Template string for TEMPLATE type (uses {0}, {1}, etc.)
        notes: Documentation about the conversion
    """

    postgres: str
    transform: TransformType = TransformType.DIRECT
    template: str | None = None
    notes: str = ""


# Date/Time functions
DATETIME_FUNCTIONS: dict[str, FunctionMapping] = {
    "now": FunctionMapping(
        postgres="now",
        notes="Direct mapping",
    ),
    "current_timestamp": FunctionMapping(
        postgres="current_timestamp",
        notes="Standard SQL",
    ),
    "curdate": FunctionMapping(
        postgres="current_date",
        notes="MySQL CURDATE() -> PostgreSQL CURRENT_DATE",
    ),
    "curtime": FunctionMapping(
        postgres="current_time",
        notes="MySQL CURTIME() -> PostgreSQL CURRENT_TIME",
    ),
    "unix_timestamp": FunctionMapping(
        postgres="extract(epoch from now())",
        transform=TransformType.TEMPLATE,
        template="extract(epoch from {0})",
        notes="No args: extract(epoch from now()), with arg: extract(epoch from ts)",
    ),
    "from_unixtime": FunctionMapping(
        postgres="to_timestamp",
        notes="FROM_UNIXTIME(ts) -> to_timestamp(ts)",
    ),
    "date_format": FunctionMapping(
        postgres="to_char",
        transform=TransformType.TEMPLATE,
        template="to_char({0}, {1})",
        notes="DATE_FORMAT needs format string translation",
    ),
    "str_to_date": FunctionMapping(
        postgres="to_timestamp",
        transform=TransformType.TEMPLATE,
        template="to_timestamp({0}, {1})",
        notes="STR_TO_DATE needs format string translation",
    ),
    "datediff": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="({0}::date - {1}::date)",
        notes="DATEDIFF(a, b) -> (a::date - b::date)",
    ),
    "date_add": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="({0} + {1})",
        notes="DATE_ADD(date, INTERVAL) -> (date + INTERVAL)",
    ),
    "date_sub": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="({0} - {1})",
        notes="DATE_SUB(date, INTERVAL) -> (date - INTERVAL)",
    ),
    "timestampdiff": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="extract(epoch from ({1} - {2})) / {unit_divisor}",
        notes="Complex: TIMESTAMPDIFF(unit, t1, t2) needs unit-based division",
    ),
}

# String functions
STRING_FUNCTIONS: dict[str, FunctionMapping] = {
    "concat": FunctionMapping(
        postgres="concat",
        notes="PostgreSQL CONCAT works the same way",
    ),
    "concat_ws": FunctionMapping(
        postgres="concat_ws",
        notes="PostgreSQL CONCAT_WS works the same way",
    ),
    "length": FunctionMapping(
        postgres="length",
        notes="Direct mapping",
    ),
    "char_length": FunctionMapping(
        postgres="char_length",
        notes="Direct mapping",
    ),
    "character_length": FunctionMapping(
        postgres="character_length",
        notes="Standard SQL",
    ),
    "substring": FunctionMapping(
        postgres="substring",
        notes="Direct mapping",
    ),
    "substr": FunctionMapping(
        postgres="substr",
        notes="Direct mapping",
    ),
    "left": FunctionMapping(
        postgres="left",
        notes="Direct mapping",
    ),
    "right": FunctionMapping(
        postgres="right",
        notes="Direct mapping",
    ),
    "trim": FunctionMapping(
        postgres="trim",
        notes="Direct mapping",
    ),
    "ltrim": FunctionMapping(
        postgres="ltrim",
        notes="Direct mapping",
    ),
    "rtrim": FunctionMapping(
        postgres="rtrim",
        notes="Direct mapping",
    ),
    "upper": FunctionMapping(
        postgres="upper",
        notes="Direct mapping",
    ),
    "lower": FunctionMapping(
        postgres="lower",
        notes="Direct mapping",
    ),
    "replace": FunctionMapping(
        postgres="replace",
        notes="Direct mapping",
    ),
    "reverse": FunctionMapping(
        postgres="reverse",
        notes="Direct mapping",
    ),
    "lpad": FunctionMapping(
        postgres="lpad",
        notes="Direct mapping",
    ),
    "rpad": FunctionMapping(
        postgres="rpad",
        notes="Direct mapping",
    ),
    "instr": FunctionMapping(
        postgres="position",
        transform=TransformType.TEMPLATE,
        template="position({1} in {0})",
        notes="INSTR(str, substr) -> position(substr in str)",
    ),
    "locate": FunctionMapping(
        postgres="position",
        transform=TransformType.TEMPLATE,
        template="position({0} in {1})",
        notes="LOCATE(substr, str) -> position(substr in str)",
    ),
}

# Numeric functions
NUMERIC_FUNCTIONS: dict[str, FunctionMapping] = {
    "abs": FunctionMapping(postgres="abs", notes="Direct mapping"),
    "ceil": FunctionMapping(postgres="ceil", notes="Direct mapping"),
    "ceiling": FunctionMapping(postgres="ceiling", notes="Direct mapping"),
    "floor": FunctionMapping(postgres="floor", notes="Direct mapping"),
    "round": FunctionMapping(postgres="round", notes="Direct mapping"),
    "truncate": FunctionMapping(
        postgres="trunc",
        notes="MySQL TRUNCATE -> PostgreSQL TRUNC",
    ),
    "mod": FunctionMapping(postgres="mod", notes="Direct mapping"),
    "pow": FunctionMapping(postgres="pow", notes="Direct mapping"),
    "power": FunctionMapping(postgres="power", notes="Direct mapping"),
    "sqrt": FunctionMapping(postgres="sqrt", notes="Direct mapping"),
    "sign": FunctionMapping(postgres="sign", notes="Direct mapping"),
    "rand": FunctionMapping(
        postgres="random",
        notes="MySQL RAND() -> PostgreSQL random()",
    ),
    "greatest": FunctionMapping(postgres="greatest", notes="Direct mapping"),
    "least": FunctionMapping(postgres="least", notes="Direct mapping"),
}

# Conditional functions
CONDITIONAL_FUNCTIONS: dict[str, FunctionMapping] = {
    "if": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="CASE WHEN {0} THEN {1} ELSE {2} END",
        notes="IF(cond, then, else) -> CASE WHEN cond THEN then ELSE else END",
    ),
    "ifnull": FunctionMapping(
        postgres="coalesce",
        notes="IFNULL(a, b) -> COALESCE(a, b)",
    ),
    "nullif": FunctionMapping(
        postgres="nullif",
        notes="Direct mapping",
    ),
    "coalesce": FunctionMapping(
        postgres="coalesce",
        notes="Direct mapping",
    ),
    "isnull": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="({0} IS NULL)",
        notes="ISNULL(expr) -> (expr IS NULL)",
    ),
}

# Type conversion functions
CONVERSION_FUNCTIONS: dict[str, FunctionMapping] = {
    "cast": FunctionMapping(
        postgres="cast",
        notes="CAST syntax is the same, but types need mapping",
    ),
    "convert": FunctionMapping(
        postgres="cast",
        transform=TransformType.TEMPLATE,
        template="CAST({0} AS {1})",
        notes="CONVERT(expr, type) -> CAST(expr AS type)",
    ),
    "binary": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="{0}::bytea",
        notes="BINARY expr -> expr::bytea",
    ),
}

# Aggregate functions (mostly direct mappings)
AGGREGATE_FUNCTIONS: dict[str, FunctionMapping] = {
    "count": FunctionMapping(postgres="count", notes="Direct mapping"),
    "sum": FunctionMapping(postgres="sum", notes="Direct mapping"),
    "avg": FunctionMapping(postgres="avg", notes="Direct mapping"),
    "min": FunctionMapping(postgres="min", notes="Direct mapping"),
    "max": FunctionMapping(postgres="max", notes="Direct mapping"),
    "group_concat": FunctionMapping(
        postgres="string_agg",
        transform=TransformType.TEMPLATE,
        template="string_agg({0}::text, ',')",
        notes="GROUP_CONCAT(col) -> string_agg(col::text, ',')",
    ),
}

# MySQL-specific functions that need special handling
MYSQL_SPECIFIC: dict[str, FunctionMapping] = {
    "uuid": FunctionMapping(
        postgres="gen_random_uuid",
        notes="Requires pgcrypto or uuid-ossp extension",
    ),
    "uuid_short": FunctionMapping(
        postgres="",
        transform=TransformType.TEMPLATE,
        template="(extract(epoch from now()) * 1000000)::bigint",
        notes="Approximate equivalent",
    ),
    "last_insert_id": FunctionMapping(
        postgres="lastval",
        notes="LAST_INSERT_ID() -> lastval()",
    ),
    "found_rows": FunctionMapping(
        postgres="",
        notes="No direct equivalent; requires query restructuring",
    ),
    "row_count": FunctionMapping(
        postgres="",
        notes="No direct equivalent; use GET DIAGNOSTICS in plpgsql",
    ),
}

# Combined registry
FUNCTION_MAPPINGS: dict[str, FunctionMapping] = {
    **DATETIME_FUNCTIONS,
    **STRING_FUNCTIONS,
    **NUMERIC_FUNCTIONS,
    **CONDITIONAL_FUNCTIONS,
    **CONVERSION_FUNCTIONS,
    **AGGREGATE_FUNCTIONS,
    **MYSQL_SPECIFIC,
}


def get_function_mapping(mysql_func: str) -> FunctionMapping | None:
    """
    Look up a function mapping by MySQL function name.

    Args:
        mysql_func: MySQL function name (case-insensitive)

    Returns:
        FunctionMapping if found, None otherwise
    """
    return FUNCTION_MAPPINGS.get(mysql_func.lower())


def has_direct_mapping(mysql_func: str) -> bool:
    """Check if a function has a direct (same-name) mapping."""
    mapping = get_function_mapping(mysql_func)
    if not mapping:
        return False
    return mapping.transform == TransformType.DIRECT
