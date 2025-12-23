"""Custom sqlglot dialects for TrinityCore SQL processing."""

from trinity_postgres_tools.dialects.trinitycore_mysql import (
    TrinityCoreMySQL,
    parse_mysql,
    register_dialect,
    transpile_to_postgres,
)

__all__ = [
    "TrinityCoreMySQL",
    "parse_mysql",
    "register_dialect",
    "transpile_to_postgres",
]
