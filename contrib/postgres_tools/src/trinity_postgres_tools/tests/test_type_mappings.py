"""Tests for type mapping registry."""

import pytest

from trinity_postgres_tools.config.type_mappings import (
    TYPE_MAPPINGS,
    convert_type,
    get_type_mapping,
)


class TestTypeMappingLookup:
    """Test type mapping lookup functionality."""

    def test_get_known_type(self):
        """Can retrieve a known type mapping."""
        mapping = get_type_mapping("int")
        assert mapping is not None
        assert mapping.postgres == "integer"

    def test_get_type_case_insensitive(self):
        """Type lookup is case insensitive."""
        assert get_type_mapping("INT") == get_type_mapping("int")
        assert get_type_mapping("VarChar") == get_type_mapping("varchar")

    def test_get_unknown_type_returns_none(self):
        """Unknown types return None."""
        assert get_type_mapping("unknown_type") is None
        assert get_type_mapping("") is None


class TestConvertType:
    """Test type conversion function."""

    def test_convert_basic_int(self):
        """INT converts to integer."""
        assert convert_type("int") == "integer"

    def test_convert_unsigned_int(self):
        """Unsigned INT converts to bigint."""
        assert convert_type("int", unsigned=True) == "bigint"

    def test_convert_tinyint(self):
        """TINYINT converts to smallint."""
        assert convert_type("tinyint") == "smallint"

    def test_convert_unsigned_smallint(self):
        """Unsigned SMALLINT upcasts to integer."""
        assert convert_type("smallint", unsigned=True) == "integer"

    def test_convert_unknown_returns_none(self):
        """Unknown types return None."""
        assert convert_type("mystery") is None


class TestIntegerTypeMappings:
    """Test integer type mappings."""

    @pytest.mark.parametrize(
        "mysql_type,expected_pg,expected_unsigned",
        [
            ("tinyint", "smallint", "smallint"),
            ("smallint", "smallint", "integer"),
            ("mediumint", "integer", "integer"),
            ("int", "integer", "bigint"),
            ("integer", "integer", "bigint"),
            ("bigint", "bigint", "bigint"),
        ],
    )
    def test_integer_mappings(self, mysql_type, expected_pg, expected_unsigned):
        """Integer types map correctly."""
        mapping = get_type_mapping(mysql_type)
        assert mapping is not None
        assert mapping.postgres == expected_pg
        assert mapping.get_postgres_type(unsigned=False) == expected_pg
        assert mapping.get_postgres_type(unsigned=True) == expected_unsigned


class TestStringTypeMappings:
    """Test string type mappings."""

    @pytest.mark.parametrize(
        "mysql_type,expected_pg,preserve_size",
        [
            ("char", "char", True),
            ("varchar", "varchar", True),
            ("tinytext", "text", False),
            ("text", "text", False),
            ("mediumtext", "text", False),
            ("longtext", "text", False),
        ],
    )
    def test_string_mappings(self, mysql_type, expected_pg, preserve_size):
        """String types map correctly."""
        mapping = get_type_mapping(mysql_type)
        assert mapping is not None
        assert mapping.postgres == expected_pg
        assert mapping.preserve_size == preserve_size


class TestBinaryTypeMappings:
    """Test binary type mappings."""

    @pytest.mark.parametrize(
        "mysql_type",
        ["binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob"],
    )
    def test_binary_types_map_to_bytea(self, mysql_type):
        """All binary types map to bytea."""
        mapping = get_type_mapping(mysql_type)
        assert mapping is not None
        assert mapping.postgres == "bytea"


class TestDateTimeTypeMappings:
    """Test date/time type mappings."""

    def test_datetime_to_timestamp(self):
        """DATETIME maps to timestamp without time zone."""
        mapping = get_type_mapping("datetime")
        assert mapping is not None
        assert mapping.postgres == "timestamp without time zone"

    def test_date_preserved(self):
        """DATE maps to date."""
        mapping = get_type_mapping("date")
        assert mapping is not None
        assert mapping.postgres == "date"

    def test_year_to_smallint(self):
        """YEAR maps to smallint."""
        mapping = get_type_mapping("year")
        assert mapping is not None
        assert mapping.postgres == "smallint"


class TestSpecialTypeMappings:
    """Test special type mappings."""

    def test_enum_to_text(self):
        """ENUM maps to text."""
        mapping = get_type_mapping("enum")
        assert mapping is not None
        assert mapping.postgres == "text"

    def test_json_to_jsonb(self):
        """JSON maps to jsonb for indexing support."""
        mapping = get_type_mapping("json")
        assert mapping is not None
        assert mapping.postgres == "jsonb"


class TestTypeMappingCompleteness:
    """Test that all expected types are covered."""

    def test_all_integer_types_present(self):
        """All MySQL integer types are in registry."""
        integer_types = ["tinyint", "smallint", "mediumint", "int", "integer", "bigint"]
        for t in integer_types:
            assert t in TYPE_MAPPINGS, f"Missing integer type: {t}"

    def test_all_string_types_present(self):
        """All MySQL string types are in registry."""
        string_types = ["char", "varchar", "tinytext", "text", "mediumtext", "longtext"]
        for t in string_types:
            assert t in TYPE_MAPPINGS, f"Missing string type: {t}"

    def test_all_binary_types_present(self):
        """All MySQL binary types are in registry."""
        binary_types = ["binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob"]
        for t in binary_types:
            assert t in TYPE_MAPPINGS, f"Missing binary type: {t}"
