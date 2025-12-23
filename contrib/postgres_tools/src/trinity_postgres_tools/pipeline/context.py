"""Conversion context for tracking state through the pipeline."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class StatementType(Enum):
    """Classification of SQL statements."""

    DDL = auto()  # CREATE, ALTER, DROP, TRUNCATE
    DML = auto()  # INSERT, UPDATE, DELETE, REPLACE
    OTHER = auto()  # SET, USE, LOCK, UNLOCK, comments, etc.
    EMPTY = auto()  # Empty or whitespace-only


@dataclass
class ConversionStats:
    """Statistics collected during conversion."""

    statements_total: int = 0
    statements_ddl: int = 0
    statements_dml: int = 0
    statements_skipped: int = 0
    statements_failed: int = 0

    type_conversions: dict[str, int] = field(default_factory=dict)
    function_conversions: dict[str, int] = field(default_factory=dict)
    artifacts_removed: dict[str, int] = field(default_factory=dict)

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def record_type_conversion(self, mysql_type: str, pg_type: str) -> None:
        """Record a type conversion."""
        key = f"{mysql_type} -> {pg_type}"
        self.type_conversions[key] = self.type_conversions.get(key, 0) + 1

    def record_function_conversion(self, mysql_func: str, pg_func: str) -> None:
        """Record a function conversion."""
        key = f"{mysql_func} -> {pg_func}"
        self.function_conversions[key] = self.function_conversions.get(key, 0) + 1

    def record_artifact_removed(self, artifact_type: str) -> None:
        """Record removal of a MySQL-specific artifact."""
        self.artifacts_removed[artifact_type] = self.artifacts_removed.get(artifact_type, 0) + 1

    def record_error(self, message: str) -> None:
        """Record an error encountered during conversion."""
        self.errors.append(message)
        self.statements_failed += 1

    def record_warning(self, message: str) -> None:
        """Record a warning during conversion."""
        self.warnings.append(message)


@dataclass
class ConversionOptions:
    """Options controlling conversion behavior."""

    # Output options
    debug: bool = False
    preserve_comments: bool = True
    add_transaction_wrapper: bool = False

    # Conversion behavior
    strict_mode: bool = False  # Fail on first error vs continue
    unsigned_upcast: bool = True  # Upcast unsigned types to larger signed types

    # Feature toggles
    convert_auto_increment: bool = True
    convert_foreign_keys: bool = True
    remove_engine_specs: bool = True
    remove_charset_specs: bool = True

    # PostgreSQL target options
    use_serial: bool = True  # Use SERIAL vs IDENTITY for auto-increment
    bytea_format: str = "decode"  # 'decode' (decode('hex', 'hex')) or 'escape' ('\x...')


@dataclass
class ConversionContext:
    """
    Context object passed through conversion pipeline stages.

    This carries:
    - Configuration options
    - Accumulated statistics
    - State between stages
    - Debug/diagnostic information
    """

    options: ConversionOptions = field(default_factory=ConversionOptions)
    stats: ConversionStats = field(default_factory=ConversionStats)

    # Current processing state
    current_statement: str = ""
    current_statement_type: StatementType = StatementType.EMPTY
    current_line_number: int = 0

    # Accumulator for output
    output_statements: list[str] = field(default_factory=list)

    # Metadata extracted during processing
    table_names: list[str] = field(default_factory=list)
    auto_increment_columns: dict[str, list[str]] = field(default_factory=dict)

    # Debug trace
    debug_log: list[str] = field(default_factory=list)

    def log_debug(self, message: str) -> None:
        """Add a debug message if debug mode is enabled."""
        if self.options.debug:
            self.debug_log.append(f"[line {self.current_line_number}] {message}")

    def add_output(self, statement: str) -> None:
        """Add a converted statement to output."""
        if statement.strip():
            self.output_statements.append(statement)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the conversion for reporting."""
        return {
            "statements": {
                "total": self.stats.statements_total,
                "ddl": self.stats.statements_ddl,
                "dml": self.stats.statements_dml,
                "skipped": self.stats.statements_skipped,
                "failed": self.stats.statements_failed,
            },
            "type_conversions": self.stats.type_conversions,
            "function_conversions": self.stats.function_conversions,
            "artifacts_removed": self.stats.artifacts_removed,
            "tables_found": len(self.table_names),
            "errors": len(self.stats.errors),
            "warnings": len(self.stats.warnings),
        }
