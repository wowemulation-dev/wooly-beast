"""Tests for conversion context."""


from trinity_postgres_tools.pipeline.context import (
    ConversionContext,
    ConversionOptions,
    ConversionStats,
    StatementType,
)


class TestConversionStats:
    """Test ConversionStats functionality."""

    def test_initial_state(self):
        """Stats start at zero."""
        stats = ConversionStats()
        assert stats.statements_total == 0
        assert stats.statements_ddl == 0
        assert stats.statements_dml == 0
        assert stats.statements_skipped == 0
        assert stats.statements_failed == 0

    def test_record_type_conversion(self):
        """Can record type conversions."""
        stats = ConversionStats()
        stats.record_type_conversion("int", "integer")
        stats.record_type_conversion("int", "integer")
        stats.record_type_conversion("varchar", "varchar")

        assert stats.type_conversions["int -> integer"] == 2
        assert stats.type_conversions["varchar -> varchar"] == 1

    def test_record_function_conversion(self):
        """Can record function conversions."""
        stats = ConversionStats()
        stats.record_function_conversion("NOW", "now")
        stats.record_function_conversion("IFNULL", "COALESCE")

        assert stats.function_conversions["NOW -> now"] == 1
        assert stats.function_conversions["IFNULL -> COALESCE"] == 1

    def test_record_artifact_removed(self):
        """Can record artifact removals."""
        stats = ConversionStats()
        stats.record_artifact_removed("LOCK TABLES")
        stats.record_artifact_removed("LOCK TABLES")
        stats.record_artifact_removed("ENGINE=InnoDB")

        assert stats.artifacts_removed["LOCK TABLES"] == 2
        assert stats.artifacts_removed["ENGINE=InnoDB"] == 1

    def test_record_error(self):
        """Recording error increments failed count."""
        stats = ConversionStats()
        stats.record_error("Parse failed")
        stats.record_error("Transform failed")

        assert len(stats.errors) == 2
        assert stats.statements_failed == 2

    def test_record_warning(self):
        """Can record warnings without affecting counts."""
        stats = ConversionStats()
        stats.record_warning("Deprecated syntax")

        assert len(stats.warnings) == 1
        assert stats.statements_failed == 0


class TestConversionOptions:
    """Test ConversionOptions defaults and behavior."""

    def test_default_options(self):
        """Default options have sensible values."""
        opts = ConversionOptions()

        assert opts.debug is False
        assert opts.preserve_comments is True
        assert opts.strict_mode is False
        assert opts.unsigned_upcast is True
        assert opts.convert_auto_increment is True
        assert opts.use_serial is True
        assert opts.bytea_format == "decode"

    def test_custom_options(self):
        """Can customize options."""
        opts = ConversionOptions(debug=True, strict_mode=True, use_serial=False)

        assert opts.debug is True
        assert opts.strict_mode is True
        assert opts.use_serial is False


class TestConversionContext:
    """Test ConversionContext functionality."""

    def test_initial_state(self):
        """Context starts empty."""
        ctx = ConversionContext()

        assert ctx.current_statement == ""
        assert ctx.current_statement_type == StatementType.EMPTY
        assert ctx.current_line_number == 0
        assert len(ctx.output_statements) == 0
        assert len(ctx.table_names) == 0

    def test_log_debug_when_enabled(self):
        """Debug logging works when enabled."""
        opts = ConversionOptions(debug=True)
        ctx = ConversionContext(options=opts)
        ctx.current_line_number = 42

        ctx.log_debug("Test message")

        assert len(ctx.debug_log) == 1
        assert "[line 42] Test message" in ctx.debug_log[0]

    def test_log_debug_when_disabled(self):
        """Debug logging is skipped when disabled."""
        opts = ConversionOptions(debug=False)
        ctx = ConversionContext(options=opts)

        ctx.log_debug("Test message")

        assert len(ctx.debug_log) == 0

    def test_add_output(self):
        """Can add output statements."""
        ctx = ConversionContext()

        ctx.add_output("SELECT 1;")
        ctx.add_output("SELECT 2;")

        assert len(ctx.output_statements) == 2

    def test_add_output_skips_empty(self):
        """Empty statements are not added to output."""
        ctx = ConversionContext()

        ctx.add_output("")
        ctx.add_output("   ")
        ctx.add_output("\n\t")

        assert len(ctx.output_statements) == 0

    def test_get_summary(self):
        """Summary includes all relevant data."""
        ctx = ConversionContext()
        ctx.stats.statements_total = 10
        ctx.stats.statements_ddl = 3
        ctx.stats.statements_dml = 5
        ctx.stats.record_error("Error 1")
        ctx.table_names = ["table1", "table2"]

        summary = ctx.get_summary()

        assert summary["statements"]["total"] == 10
        assert summary["statements"]["ddl"] == 3
        assert summary["statements"]["dml"] == 5
        assert summary["tables_found"] == 2
        assert summary["errors"] == 1


class TestStatementType:
    """Test StatementType enum."""

    def test_statement_types_exist(self):
        """All expected statement types exist."""
        assert StatementType.DDL
        assert StatementType.DML
        assert StatementType.OTHER
        assert StatementType.EMPTY

    def test_statement_types_are_distinct(self):
        """Statement types are distinct values."""
        types = [StatementType.DDL, StatementType.DML, StatementType.OTHER, StatementType.EMPTY]
        assert len(set(types)) == 4
