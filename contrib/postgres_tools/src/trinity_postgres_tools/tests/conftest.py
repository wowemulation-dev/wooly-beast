"""Pytest configuration and shared fixtures."""

import pytest

from trinity_postgres_tools.config.type_mappings import TYPE_MAPPINGS
from trinity_postgres_tools.pipeline.context import ConversionContext, ConversionOptions


@pytest.fixture
def default_context() -> ConversionContext:
    """Create a default conversion context for testing."""
    return ConversionContext()


@pytest.fixture
def debug_context() -> ConversionContext:
    """Create a context with debug mode enabled."""
    options = ConversionOptions(debug=True)
    return ConversionContext(options=options)


@pytest.fixture
def strict_context() -> ConversionContext:
    """Create a context with strict mode enabled."""
    options = ConversionOptions(strict_mode=True)
    return ConversionContext(options=options)


# Type mapping test data - generated from registry
@pytest.fixture
def all_type_mappings() -> dict:
    """Get all type mappings for parameterized tests."""
    return TYPE_MAPPINGS


# SQL fixtures for common test patterns
@pytest.fixture
def simple_create_table() -> str:
    """Simple CREATE TABLE statement."""
    return """
CREATE TABLE test_table (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


@pytest.fixture
def create_table_unsigned() -> str:
    """CREATE TABLE with unsigned types."""
    return """
CREATE TABLE unsigned_test (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    small_val TINYINT UNSIGNED DEFAULT 0,
    medium_val SMALLINT UNSIGNED,
    large_val BIGINT UNSIGNED,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
"""


@pytest.fixture
def insert_with_escapes() -> str:
    """INSERT with various escape sequences."""
    return r"""
INSERT INTO test_table (name, description) VALUES
('Zul\'Farrak', 'A desert troll city'),
('Test\\Path', 'Contains backslash'),
('Line1\nLine2', 'Contains newline'),
('Tab\there', 'Contains tab');
"""


@pytest.fixture
def insert_with_hex() -> str:
    """INSERT with hex literals."""
    return """
INSERT INTO binary_data (data) VALUES
(0x48656C6C6F),
(0xDEADBEEF),
(0x00);
"""


@pytest.fixture
def complex_alter_table() -> str:
    """Complex ALTER TABLE statement."""
    return """
ALTER TABLE characters
    ADD COLUMN level TINYINT UNSIGNED NOT NULL DEFAULT 1,
    MODIFY COLUMN name VARCHAR(100) NOT NULL,
    DROP COLUMN old_field,
    ADD INDEX idx_level (level),
    DROP FOREIGN KEY fk_old;
"""


@pytest.fixture
def mysqldump_artifacts() -> str:
    """SQL with mysqldump artifacts to remove."""
    return """
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;

LOCK TABLES `test_table` WRITE;
INSERT INTO test_table VALUES (1, 'test');
UNLOCK TABLES;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
"""


@pytest.fixture
def replace_statement() -> str:
    """MySQL REPLACE statement."""
    return """
REPLACE INTO config (key, value) VALUES ('setting1', 'value1');
"""


# Test data paths
@pytest.fixture
def fixtures_dir(tmp_path):
    """Create a temporary fixtures directory."""
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    return fixtures


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests requiring external resources"
    )
