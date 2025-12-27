"""
Declarative artifact removal rules for mysqldump output.

This module defines patterns for MySQL-specific artifacts that need
to be removed or transformed before PostgreSQL conversion.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto

from trinity_postgres_tools.pipeline.context import ConversionContext


class ArtifactType(Enum):
    """Types of mysqldump artifacts."""

    CONDITIONAL_COMMENT = auto()  # /*!40101 ... */
    LOCK_STATEMENT = auto()  # LOCK TABLES, UNLOCK TABLES
    SET_STATEMENT = auto()  # SET @var, SET NAMES
    USE_STATEMENT = auto()  # USE database
    DELIMITER = auto()  # DELIMITER ;;
    DISABLED_KEYS = auto()  # ALTER TABLE ... DISABLE KEYS


@dataclass
class ArtifactRule:
    """
    Rule for identifying and handling a mysqldump artifact.

    Attributes:
        name: Rule name for logging
        artifact_type: Category of artifact
        pattern: Regex pattern to match
        replacement: Replacement string (None to remove entirely)
        multiline: Whether pattern spans multiple lines
    """

    name: str
    artifact_type: ArtifactType
    pattern: str
    replacement: str | None = None
    multiline: bool = False

    def compile(self) -> re.Pattern:
        """Compile the pattern to a regex."""
        flags = re.IGNORECASE
        if self.multiline:
            flags |= re.MULTILINE | re.DOTALL
        return re.compile(self.pattern, flags)


# Conditional comments - MySQL version-specific code
# Consume trailing semicolon to avoid leaving empty statements
CONDITIONAL_COMMENT_RULES = [
    ArtifactRule(
        name="conditional_comment_full",
        artifact_type=ArtifactType.CONDITIONAL_COMMENT,
        pattern=r"/\*!\d+\s+.*?\*/\s*;?",
        replacement="",
        multiline=True,
    ),
    ArtifactRule(
        name="conditional_comment_set",
        artifact_type=ArtifactType.CONDITIONAL_COMMENT,
        pattern=r"/\*!\d+\s+SET\s+.*?\*/\s*;?",
        replacement="",
        multiline=True,
    ),
]

# Lock statements
LOCK_RULES = [
    ArtifactRule(
        name="lock_tables",
        artifact_type=ArtifactType.LOCK_STATEMENT,
        pattern=r"LOCK\s+TABLES\s+.*?;",
        replacement="",
        multiline=True,
    ),
    ArtifactRule(
        name="unlock_tables",
        artifact_type=ArtifactType.LOCK_STATEMENT,
        pattern=r"UNLOCK\s+TABLES\s*;",
        replacement="",
    ),
]

# SET statements
SET_RULES = [
    ArtifactRule(
        name="set_names",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+NAMES\s+\w+\s*;",
        replacement="",
    ),
    ArtifactRule(
        name="set_character_set",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+character_set_\w+\s*=\s*@?\w+\s*;",
        replacement="",
    ),
    ArtifactRule(
        name="set_sql_mode",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+SQL_MODE\s*=.*?;",
        replacement="",
        multiline=True,
    ),
    ArtifactRule(
        name="set_time_zone",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+TIME_ZONE\s*=.*?;",
        replacement="",
    ),
    ArtifactRule(
        name="set_at_variable",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+@\w+\s*=.*?;",
        replacement="",
    ),
    ArtifactRule(
        name="set_foreign_key_checks",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+FOREIGN_KEY_CHECKS\s*=\s*\d+\s*;",
        replacement="",
    ),
    ArtifactRule(
        name="set_unique_checks",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+UNIQUE_CHECKS\s*=\s*\d+\s*;",
        replacement="",
    ),
    ArtifactRule(
        name="set_autocommit",
        artifact_type=ArtifactType.SET_STATEMENT,
        pattern=r"SET\s+AUTOCOMMIT\s*=\s*\d+\s*;",
        replacement="",
    ),
]

# USE statements
USE_RULES = [
    ArtifactRule(
        name="use_database",
        artifact_type=ArtifactType.USE_STATEMENT,
        pattern=r"USE\s+`?\w+`?\s*;",
        replacement="",
    ),
]

# Delimiter statements
DELIMITER_RULES = [
    ArtifactRule(
        name="delimiter",
        artifact_type=ArtifactType.DELIMITER,
        pattern=r"DELIMITER\s+.*?$",
        replacement="",
        multiline=True,
    ),
]

# Disabled keys (for faster imports)
DISABLED_KEYS_RULES = [
    ArtifactRule(
        name="disable_keys",
        artifact_type=ArtifactType.DISABLED_KEYS,
        pattern=r"ALTER\s+TABLE\s+`?\w+`?\s+DISABLE\s+KEYS\s*;",
        replacement="",
    ),
    ArtifactRule(
        name="enable_keys",
        artifact_type=ArtifactType.DISABLED_KEYS,
        pattern=r"ALTER\s+TABLE\s+`?\w+`?\s+ENABLE\s+KEYS\s*;",
        replacement="",
    ),
]

# All rules combined
ALL_ARTIFACT_RULES = [
    *CONDITIONAL_COMMENT_RULES,
    *LOCK_RULES,
    *SET_RULES,
    *USE_RULES,
    *DELIMITER_RULES,
    *DISABLED_KEYS_RULES,
]


class ArtifactRemover:
    """
    Removes mysqldump artifacts from SQL content.

    Uses declarative rules to identify and remove MySQL-specific
    patterns that are not valid in PostgreSQL.
    """

    def __init__(self, rules: list[ArtifactRule] | None = None) -> None:
        """
        Initialize with artifact rules.

        Args:
            rules: Rules to apply, or ALL_ARTIFACT_RULES if None
        """
        self.rules = rules or ALL_ARTIFACT_RULES
        self._compiled: list[tuple[ArtifactRule, re.Pattern]] = []
        self._compile_rules()

    def _compile_rules(self) -> None:
        """Compile all rules to regex patterns."""
        self._compiled = [(rule, rule.compile()) for rule in self.rules]

    def remove_artifacts(self, sql: str, ctx: ConversionContext | None = None) -> str:
        """
        Remove all artifacts from SQL content.

        Args:
            sql: SQL content with potential artifacts
            ctx: Optional context for statistics

        Returns:
            Cleaned SQL content
        """
        result = sql

        for rule, pattern in self._compiled:
            matches = pattern.findall(result)
            if matches:
                if ctx:
                    ctx.stats.record_artifact_removed(rule.name)
                    ctx.log_debug(f"Removed {len(matches)} {rule.name} artifacts")

                replacement = rule.replacement if rule.replacement is not None else ""
                result = pattern.sub(replacement, result)

        return result

    def remove_by_type(
        self, sql: str, artifact_type: ArtifactType, ctx: ConversionContext | None = None
    ) -> str:
        """
        Remove only artifacts of a specific type.

        Args:
            sql: SQL content
            artifact_type: Type of artifacts to remove
            ctx: Optional context for statistics

        Returns:
            Cleaned SQL content
        """
        result = sql

        for rule, pattern in self._compiled:
            if rule.artifact_type == artifact_type:
                matches = pattern.findall(result)
                if matches:
                    if ctx:
                        ctx.stats.record_artifact_removed(rule.name)
                    replacement = rule.replacement if rule.replacement is not None else ""
                    result = pattern.sub(replacement, result)

        return result


def remove_mysqldump_artifacts(sql: str, ctx: ConversionContext | None = None) -> str:
    """
    Convenience function to remove all mysqldump artifacts.

    Args:
        sql: SQL content
        ctx: Optional context for statistics

    Returns:
        Cleaned SQL content
    """
    remover = ArtifactRemover()
    return remover.remove_artifacts(sql, ctx)


def get_artifact_rules() -> list[ArtifactRule]:
    """Get all defined artifact rules."""
    return ALL_ARTIFACT_RULES.copy()
