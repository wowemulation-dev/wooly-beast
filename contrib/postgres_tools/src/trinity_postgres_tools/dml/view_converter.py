"""
MySQL VIEW to PostgreSQL VIEW converter.

MySQL VIEWs in mysqldump are wrapped in conditional comments:
  /*!50001 CREATE ALGORITHM=UNDEFINED */
  /*!50013 */
  /*!50001 VIEW `view_name` AS select ... */

This module extracts and converts these to PostgreSQL CREATE VIEW statements.
"""

import re


def extract_views_from_conditional_comments(sql: str) -> tuple[str, list[str]]:
    """
    Extract VIEW definitions from MySQL conditional comments.

    MySQL views appear in two forms in mysqldump:
    1. Temporary placeholder (early in dump):
       /*!50001 CREATE VIEW `name` AS SELECT 1 AS `col1`, 1 AS `col2`, ...*/;

    2. Final definition (end of dump):
       /*!50001 CREATE ALGORITHM=UNDEFINED */
       /*!50013 */
       /*!50001 VIEW `name` AS select ... */;

    This function extracts the final definitions (form 2) which contain
    the actual view logic.

    Args:
        sql: Full SQL dump content

    Returns:
        Tuple of (sql with view comments removed, list of extracted view definitions)
    """
    extracted_views: list[str] = []

    # Pattern to match the full view definition block
    # /*!50001 CREATE ALGORITHM=UNDEFINED */
    # /*!50013 */  (or /*!50013 DEFINER=... */)
    # /*!50001 VIEW `name` AS ... */;
    #
    # The pattern needs to handle multiline content in the view body
    view_block_pattern = re.compile(
        r"/\*!50001\s+CREATE\s+ALGORITHM\s*=\s*\w+\s*\*/\s*"
        r"/\*!50013[^*]*\*/\s*"
        r"/\*!50001\s+VIEW\s+(`\w+`)\s+AS\s+(.*?)\s*\*/\s*;",
        re.IGNORECASE | re.DOTALL,
    )

    def extract_view(match: re.Match[str]) -> str:
        view_name = match.group(1)
        view_body = match.group(2)
        extracted_views.append(f"CREATE VIEW {view_name} AS {view_body};")
        return ""  # Remove from original SQL

    sql = view_block_pattern.sub(extract_view, sql)

    # Also handle placeholder views (temporary structure)
    # /*!50001 CREATE VIEW `name` AS SELECT 1 AS `col`, ...*/;
    # These should be removed (not converted) since they're just placeholders
    placeholder_pattern = re.compile(
        r"/\*!50001\s+CREATE\s+VIEW\s+`\w+`\s+AS\s+SELECT\s+"
        r"(?:1\s+AS\s+`\w+`\s*,?\s*)+\*/\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    sql = placeholder_pattern.sub("", sql)

    # Remove DROP VIEW IF EXISTS comments
    drop_view_pattern = re.compile(
        r"/\*!50001\s+DROP\s+VIEW\s+IF\s+EXISTS\s+`\w+`\s*\*/\s*;?",
        re.IGNORECASE,
    )
    sql = drop_view_pattern.sub("", sql)

    return sql, extracted_views


def convert_mysql_view_to_postgres(view_sql: str) -> str:
    """
    Convert a MySQL VIEW definition to PostgreSQL syntax.

    Handles:
    - Double-quoted strings -> single-quoted strings (FIRST, before backtick conversion)
    - Backtick identifiers -> double-quoted (PostgreSQL case-preserving)
    - CASE expressions (PostgreSQL compatible)
    - Column references

    Args:
        view_sql: MySQL CREATE VIEW statement

    Returns:
        PostgreSQL CREATE VIEW statement
    """
    # IMPORTANT: Convert double-quoted strings to single-quoted strings FIRST
    # MySQL allows both 'string' and "string" for string literals
    # PostgreSQL uses single quotes for strings (double quotes are identifiers)
    # We must do this BEFORE converting backticks to double-quotes
    def convert_dquoted_string(match: re.Match[str]) -> str:
        inner = match.group(1)
        # Escape any single quotes by doubling them (PostgreSQL style)
        inner = inner.replace("'", "''")
        return f"'{inner}'"

    # Pattern matches double-quoted strings (simple version for view bodies)
    dquote_pattern = r'"([^"]*)"'
    view_sql = re.sub(dquote_pattern, convert_dquoted_string, view_sql)

    # Convert backticks to PostgreSQL identifiers
    # MySQL: `table`.`column` -> PostgreSQL: table.column (lowercase)
    # MySQL: `Permission ID` -> PostgreSQL: "permission id" (needs quotes due to space)
    # PostgreSQL normalizes unquoted identifiers to lowercase, so we lowercase
    # all identifiers to match our DDL schema (which also uses lowercase).
    def convert_backtick_identifier(match: re.Match[str]) -> str:
        ident = match.group(1).lower()
        # If identifier contains spaces or special chars, it needs double quotes
        if not re.match(r"^[a-z_][a-z0-9_]*$", ident):
            return f'"{ident}"'
        return ident

    view_sql = re.sub(r"`([^`]+)`", convert_backtick_identifier, view_sql)

    # Convert MySQL IFNULL to PostgreSQL COALESCE
    view_sql = re.sub(r"\bifnull\s*\(", "COALESCE(", view_sql, flags=re.IGNORECASE)

    # Fix COALESCE type mismatch: when first arg is column and second is string literal
    # Cast the column to text so types are compatible
    # Pattern: COALESCE(table.column, 'string') -> COALESCE(table.column::text, 'string')
    view_sql = re.sub(
        r"\bCOALESCE\s*\(\s*([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\s*,\s*'",
        r"COALESCE(\1::text,'",
        view_sql,
        flags=re.IGNORECASE,
    )

    # Convert MySQL FROM_UNIXTIME to PostgreSQL TO_TIMESTAMP
    # MySQL: FROM_UNIXTIME(unix_timestamp) -> PostgreSQL: TO_TIMESTAMP(unix_timestamp)
    view_sql = re.sub(r"\bfrom_unixtime\s*\(", "to_timestamp(", view_sql, flags=re.IGNORECASE)

    # Fix CASE type unification: Cast ELSE column references to text
    # PostgreSQL requires all CASE branches to return compatible types.
    # When THEN returns 'string' but ELSE returns an integer column, we must cast.
    # Pattern: else table.column end) -> else table.column::text end)
    view_sql = re.sub(
        r"\belse\s+([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\s+end\)",
        r"else \1::text end)",
        view_sql,
        flags=re.IGNORECASE,
    )

    # Fix MySQL's loose GROUP BY behavior for PostgreSQL strict mode
    # MySQL allows selecting non-aggregated columns not in GROUP BY when ONLY_FULL_GROUP_BY is off
    # PostgreSQL requires all non-aggregated SELECT columns to be in GROUP BY
    view_sql = _fix_group_by_clause(view_sql)

    # Ensure CREATE OR REPLACE VIEW for idempotent import
    view_sql = re.sub(
        r"^CREATE\s+VIEW\b",
        "CREATE OR REPLACE VIEW",
        view_sql,
        flags=re.IGNORECASE,
    )

    return view_sql


def _fix_group_by_clause(view_sql: str) -> str:
    """
    Fix GROUP BY clause to include all non-aggregated columns from SELECT.

    MySQL with ONLY_FULL_GROUP_BY disabled allows selecting columns not in GROUP BY.
    PostgreSQL strictly requires all non-aggregated SELECT columns to be in GROUP BY.

    This function parses the SELECT and GROUP BY, identifies missing columns,
    and adds them to the GROUP BY clause.
    """
    # Check if there's a GROUP BY clause
    group_by_match = re.search(r"\bgroup\s+by\s+([^;]+?)(?:;|\s*$)", view_sql, re.IGNORECASE)
    if not group_by_match:
        return view_sql

    # Find the SELECT clause (between "AS select" and "from")
    select_match = re.search(r"\bAS\s+select\s+(.*?)\s+from\s+", view_sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return view_sql

    select_clause = select_match.group(1)
    group_by_clause = group_by_match.group(1).strip()

    # Parse the GROUP BY columns (simple split by comma)
    group_by_cols = {col.strip().lower() for col in group_by_clause.split(",")}

    # Parse SELECT items to find non-aggregated column references
    # Aggregate functions: min, max, count, sum, avg, etc.
    aggregate_pattern = re.compile(
        r"\b(?:min|max|count|sum|avg|group_concat|coalesce)\s*\(",
        re.IGNORECASE,
    )

    # Split SELECT by comma, but be careful about nested parentheses
    select_items = _split_select_items(select_clause)

    missing_cols = []
    for item in select_items:
        # Skip if it contains an aggregate function
        if aggregate_pattern.search(item):
            continue

        # Extract the column reference (before AS alias if present)
        as_match = re.search(r"\s+AS\s+", item, re.IGNORECASE)
        if as_match:
            col_expr = item[: as_match.start()].strip()
        else:
            col_expr = item.strip()

        # Check if this column is already in GROUP BY
        col_lower = col_expr.lower()
        if col_lower not in group_by_cols:
            # Check if it's a simple column reference (table.column or column)
            if re.match(r"^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?$", col_lower):
                missing_cols.append(col_expr)

    if missing_cols:
        # Add missing columns to GROUP BY
        new_group_by = group_by_clause + "," + ",".join(missing_cols)
        view_sql = view_sql[: group_by_match.start(1)] + new_group_by + view_sql[group_by_match.end(1) :]

    return view_sql


def _split_select_items(select_clause: str) -> list[str]:
    """
    Split SELECT clause into individual items, respecting parentheses.

    Returns list of SELECT items (each may contain AS alias).
    """
    items = []
    current = ""
    paren_depth = 0

    for char in select_clause:
        if char == "(":
            paren_depth += 1
            current += char
        elif char == ")":
            paren_depth -= 1
            current += char
        elif char == "," and paren_depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        items.append(current.strip())

    return items


def process_views(sql: str) -> tuple[str, list[str]]:
    """
    Extract MySQL views and convert them to PostgreSQL format.

    This is the main entry point for view processing.

    Args:
        sql: Full SQL dump content

    Returns:
        Tuple of (sql with MySQL view syntax removed, list of PostgreSQL view statements)
    """
    # Extract views from conditional comments
    sql, mysql_views = extract_views_from_conditional_comments(sql)

    # Convert each view to PostgreSQL
    postgres_views = [convert_mysql_view_to_postgres(view) for view in mysql_views]

    return sql, postgres_views
