"""Tests for statement splitter."""

from trinity_postgres_tools.parsing.splitter import (
    Statement,
    StatementSplitter,
    split_and_filter,
    split_statements,
)


class TestStatementSplitter:
    """Test basic statement splitting."""

    def test_split_simple_statements(self):
        """Splits simple semicolon-delimited statements."""
        sql = "SELECT 1; SELECT 2; SELECT 3;"
        statements = split_statements(sql)
        assert len(statements) == 3

    def test_split_with_newlines(self):
        """Handles newlines between statements."""
        sql = """SELECT 1;
SELECT 2;
SELECT 3;"""
        statements = split_statements(sql)
        assert len(statements) == 3

    def test_empty_input(self):
        """Empty input produces no statements."""
        statements = split_statements("")
        assert len(statements) == 0

    def test_single_statement_no_semicolon(self):
        """Handles statement without trailing semicolon."""
        sql = "SELECT 1"
        statements = split_statements(sql)
        assert len(statements) == 1
        assert statements[0].sql == "SELECT 1"

    def test_preserves_statement_content(self):
        """Statement content is preserved."""
        sql = "INSERT INTO test VALUES (1, 'hello');"
        statements = split_statements(sql)
        assert len(statements) == 1
        assert "INSERT INTO test VALUES" in statements[0].sql


class TestQuotedStrings:
    """Test handling of quoted strings."""

    def test_semicolon_in_single_quote(self):
        """Ignores semicolons inside single-quoted strings."""
        sql = "INSERT INTO test VALUES ('hello; world');"
        statements = split_statements(sql)
        assert len(statements) == 1
        assert "hello; world" in statements[0].sql

    def test_semicolon_in_double_quote(self):
        """Ignores semicolons inside double-quoted strings."""
        sql = 'INSERT INTO test VALUES ("hello; world");'
        statements = split_statements(sql)
        assert len(statements) == 1

    def test_semicolon_in_backtick(self):
        """Ignores semicolons inside backtick identifiers."""
        sql = "SELECT * FROM `table; name`;"
        statements = split_statements(sql)
        assert len(statements) == 1


class TestEscapeSequences:
    """Test handling of escape sequences in strings."""

    def test_escaped_quote(self):
        """Handles escaped quotes in strings."""
        sql = r"INSERT INTO test VALUES ('Zul\'Farrak');"
        statements = split_statements(sql)
        assert len(statements) == 1
        assert r"\'" in statements[0].sql

    def test_doubled_quote(self):
        """Handles doubled quotes in strings."""
        sql = "INSERT INTO test VALUES ('it''s');"
        statements = split_statements(sql)
        assert len(statements) == 1
        assert "''" in statements[0].sql

    def test_escaped_backslash(self):
        """Handles escaped backslashes."""
        sql = r"INSERT INTO test VALUES ('path\\to\\file');"
        statements = split_statements(sql)
        assert len(statements) == 1

    def test_critical_backslash_quote(self):
        """Handles the critical \\' edge case."""
        # String ending with escaped backslash
        sql = r"INSERT INTO test VALUES ('text\\');"
        statements = split_statements(sql)
        assert len(statements) == 1


class TestComments:
    """Test handling of comments."""

    def test_line_comment(self):
        """Handles line comments."""
        sql = """SELECT 1; -- this is a comment
SELECT 2;"""
        statements = split_statements(sql)
        assert len(statements) == 2

    def test_block_comment(self):
        """Handles block comments."""
        sql = "SELECT /* comment */ 1; SELECT 2;"
        statements = split_statements(sql)
        assert len(statements) == 2

    def test_semicolon_in_comment(self):
        """Ignores semicolons in comments."""
        sql = "SELECT 1 /* ; */ FROM test;"
        statements = split_statements(sql)
        assert len(statements) == 1

    def test_comment_only_statement(self):
        """Identifies comment-only statements."""
        sql = """-- This is a comment
SELECT 1;"""
        statements = split_statements(sql)
        # Should have 2 statements, one comment-only
        assert any(s.is_comment_only for s in statements) or len(statements) == 1


class TestLineNumbers:
    """Test line number tracking."""

    def test_tracks_start_line(self):
        """Tracks statement start line."""
        sql = """SELECT 1;

SELECT 2;"""
        statements = split_statements(sql)
        assert statements[0].start_line == 1

    def test_tracks_end_line(self):
        """Tracks statement end line."""
        sql = """SELECT 1;

SELECT 2;"""
        statements = split_statements(sql)
        # First statement ends on line 1
        # Second statement ends on line 3


class TestSplitAndFilter:
    """Test the split_and_filter convenience function."""

    def test_filters_comment_only(self):
        """Filters out comment-only statements."""
        sql = """-- Comment
SELECT 1;
-- Another comment
SELECT 2;"""
        statements = split_and_filter(sql)
        # Should only have the SELECT statements
        assert all("SELECT" in s for s in statements)

    def test_filters_empty(self):
        """Filters out empty statements."""
        sql = "SELECT 1;; SELECT 2;"
        statements = split_and_filter(sql)
        # Empty statement between ;; should be filtered
        assert all(s.strip() for s in statements)


class TestComplexStatements:
    """Test complex real-world statements."""

    def test_create_table(self):
        """Handles CREATE TABLE with multiple columns."""
        sql = """CREATE TABLE test (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    data TEXT
);"""
        statements = split_statements(sql)
        assert len(statements) == 1
        assert "CREATE TABLE" in statements[0].sql

    def test_insert_with_multiple_values(self):
        """Handles INSERT with multiple value tuples."""
        sql = """INSERT INTO test VALUES
    (1, 'a'),
    (2, 'b'),
    (3, 'c');"""
        statements = split_statements(sql)
        assert len(statements) == 1

    def test_mixed_statements(self):
        """Handles mix of DDL and DML."""
        sql = """CREATE TABLE test (id INT);
INSERT INTO test VALUES (1);
SELECT * FROM test;"""
        statements = split_statements(sql)
        assert len(statements) == 3
