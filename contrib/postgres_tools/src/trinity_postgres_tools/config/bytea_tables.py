"""
Configuration for tables with BYTEA columns that contain hex data.

When MySQL INSERT statements use hex literals (0xDEADBEEF) for binary columns,
PostgreSQL requires decode('DEADBEEF', 'hex') instead of integer conversion.

This file lists tables and columns where hex literals should be converted to
decode() calls instead of decimal integers.

Format:
    BYTEA_COLUMNS = {
        "table_name": ["column_name1", "column_name2", ...],
    }

The column positions are determined at runtime by parsing the INSERT statement.
"""

# Tables with binary columns that store hex data
# Keys are lowercase table names, values are lists of lowercase column names
BYTEA_COLUMNS: dict[str, list[str]] = {
    # Auth database tables
    "build_auth_key": ["key"],  # binary(16) - authentication key
    "build_executable_hash": ["executablehash"],  # binary(20) - SHA1 hash

    # World database tables
    "warden_checks": ["data", "result"],  # binary(24), varbinary(24)
}


def get_bytea_column_indices(table_name: str, columns: list[str]) -> set[int]:
    """
    Get the indices of BYTEA columns for a given table and column list.

    Args:
        table_name: The table name (case-insensitive)
        columns: List of column names from the INSERT statement

    Returns:
        Set of 0-based column indices that contain BYTEA data
    """
    table_lower = table_name.lower()
    if table_lower not in BYTEA_COLUMNS:
        return set()

    bytea_cols = {col.lower() for col in BYTEA_COLUMNS[table_lower]}
    indices = set()

    for i, col in enumerate(columns):
        if col.lower() in bytea_cols:
            indices.add(i)

    return indices


def is_bytea_table(table_name: str) -> bool:
    """
    Check if a table has any BYTEA columns configured.

    Args:
        table_name: The table name (case-insensitive)

    Returns:
        True if the table has BYTEA columns that need special handling
    """
    return table_name.lower() in BYTEA_COLUMNS
