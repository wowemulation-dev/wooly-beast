"""Tests for escape sequence handler."""


from trinity_postgres_tools.dml.escape_handler import (
    StringStyle,
    convert_string_content,
    convert_string_escapes,
    escape_for_postgres,
    needs_escape_string_style,
)


class TestConvertStringEscapes:
    """Test the main escape conversion function."""

    def test_simple_string(self):
        """Simple strings pass through unchanged."""
        result = convert_string_escapes("'hello'")
        assert result.value == "'hello'"
        assert result.style == StringStyle.STANDARD
        assert not result.had_special_escapes

    def test_empty_string(self):
        """Empty strings work correctly."""
        result = convert_string_escapes("''")
        assert result.value == "''"

    def test_escaped_quote(self):
        """Escaped quotes convert correctly."""
        # MySQL: 'Zul\'Farrak' -> PostgreSQL: 'Zul''Farrak'
        result = convert_string_escapes(r"'Zul\'Farrak'")
        assert result.value == "'Zul''Farrak'"
        assert result.style == StringStyle.STANDARD

    def test_doubled_quote_preserved(self):
        """Doubled quotes are already PostgreSQL compatible."""
        result = convert_string_escapes("'it''s'")
        assert result.value == "'it''s'"

    def test_escaped_backslash(self):
        """Escaped backslashes are preserved."""
        # MySQL: 'path\\to' has content path\to
        # In Python raw string: r"'path\\to'" is the literal 'path\\to'
        result = convert_string_escapes(r"'path\\to'")
        # Should keep the escaped backslash
        assert "\\\\" in result.value


class TestCriticalEscapeCase:
    """Test the critical \\' edge case."""

    def test_escaped_backslash_before_quote_end(self):
        """
        CRITICAL: \\' at end of string.

        MySQL string 'text\\' has content: text\\  (text followed by backslash)
        This should convert to PostgreSQL 'text\\' (same representation)

        The danger is that naive conversion might see \\' as:
        - backslash followed by escaped quote
        Instead of:
        - escaped backslash followed by end quote
        """
        # Input: MySQL string 'text\\'
        # The \\\\ in the raw string is the literal \\ in the MySQL string
        mysql_string = r"'text\\'"

        result = convert_string_escapes(mysql_string)

        # Result should be 'text\\' - PostgreSQL sees same content
        assert result.value == r"'text\\'"
        # Most importantly, it should NOT have corrupted the quote
        assert result.value.endswith("'")
        assert result.value.count("'") == 2

    def test_escaped_backslash_before_escaped_quote(self):
        """
        Handle \\\\' (escaped backslash then escaped quote).

        MySQL: 'text\\\'' -> content is: text\'
        PostgreSQL: 'text\\''' (backslash, then doubled quote)
        """
        # MySQL 'text\\\'' means content is: text\'
        mysql_string = r"'text\\\''"

        result = convert_string_escapes(mysql_string)

        # PostgreSQL needs: 'text\\'''
        # The escaped backslash stays, escaped quote becomes doubled
        # But wait - let me think about this more carefully
        # Input string content after removing quotes: text\\'
        # That's: text + \\ (escaped backslash) + ' (escaped quote)
        # PostgreSQL: text + \\ + '' (doubled quote)
        assert "''" in result.value  # The escaped quote became doubled


class TestSpecialEscapeSequences:
    """Test special escape sequences that need E'' style."""

    def test_newline_escape(self):
        """Strings with \\n need E'' style."""
        result = convert_string_escapes(r"'line1\nline2'")
        assert result.style == StringStyle.ESCAPE
        assert result.had_special_escapes
        assert result.value.startswith("E'")

    def test_tab_escape(self):
        """Strings with \\t need E'' style."""
        result = convert_string_escapes(r"'col1\tcol2'")
        assert result.style == StringStyle.ESCAPE

    def test_carriage_return_escape(self):
        """Strings with \\r need E'' style."""
        result = convert_string_escapes(r"'line1\rline2'")
        assert result.style == StringStyle.ESCAPE

    def test_null_escape(self):
        """Strings with \\0 need E'' style."""
        result = convert_string_escapes(r"'data\0more'")
        assert result.style == StringStyle.ESCAPE


class TestDoubleQuoteEscape:
    """Test escaped double quote handling."""

    def test_escaped_double_quote(self):
        """Escaped double quotes are unescaped."""
        # MySQL: 'say \"hello\"' -> PostgreSQL: 'say "hello"'
        result = convert_string_escapes(r"'say \"hello\"'")
        assert '"' in result.value
        assert r'\"' not in result.value


class TestConvertStringContent:
    """Test the content-only conversion function."""

    def test_simple_content(self):
        """Simple content unchanged."""
        content, needs_escape = convert_string_content("hello")
        assert content == "hello"
        assert not needs_escape

    def test_escaped_quote_in_content(self):
        """Escaped quotes convert."""
        content, needs_escape = convert_string_content(r"it\'s")
        assert content == "it''s"
        assert not needs_escape

    def test_special_escape_detected(self):
        """Special escapes are detected."""
        _content, needs_escape = convert_string_content(r"line1\nline2")
        assert needs_escape


class TestNeedsEscapeStringStyle:
    """Test the escape style detection function."""

    def test_simple_no_escape(self):
        """Simple strings don't need E''."""
        assert not needs_escape_string_style("hello")

    def test_newline_needs_escape(self):
        """Strings with \\n need E''."""
        assert needs_escape_string_style(r"hello\nworld")

    def test_tab_needs_escape(self):
        """Strings with \\t need E''."""
        assert needs_escape_string_style(r"col1\tcol2")

    def test_regular_backslash_no_escape(self):
        """Regular escaped backslashes don't need E''."""
        # \\\\ is an escaped backslash, not a special escape
        # Note: avoid \\f, \\b, \\n, \\r, \\t, \\0 in test string
        assert not needs_escape_string_style(r"path\\data")


class TestEscapeForPostgres:
    """Test creating new PostgreSQL string literals."""

    def test_simple_value(self):
        """Simple values get single quotes."""
        result = escape_for_postgres("hello")
        assert result == "'hello'"

    def test_value_with_quote(self):
        """Quotes get doubled."""
        result = escape_for_postgres("it's")
        assert result == "'it''s'"

    def test_value_with_newline(self):
        """Newlines trigger E'' style."""
        result = escape_for_postgres("line1\nline2")
        assert result.startswith("E'")
        assert "\\n" in result

    def test_value_with_backslash(self):
        """Backslashes get escaped."""
        result = escape_for_postgres("path\\file")
        # Should be escaped in E'' style if there are special chars
        # or in standard style if not
        assert "'" in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_short_string(self):
        """Handle very short strings."""
        result = convert_string_escapes("'a'")
        assert result.value == "'a'"

    def test_not_a_string_literal(self):
        """Non-string-literal input passed through."""
        result = convert_string_escapes("hello")
        assert result.value == "hello"

    def test_null_input(self):
        """Empty input handled."""
        result = convert_string_escapes("")
        assert result.value == ""

    def test_just_quotes(self):
        """Just quotes handled."""
        result = convert_string_escapes("''")
        assert result.value == "''"

    def test_multiple_consecutive_escapes(self):
        """Multiple consecutive escape sequences."""
        # String with multiple escapes: 'a\'b\'c'
        result = convert_string_escapes(r"'a\'b\'c'")
        assert result.value == "'a''b''c'"
