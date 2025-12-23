"""Tests for preprocessing module."""

from trinity_postgres_tools.pipeline.context import ConversionContext
from trinity_postgres_tools.preprocessing.artifacts import (
    ALL_ARTIFACT_RULES,
    ArtifactRemover,
    ArtifactType,
    remove_mysqldump_artifacts,
)


class TestArtifactRemover:
    """Test artifact removal functionality."""

    def test_removes_conditional_comments(self):
        """Removes MySQL conditional comments."""
        sql = """/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "/*!40101" not in result
        assert "INSERT INTO test VALUES" in result

    def test_removes_lock_tables(self):
        """Removes LOCK/UNLOCK TABLES statements."""
        sql = """LOCK TABLES `test` WRITE;
INSERT INTO test VALUES (1);
UNLOCK TABLES;"""
        result = remove_mysqldump_artifacts(sql)
        assert "LOCK TABLES" not in result
        assert "UNLOCK TABLES" not in result
        assert "INSERT INTO test VALUES" in result

    def test_removes_set_names(self):
        """Removes SET NAMES statements."""
        sql = """SET NAMES utf8;
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "SET NAMES" not in result
        assert "INSERT" in result

    def test_removes_set_sql_mode(self):
        """Removes SET SQL_MODE statements."""
        sql = """SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "SQL_MODE" not in result

    def test_removes_use_database(self):
        """Removes USE database statements."""
        sql = """USE `world`;
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "USE" not in result
        assert "INSERT" in result

    def test_removes_disable_keys(self):
        """Removes ALTER TABLE DISABLE/ENABLE KEYS."""
        sql = """ALTER TABLE test DISABLE KEYS;
INSERT INTO test VALUES (1);
ALTER TABLE test ENABLE KEYS;"""
        result = remove_mysqldump_artifacts(sql)
        assert "DISABLE KEYS" not in result
        assert "ENABLE KEYS" not in result
        assert "INSERT" in result

    def test_preserves_regular_sql(self):
        """Preserves regular SQL statements."""
        sql = """CREATE TABLE test (id INT PRIMARY KEY);
INSERT INTO test VALUES (1);
SELECT * FROM test;"""
        result = remove_mysqldump_artifacts(sql)
        assert "CREATE TABLE" in result
        assert "INSERT INTO" in result
        assert "SELECT" in result

    def test_tracks_statistics(self):
        """Records artifact removal statistics."""
        sql = """SET NAMES utf8;
LOCK TABLES test WRITE;
INSERT INTO test VALUES (1);
UNLOCK TABLES;"""
        ctx = ConversionContext()
        remove_mysqldump_artifacts(sql, ctx)

        assert sum(ctx.stats.artifacts_removed.values()) > 0


class TestArtifactRemoverByType:
    """Test selective artifact removal."""

    def test_remove_only_lock_statements(self):
        """Can remove only lock statements."""
        sql = """SET NAMES utf8;
LOCK TABLES test WRITE;
INSERT INTO test VALUES (1);"""
        remover = ArtifactRemover()
        result = remover.remove_by_type(sql, ArtifactType.LOCK_STATEMENT)

        assert "LOCK TABLES" not in result
        assert "SET NAMES" in result  # Not removed


class TestArtifactRules:
    """Test artifact rule definitions."""

    def test_all_rules_have_names(self):
        """All rules have unique names."""
        names = [rule.name for rule in ALL_ARTIFACT_RULES]
        assert len(names) == len(set(names))

    def test_all_rules_have_patterns(self):
        """All rules have valid regex patterns."""
        for rule in ALL_ARTIFACT_RULES:
            # Should compile without error
            pattern = rule.compile()
            assert pattern is not None

    def test_rules_cover_common_artifacts(self):
        """Rules cover common mysqldump artifacts."""
        names = {rule.name for rule in ALL_ARTIFACT_RULES}

        # Check for essential rules
        assert "lock_tables" in names
        assert "unlock_tables" in names
        assert "set_names" in names


class TestComplexArtifacts:
    """Test complex artifact patterns."""

    def test_multiline_conditional_comment(self):
        """Handles multiline conditional comments."""
        sql = """/*!40101 SET
@OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT
*/;
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "CHARACTER_SET" not in result
        assert "INSERT" in result

    def test_multiline_lock_tables(self):
        """Handles LOCK TABLES with multiple tables."""
        sql = """LOCK TABLES `table1` WRITE,
`table2` WRITE,
`table3` READ;
INSERT INTO test VALUES (1);"""
        result = remove_mysqldump_artifacts(sql)
        assert "LOCK TABLES" not in result
        assert "INSERT" in result
