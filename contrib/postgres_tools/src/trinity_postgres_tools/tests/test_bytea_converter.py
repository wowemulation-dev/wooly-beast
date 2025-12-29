"""Tests for BYTEA column hex literal conversion."""

import pytest

from trinity_postgres_tools.dml.bytea_converter import (
    convert_bytea_hex_in_insert,
    convert_hex_to_decode,
)


class TestHexToDecodeConversion:
    """Test hex literal to decode() conversion."""

    def test_simple_hex(self):
        """Test basic hex to decode conversion."""
        result = convert_hex_to_decode("0xDEADBEEF")
        assert result == "decode('DEADBEEF', 'hex')"

    def test_lowercase_hex(self):
        """Test lowercase hex is converted to uppercase."""
        result = convert_hex_to_decode("0xdeadbeef")
        assert result == "decode('DEADBEEF', 'hex')"

    def test_mixed_case_hex(self):
        """Test mixed case hex."""
        result = convert_hex_to_decode("0xDeAdBeEf")
        assert result == "decode('DEADBEEF', 'hex')"

    def test_empty_hex(self):
        """Test empty hex literal."""
        result = convert_hex_to_decode("0x")
        assert result == "decode('', 'hex')"

    def test_non_hex_unchanged(self):
        """Test non-hex values pass through unchanged."""
        result = convert_hex_to_decode("12345")
        assert result == "12345"

    def test_long_hex(self):
        """Test long hex value (like authentication key)."""
        result = convert_hex_to_decode("0x66FC5E09B8706126795F140308C8C1D8")
        assert result == "decode('66FC5E09B8706126795F140308C8C1D8', 'hex')"


class TestByteaInsertConversion:
    """Test BYTEA column INSERT statement conversion."""

    def test_build_auth_key_with_column_list(self):
        """Test build_auth_key table with explicit column list."""
        sql = """INSERT INTO build_auth_key (build, platform, arch, type, key) VALUES
(25549,'Mac','x64','WoW',0x66FC5E09B8706126795F140308C8C1D8);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "decode('66FC5E09B8706126795F140308C8C1D8', 'hex')" in result
        assert "0x66FC5E09B8706126795F140308C8C1D8" not in result

    def test_build_auth_key_without_column_list(self):
        """Test build_auth_key table without column list."""
        sql = """INSERT INTO build_auth_key VALUES
(25549,'Mac','x64','WoW',0x66FC5E09B8706126795F140308C8C1D8);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "decode('66FC5E09B8706126795F140308C8C1D8', 'hex')" in result

    def test_build_executable_hash(self):
        """Test build_executable_hash table."""
        sql = """INSERT INTO build_executable_hash VALUES
(25549,'Mac',0xABCD1234567890ABCDEF1234567890ABCDEF5678);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "decode('ABCD1234567890ABCDEF1234567890ABCDEF5678', 'hex')" in result

    def test_warden_checks(self):
        """Test warden_checks table with multiple BYTEA columns."""
        sql = """INSERT INTO warden_checks (id, type, data, result) VALUES
(1,'CHECK',0xDEADBEEF12345678,0x12345678DEADBEEF);"""
        result = convert_bytea_hex_in_insert(sql)
        # Both data and result should be converted
        assert "decode('DEADBEEF12345678', 'hex')" in result
        assert "decode('12345678DEADBEEF', 'hex')" in result

    def test_non_bytea_table_unchanged(self):
        """Test that non-BYTEA tables are not affected."""
        sql = """INSERT INTO creature_template (entry, flags) VALUES
(1234,0x00000001);"""
        result = convert_bytea_hex_in_insert(sql)
        # Should NOT be converted to decode() - this is a flag value
        assert result == sql

    def test_multiple_rows(self):
        """Test multiple row INSERT."""
        sql = """INSERT INTO build_auth_key VALUES
(25549,'Mac','x64','WoW',0x66FC5E09B8706126795F140308C8C1D8),
(25549,'Win','x64','WoW',0xABCDEF1234567890ABCDEF1234567890);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "decode('66FC5E09B8706126795F140308C8C1D8', 'hex')" in result
        assert "decode('ABCDEF1234567890ABCDEF1234567890', 'hex')" in result

    def test_non_insert_unchanged(self):
        """Test that UPDATE statements are unchanged."""
        sql = """UPDATE build_auth_key SET key = 0xDEADBEEF;"""
        result = convert_bytea_hex_in_insert(sql)
        assert result == sql

    def test_insert_with_leading_comments(self):
        """Test INSERT with comments before it (common in mysqldump output)."""
        sql = """--
-- Dumping data for table `build_auth_key`
--

INSERT INTO `build_auth_key` VALUES
(25549,'Mac','x64','WoW',0x66FC5E09B8706126795F140308C8C1D8);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "decode('66FC5E09B8706126795F140308C8C1D8', 'hex')" in result
        assert "0x66FC5E09B8706126795F140308C8C1D8" not in result

    def test_preserves_other_values(self):
        """Test that non-hex values in BYTEA tables are preserved."""
        sql = """INSERT INTO build_auth_key VALUES
(25549,'Mac','x64','WoW',0x66FC5E09B8706126795F140308C8C1D8);"""
        result = convert_bytea_hex_in_insert(sql)
        assert "25549" in result
        assert "'Mac'" in result
        assert "'x64'" in result
        assert "'WoW'" in result


class TestColumnPositionDetection:
    """Test detection of BYTEA column positions."""

    def test_correct_column_converted(self):
        """Test that only the BYTEA column is converted."""
        # In this case, column 4 (0-indexed) is 'key' which is BYTEA
        sql = """INSERT INTO build_auth_key VALUES
(12340,'Win','x86','WoW',0xABCD);"""
        result = convert_bytea_hex_in_insert(sql)
        # Only the last value (key) should be converted
        assert "decode('ABCD', 'hex')" in result
        assert result.count("decode(") == 1

    def test_integer_hex_not_converted(self):
        """Test that hex values in non-BYTEA columns are not converted."""
        # First column could contain a hex build number but shouldn't be converted
        # to decode() - it's not in a BYTEA column
        sql = """INSERT INTO build_auth_key VALUES
(0x304C,'Win','x86','WoW',0xABCD);"""
        result = convert_bytea_hex_in_insert(sql)
        # The key column should be decode(), but build should NOT
        assert "decode('ABCD', 'hex')" in result
        # The build value 0x304C should remain as-is (will be converted to int later)
        assert "0x304C" in result
