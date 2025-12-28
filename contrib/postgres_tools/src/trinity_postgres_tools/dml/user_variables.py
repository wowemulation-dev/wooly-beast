"""
MySQL user variable expansion for PostgreSQL conversion.

MySQL supports user-defined variables like @OGUID that can be set with
SET @OGUID := 94047; and referenced later. PostgreSQL doesn't support this
syntax, so we expand variables inline by replacing references with values.

Example:
    SET @OGUID := 94047;
    SET @EVENT := 2;
    INSERT INTO tbl (guid) VALUES (@OGUID+0), (@OGUID+1);

Becomes:
    INSERT INTO tbl (guid) VALUES (94047+0), (94047+1);
"""

import re


def expand_user_variables(sql: str) -> str:
    """
    Expand MySQL user variables by replacing references with values.

    This function:
    1. Finds all SET @VAR := value; or SET @VAR = value; statements
    2. Stores the variable-value mappings
    3. Replaces all @VAR references with their values
    4. Removes the SET statements

    Args:
        sql: SQL content with MySQL user variables

    Returns:
        SQL with variables expanded inline
    """
    # Pattern for SET @VAR := value; or SET @VAR = value;
    # Captures variable name and value (which can be complex expressions)
    set_pattern = re.compile(
        r"SET\s+@(\w+)\s*:?=\s*([^;]+?)\s*;",
        re.IGNORECASE,
    )

    # First pass: collect all variable definitions
    variables: dict[str, str] = {}
    for match in set_pattern.finditer(sql):
        var_name = match.group(1).upper()  # Normalize to uppercase
        var_value = match.group(2).strip()
        variables[var_name] = var_value

    if not variables:
        return sql  # No variables to expand

    # Second pass: remove SET statements
    result = set_pattern.sub("", sql)

    # Third pass: replace variable references
    # Pattern matches @VAR (case-insensitive)
    for var_name, var_value in variables.items():
        # Replace @VAR with value, preserving case-insensitivity
        var_pattern = re.compile(rf"@{var_name}\b", re.IGNORECASE)
        result = var_pattern.sub(var_value, result)

    # Clean up any leftover empty lines from SET statement removal
    result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)

    return result


def has_user_variables(sql: str) -> bool:
    """
    Check if SQL contains MySQL user variable syntax.

    Args:
        sql: SQL content to check

    Returns:
        True if user variables are present
    """
    # Check for SET @var or @var references
    return bool(re.search(r"@\w+", sql))


def get_variable_definitions(sql: str) -> dict[str, str]:
    """
    Extract user variable definitions from SQL.

    Args:
        sql: SQL content with SET @VAR := value; statements

    Returns:
        Dictionary mapping variable names to values
    """
    set_pattern = re.compile(
        r"SET\s+@(\w+)\s*:?=\s*([^;]+?)\s*;",
        re.IGNORECASE,
    )

    variables: dict[str, str] = {}
    for match in set_pattern.finditer(sql):
        var_name = match.group(1).upper()
        var_value = match.group(2).strip()
        variables[var_name] = var_value

    return variables
