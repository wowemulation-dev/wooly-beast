# TrinityCore PostgreSQL Migration Tools

This directory contains tools for converting TrinityCore SQL files from MySQL to PostgreSQL format.

## Important: Generated Files Not Shipped

PostgreSQL SQL files are **not included** in the repository. Users must generate them locally using these tools before using PostgreSQL as a database backend.

The generated files are excluded via `.gitignore` because:
- They are derived from the MySQL source files
- Regenerating ensures compatibility with converter improvements
- It avoids repository bloat from duplicate SQL content

Run the conversion scripts (see below) to generate PostgreSQL-compatible SQL files.

### Quick Start: Generate PostgreSQL Files

```bash
cd contrib/postgres_tools

# Install dependencies
uv sync

# Convert sql/updates/ files
./regenerate_updates.sh

# Convert sql/base/ schemas
uv run mysql-to-postgres ../../sql/base/auth_database.sql ../../sql/base/postgresql/auth_database.sql
uv run mysql-to-postgres ../../sql/base/characters_database.sql ../../sql/base/postgresql/characters_database.sql

# Convert sql/old/ updates (optional, only needed for historical migrations)
uv run mysql-to-postgres --directory ../../sql/old/3.3.5a ../../sql/old/3.3.5a
```

This creates `postgresql/` subdirectories containing converted SQL files.

## Requirements

### Tool Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) - Python package manager

### Database Requirements

- **Source Database**: MySQL 8.0+ or MariaDB 10.6+
  - Required for generating mysqldump exports that the converter can process
  - Older versions may use deprecated syntax not handled by the converter

- **Target Database**: PostgreSQL 16+
  - Required for full compatibility with generated SQL
  - Earlier versions may lack support for some converted syntax

## Installation

```bash
cd contrib/postgres_tools
uv sync
```

## Tools Overview

### mysql-to-postgres (CLI)

Converts MySQL schema and update files to PostgreSQL-compatible format using a hybrid approach:

- **DDL statements** (CREATE, ALTER, DROP, TRUNCATE) use [sqlglot](https://github.com/tobymao/sqlglot) for proper SQL parsing that preserves string literals
- **DML statements** (INSERT, UPDATE, DELETE, REPLACE) use fast regex conversion

**Features:**

- Converts MySQL data types to PostgreSQL equivalents
- Handles AUTO_INCREMENT to SERIAL conversion
- Removes MySQL-specific syntax (ENGINE, CHARACTER SET, etc.)
- Converts foreign key constraints
- Handles unsigned integer types
- Converts MySQL functions to PostgreSQL equivalents
- Properly handles mysqldump artifacts (LOCK/UNLOCK TABLES, conditional comments)

**Usage:**

```bash
# Convert schema file
uv run mysql-to-postgres input.sql output.sql

# Convert with debug output
uv run mysql-to-postgres input.sql output.sql --debug
```

### convert_updates.sh

Batch converts MySQL update files to PostgreSQL format with progress tracking.

**Features:**

- Converts all update files in sql/updates directory
- Maintains directory structure
- Skips already converted files (based on modification time)
- Progress tracking with color output
- Error reporting

**Usage:**

```bash
# Convert all updates for 3.3.5 (default)
./convert_updates.sh

# Convert for a specific branch
BRANCH_VERSION=cata_classic ./convert_updates.sh

# Convert with custom paths
./convert_updates.sh /path/to/sql/updates /path/to/output
```

### regenerate_updates.sh

Regenerates all PostgreSQL update files from MySQL versions (no skip logic).
Unlike `convert_updates.sh`, this always regenerates all files regardless of
modification time.

**Usage:**

```bash
# Regenerate all PostgreSQL files
./regenerate_updates.sh

# Regenerate for cata_classic
BRANCH_VERSION=cata_classic ./regenerate_updates.sh
```

## Directory Structure

The tools expect the following directory structure:

```
sql/updates/
├── auth/
│   └── 3.3.5/
│       ├── *.sql              # MySQL update files
│       └── postgresql/        # PostgreSQL converted files
├── characters/
│   └── 3.3.5/
│       ├── *.sql
│       └── postgresql/
└── world/
    └── 3.3.5/
        ├── *.sql
        └── postgresql/
```

## Migration Process

### Step 1: Create PostgreSQL Databases

Create three databases and a `trinity` user with access:

```bash
psql -U postgres <<EOF
CREATE USER trinity WITH PASSWORD 'trinity';
CREATE DATABASE trinity_auth OWNER trinity;
CREATE DATABASE trinity_characters OWNER trinity;
CREATE DATABASE trinity_world OWNER trinity;
EOF
```

For development, the `test-dev-environment.sh setup-postgres` script automates this using Podman containers.

### Step 2: Generate and Import PostgreSQL Schemas

First generate the PostgreSQL SQL files (see [Quick Start](#quick-start-generate-postgresql-files) above), then import:

```bash
# Import base schemas
psql -U trinity -d trinity_auth -f sql/base/postgresql/auth_database.sql
psql -U trinity -d trinity_characters -f sql/base/postgresql/characters_database.sql
psql -U trinity -d trinity_world -f sql/base/postgresql/TDB_full_world_335.sql
```

Alternatively, the servers can auto-import schemas on first startup when `Updates.EnableDatabases` is configured. See [PostgreSQL Test Setup](../../doc/PostgreSQLTestSetup.md) for details.

### Step 3: Configure TrinityCore

Build with `-DWITH_POSTGRESQL=1` and update configuration files:

**authserver.conf:**

```conf
LoginDatabaseInfo = "127.0.0.1;5432;trinity;trinity;trinity_auth"
```

**worldserver.conf:**

```conf
LoginDatabaseInfo     = "127.0.0.1;5432;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;5432;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;5432;trinity;trinity;trinity_characters"
```

## Data Type Conversions

| MySQL Type | PostgreSQL Type |
|------------|-----------------|
| TINYINT | SMALLINT |
| SMALLINT | SMALLINT |
| MEDIUMINT | INTEGER |
| INT | INTEGER |
| BIGINT | BIGINT |
| FLOAT | REAL |
| DOUBLE | DOUBLE PRECISION |
| DATETIME | TIMESTAMP WITHOUT TIME ZONE |
| TINYTEXT/TEXT/MEDIUMTEXT/LONGTEXT | TEXT |
| TINYBLOB/BLOB/MEDIUMBLOB/LONGBLOB | BYTEA |
| BINARY/VARBINARY | BYTEA |
| ENUM | TEXT |
| SET | TEXT |

## Function Conversions

| MySQL Function | PostgreSQL Equivalent |
|----------------|----------------------|
| UNIX_TIMESTAMP() | extract(epoch from now()) |
| FROM_UNIXTIME(x) | to_timestamp(x) |
| DATEDIFF(a, b) | (a::date - b::date) |
| CONCAT(a, b, ...) | a \|\| b \|\| ... |

## Troubleshooting

### Common Issues

1. **Character encoding errors**
   - Ensure PostgreSQL databases are created with UTF8 encoding
   - Check LC_COLLATE and LC_CTYPE settings

2. **Foreign key violations**
   - The converter adds CASCADE to common tables with foreign keys
   - If issues persist, check table creation order

3. **Complex queries failing**
   - Some complex MySQL queries may need manual adjustment
   - Check for MySQL-specific functions not yet handled

### Performance Tips

1. **Before import:**

   ```sql
   -- Disable autovacuum temporarily
   ALTER DATABASE trinity_world SET autovacuum = off;
   ```

2. **After import:**

   ```sql
   -- Re-enable and run vacuum
   ALTER DATABASE trinity_world SET autovacuum = on;
   VACUUM ANALYZE;
   ```

## Limitations

1. **Views** - Views require manual conversion due to function differences
2. **Stored procedures** - Not yet supported, require manual porting
3. **Triggers** - Must be recreated manually in PostgreSQL syntax
4. **Custom functions** - MySQL functions need PostgreSQL equivalents

## Support

For issues or questions:

1. Report issues on GitHub with `[PostgreSQL]` prefix
2. Include error messages and conversion logs
