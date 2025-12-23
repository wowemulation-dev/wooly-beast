"""Tests for MySQL tokenizer."""


from trinity_postgres_tools.dml.tokenizer import TokenType, tokenize


class TestSimpleTokens:
    """Test basic token recognition."""

    def test_empty_string(self):
        """Empty input produces no tokens."""
        tokens = tokenize("")
        assert tokens == []

    def test_simple_keyword(self):
        """Recognizes simple keywords."""
        tokens = tokenize("SELECT")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.KEYWORD
        assert tokens[0].value == "SELECT"

    def test_whitespace(self):
        """Recognizes whitespace."""
        tokens = tokenize("  \t\n  ")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.WHITESPACE

    def test_operators(self):
        """Recognizes operators."""
        tokens = tokenize("(,);")
        assert len(tokens) == 4
        assert all(t.type == TokenType.OPERATOR for t in tokens)
        assert [t.value for t in tokens] == ["(", ",", ")", ";"]

    def test_number(self):
        """Recognizes numeric literals."""
        tokens = tokenize("123")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMERIC
        assert tokens[0].value == "123"

    def test_negative_number(self):
        """Recognizes negative numbers."""
        tokens = tokenize("-45.67")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMERIC
        assert tokens[0].value == "-45.67"

    def test_scientific_notation(self):
        """Recognizes scientific notation."""
        tokens = tokenize("1.5e-10")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMERIC
        assert tokens[0].value == "1.5e-10"


class TestStringTokens:
    """Test string literal tokenization."""

    def test_simple_string(self):
        """Recognizes simple string literals."""
        tokens = tokenize("'hello'")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "'hello'"

    def test_empty_string(self):
        """Recognizes empty string."""
        tokens = tokenize("''")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "''"

    def test_string_with_spaces(self):
        """Strings can contain spaces."""
        tokens = tokenize("'hello world'")
        assert len(tokens) == 1
        assert tokens[0].value == "'hello world'"


class TestEscapeSequences:
    """Test escape sequence handling in strings."""

    def test_escaped_quote(self):
        """Handles escaped single quote."""
        tokens = tokenize(r"'Zul\'Farrak'")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == r"'Zul\'Farrak'"

    def test_doubled_quote(self):
        """Handles doubled quote escape."""
        tokens = tokenize("'it''s'")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "'it''s'"

    def test_escaped_backslash(self):
        """Handles escaped backslash."""
        tokens = tokenize(r"'path\\to\\file'")
        assert len(tokens) == 1
        assert tokens[0].value == r"'path\\to\\file'"

    def test_critical_edge_case_escaped_backslash_before_quote(self):
        """
        CRITICAL TEST: \\' sequence.

        The sequence \\' should be interpreted as:
        - An escaped backslash (\\)
        - Followed by the end of the string (')

        NOT as:
        - A backslash
        - Followed by an escaped quote (\\')
        """
        # This is the string "text\\" followed by end quote
        # In raw Python string: 'text\\\\'  means string content is: text\\
        # When we add the trailing quote: 'text\\\\'
        tokens = tokenize("'text\\\\'")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        # The tokenizer should capture the whole string
        assert tokens[0].value == "'text\\\\'"

    def test_backslash_quote_in_middle(self):
        """Escaped quote with backslash in middle of string."""
        # 'adoptas esa forma...\\'  ->  string ends after \\
        sql = "'adoptas esa forma...\\\\'"
        tokens = tokenize(sql)
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING

    def test_escaped_n_newline(self):
        """Handles \\n escape sequence."""
        tokens = tokenize(r"'line1\nline2'")
        assert len(tokens) == 1
        assert r"\n" in tokens[0].value

    def test_escaped_t_tab(self):
        """Handles \\t escape sequence."""
        tokens = tokenize(r"'col1\tcol2'")
        assert len(tokens) == 1
        assert r"\t" in tokens[0].value


class TestHexLiterals:
    """Test hex literal tokenization."""

    def test_simple_hex(self):
        """Recognizes hex literals."""
        tokens = tokenize("0xDEADBEEF")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.HEX_LITERAL
        assert tokens[0].value == "0xDEADBEEF"

    def test_lowercase_hex(self):
        """Recognizes lowercase hex."""
        tokens = tokenize("0xabcdef")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.HEX_LITERAL

    def test_mixed_case_hex(self):
        """Recognizes mixed case hex."""
        tokens = tokenize("0xAbCdEf")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.HEX_LITERAL

    def test_hex_in_values(self):
        """Hex literal in VALUES clause."""
        tokens = tokenize("(0x48656C6C6F)")
        hex_tokens = [t for t in tokens if t.type == TokenType.HEX_LITERAL]
        assert len(hex_tokens) == 1
        assert hex_tokens[0].value == "0x48656C6C6F"


class TestBacktickIdentifiers:
    """Test backtick-quoted identifiers."""

    def test_simple_backtick(self):
        """Recognizes backtick identifiers."""
        tokens = tokenize("`column_name`")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.BACKTICK_ID
        assert tokens[0].value == "`column_name`"

    def test_backtick_with_spaces(self):
        """Backticks can quote identifiers with spaces."""
        tokens = tokenize("`my column`")
        assert len(tokens) == 1
        assert tokens[0].value == "`my column`"

    def test_doubled_backtick(self):
        """Handles doubled backtick escape."""
        tokens = tokenize("`name``with``backticks`")
        assert len(tokens) == 1
        assert tokens[0].value == "`name``with``backticks`"


class TestDoubleQuotedStrings:
    """Test double-quoted strings."""

    def test_double_quoted(self):
        """Recognizes double-quoted strings."""
        tokens = tokenize('"hello"')
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.DOUBLE_QUOTED
        assert tokens[0].value == '"hello"'


class TestComments:
    """Test comment handling."""

    def test_line_comment(self):
        """Recognizes line comments."""
        tokens = tokenize("-- this is a comment")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.COMMENT
        assert tokens[0].value == "-- this is a comment"

    def test_block_comment(self):
        """Recognizes block comments."""
        tokens = tokenize("/* block comment */")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.COMMENT


class TestComplexStatements:
    """Test tokenizing complete SQL statements."""

    def test_simple_insert(self):
        """Tokenizes a simple INSERT statement."""
        sql = "INSERT INTO table1 VALUES (1, 'test')"
        tokens = tokenize(sql)

        keywords = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert "INSERT" in [k.value for k in keywords]
        assert "INTO" in [k.value for k in keywords]
        assert "VALUES" in [k.value for k in keywords]

        strings = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strings) == 1
        assert strings[0].value == "'test'"

    def test_insert_with_escapes(self):
        """Tokenizes INSERT with escape sequences."""
        sql = r"INSERT INTO t VALUES (1, 'Zul\'Farrak', 0xDEAD)"
        tokens = tokenize(sql)

        strings = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strings) == 1
        assert r"\'" in strings[0].value

        hexes = [t for t in tokens if t.type == TokenType.HEX_LITERAL]
        assert len(hexes) == 1

    def test_reconstructs_original(self):
        """Token values can reconstruct original SQL."""
        sql = "INSERT INTO `t` VALUES (1, 'test')"
        tokens = tokenize(sql)
        reconstructed = "".join(t.value for t in tokens)
        assert reconstructed == sql


class TestTokenPositions:
    """Test that token positions are correct."""

    def test_token_start_end(self):
        """Token positions are accurate."""
        sql = "SELECT 1"
        tokens = tokenize(sql)

        # SELECT starts at 0
        assert tokens[0].start == 0
        assert tokens[0].end == 6

        # whitespace at 6
        assert tokens[1].start == 6
        assert tokens[1].end == 7

        # 1 at 7
        assert tokens[2].start == 7
        assert tokens[2].end == 8

    def test_token_length(self):
        """Token length property is correct."""
        tokens = tokenize("'hello'")
        assert tokens[0].length == 7
