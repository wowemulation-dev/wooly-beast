"""Tests for statement classifier."""

from trinity_postgres_tools.parsing.classifier import (
    ClassifiedStatement,
    StatementClassifier,
    classify_statement,
    classify_statements,
    get_statement_keyword,
    is_ddl,
    is_dml,
    should_skip,
)
from trinity_postgres_tools.pipeline.context import StatementType


class TestGetStatementKeyword:
    """Test keyword extraction."""

    def test_simple_keyword(self):
        """Extracts simple keyword."""
        assert get_statement_keyword("SELECT * FROM test") == "SELECT"

    def test_keyword_case_insensitive(self):
        """Returns uppercase keyword."""
        assert get_statement_keyword("select * from test") == "SELECT"

    def test_keyword_with_whitespace(self):
        """Handles leading whitespace."""
        assert get_statement_keyword("  INSERT INTO test VALUES (1)") == "INSERT"

    def test_empty_string(self):
        """Empty string returns empty keyword."""
        assert get_statement_keyword("") == ""

    def test_comment_keyword(self):
        """Comment lines return the comment marker as keyword."""
        # Note: -- isn't a word character, so this returns empty
        assert get_statement_keyword("-- comment") == ""


class TestClassifyStatement:
    """Test statement classification."""

    def test_classify_create(self):
        """CREATE is classified as DDL."""
        result = classify_statement("CREATE TABLE test (id INT)")
        assert result.statement_type == StatementType.DDL
        assert result.keyword == "CREATE"

    def test_classify_alter(self):
        """ALTER is classified as DDL."""
        result = classify_statement("ALTER TABLE test ADD COLUMN name TEXT")
        assert result.statement_type == StatementType.DDL
        assert result.keyword == "ALTER"

    def test_classify_drop(self):
        """DROP is classified as DDL."""
        result = classify_statement("DROP TABLE test")
        assert result.statement_type == StatementType.DDL
        assert result.keyword == "DROP"

    def test_classify_truncate(self):
        """TRUNCATE is classified as DDL."""
        result = classify_statement("TRUNCATE TABLE test")
        assert result.statement_type == StatementType.DDL
        assert result.keyword == "TRUNCATE"

    def test_classify_insert(self):
        """INSERT is classified as DML."""
        result = classify_statement("INSERT INTO test VALUES (1)")
        assert result.statement_type == StatementType.DML
        assert result.keyword == "INSERT"

    def test_classify_update(self):
        """UPDATE is classified as DML."""
        result = classify_statement("UPDATE test SET name = 'foo'")
        assert result.statement_type == StatementType.DML
        assert result.keyword == "UPDATE"

    def test_classify_delete(self):
        """DELETE is classified as DML."""
        result = classify_statement("DELETE FROM test WHERE id = 1")
        assert result.statement_type == StatementType.DML
        assert result.keyword == "DELETE"

    def test_classify_replace(self):
        """REPLACE is classified as DML."""
        result = classify_statement("REPLACE INTO test VALUES (1)")
        assert result.statement_type == StatementType.DML
        assert result.keyword == "REPLACE"

    def test_classify_select(self):
        """SELECT is classified as OTHER (passthrough)."""
        result = classify_statement("SELECT * FROM test")
        assert result.statement_type == StatementType.OTHER
        assert result.keyword == "SELECT"

    def test_classify_set(self):
        """SET is classified as OTHER."""
        result = classify_statement("SET NAMES utf8")
        assert result.statement_type == StatementType.OTHER
        assert result.keyword == "SET"

    def test_classify_empty(self):
        """Empty string is classified as EMPTY."""
        result = classify_statement("")
        assert result.statement_type == StatementType.EMPTY

    def test_classify_whitespace(self):
        """Whitespace-only is classified as EMPTY."""
        result = classify_statement("   \n\t  ")
        assert result.statement_type == StatementType.EMPTY


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_is_ddl(self):
        """is_ddl returns True for DDL statements."""
        assert is_ddl("CREATE TABLE test (id INT)")
        assert is_ddl("ALTER TABLE test ADD COLUMN x INT")
        assert not is_ddl("INSERT INTO test VALUES (1)")
        assert not is_ddl("SELECT 1")

    def test_is_dml(self):
        """is_dml returns True for DML statements."""
        assert is_dml("INSERT INTO test VALUES (1)")
        assert is_dml("UPDATE test SET x = 1")
        assert is_dml("DELETE FROM test")
        assert not is_dml("CREATE TABLE test (id INT)")
        assert not is_dml("SELECT 1")

    def test_should_skip(self):
        """should_skip returns True for skip keywords."""
        assert should_skip("SET NAMES utf8")
        assert should_skip("USE database")
        assert should_skip("LOCK TABLES test WRITE")
        assert should_skip("UNLOCK TABLES")
        assert not should_skip("CREATE TABLE test (id INT)")
        assert not should_skip("INSERT INTO test VALUES (1)")


class TestStatementClassifier:
    """Test the StatementClassifier class."""

    def test_tracks_counts(self):
        """Tracks classification counts."""
        classifier = StatementClassifier()

        classifier.classify("CREATE TABLE test (id INT)")
        classifier.classify("INSERT INTO test VALUES (1)")
        classifier.classify("INSERT INTO test VALUES (2)")
        classifier.classify("SELECT 1")

        assert classifier.ddl_count == 1
        assert classifier.dml_count == 2
        assert classifier.other_count == 1

    def test_classify_batch(self):
        """Batch classification works correctly."""
        statements = [
            "CREATE TABLE test (id INT)",
            "INSERT INTO test VALUES (1)",
            "SELECT 1",
        ]

        results = classify_statements(statements)

        assert len(results) == 3
        assert results[0].statement_type == StatementType.DDL
        assert results[1].statement_type == StatementType.DML
        assert results[2].statement_type == StatementType.OTHER

    def test_reset_counts(self):
        """Can reset classification counts."""
        classifier = StatementClassifier()
        classifier.classify("CREATE TABLE test (id INT)")
        classifier.reset_counts()

        assert classifier.ddl_count == 0
        assert classifier.dml_count == 0
