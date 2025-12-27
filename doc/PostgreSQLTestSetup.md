# PostgreSQL Build Test Setup

This document describes the steps to verify the PostgreSQL build works correctly.

## Prerequisites

- PostgreSQL build completed: `./build-dev.sh --postgresql -j all` or `./test-dev-environment.sh build-postgres`
- Client data extracted to `build-client-data/` (maps, vmaps, dbc files)
- Podman installed for database containers
- PostgreSQL client installed: `/usr/bin/psql`

## 1. Database Setup

Start the PostgreSQL containers:

```bash
./test-dev-environment.sh setup-postgres
```

Verify the containers are running:

```bash
podman ps | grep trinity-335-postgres
```

Expected output shows three containers:
- `trinity-335-postgres-auth` (port 53556)
- `trinity-335-postgres-characters` (port 53557)
- `trinity-335-postgres-world` (port 53558)

The script automatically creates databases and the `trinity` user.

## 2. Import Base Schemas

Unlike MySQL, PostgreSQL requires manual schema import before the server can start.

### Import Auth Database Schema

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth \
  < sql/base/postgresql/auth_database.sql
```

### Import Characters Database Schema

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53557 -U trinity -d trinity_characters \
  < sql/base/postgresql/characters_database.sql
```

### Import World Database (TDB)

The world database is large (~280 MB). Import the converted TDB dump:

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world \
  < sql/base/postgresql/TDB_full_world_335.sql
```

This import takes several minutes due to the database size.

## 3. Add Realmlist Entry

The realmlist entry must exist before clients can connect:

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "
DELETE FROM realmlist WHERE id = 1;
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 12340);
"
```

## 4. Configure authserver

Create the configuration file:

```bash
cp install-335-postgresql/etc/authserver.conf.dist install-335-postgresql/etc/authserver.conf
```

Edit `install-335-postgresql/etc/authserver.conf` and set:

```ini
# Database connection (port 53556 for PostgreSQL 3.3.5 branch)
LoginDatabaseInfo = "127.0.0.1;53556;trinity;trinity;trinity_auth"

# Disable automatic updates (PostgreSQL doesn't support the updater yet)
Updates.EnableDatabases = 0
```

## 5. Configure worldserver

Create the configuration file:

```bash
cp install-335-postgresql/etc/worldserver.conf.dist install-335-postgresql/etc/worldserver.conf
```

Edit `install-335-postgresql/etc/worldserver.conf` and set:

```ini
# Database connections (separate containers on different ports)
LoginDatabaseInfo     = "127.0.0.1;53556;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;53558;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;53557;trinity;trinity;trinity_characters"

# Client data location (relative to install directory)
DataDir = "../build-client-data"

# Disable automatic updates (PostgreSQL doesn't support the updater yet)
Updates.EnableDatabases = 0
```

## 6. Start Servers

**Important:** Servers must be started from inside the `install-335-postgresql/` directory. The `DataDir` configuration uses relative paths (`../build-client-data`) that resolve correctly only when the working directory is the install folder.

Start authserver in one terminal:

```bash
cd install-335-postgresql
./bin/authserver
```

Expected startup indicators:
- `DatabasePool 'trinity_auth' opened successfully`
- `Added realm "Trinity" at 127.0.0.1:8085`
- `Network: Started listening on 0.0.0.0:3724`

Start worldserver in another terminal:

```bash
cd install-335-postgresql
./bin/worldserver
```

Expected startup indicators:
- `DatabasePool 'trinity_world' opened successfully`
- `DatabasePool 'trinity_characters' opened successfully`
- `Loading DBC files...` (verifies DataDir)
- `Loading vmaps...` (verifies vmap extraction)
- `World initialized`

## 7. Create Test Account

In the worldserver console:

```
account create testuser testpass
account set gmlevel testuser 3 -1
```

## 8. Client Connection Test (Optional)

Update the client realmlist:

```bash
echo "set realmlist 127.0.0.1" > ~/.wine/drive_c/users/Public/WoW/Data/enUS/realmlist.wtf
```

Launch the client:

```bash
wine ~/.wine/drive_c/users/Public/WoW/Wow.exe
```

## Port Reference

The 3.3.5 branch PostgreSQL setup uses these ports:

| Service | Port |
|---------|------|
| PostgreSQL (auth) | 53556 |
| PostgreSQL (characters) | 53557 |
| PostgreSQL (world) | 53558 |
| authserver | 3724 |
| worldserver | 8085 |

## Quick Test Commands

### Verify PostgreSQL Connectivity

```bash
# Test auth database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "SELECT 1"

# Test characters database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53557 -U trinity -d trinity_characters -c "SELECT 1"

# Test world database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c "SELECT 1"
```

### Check Table Counts

```bash
# Auth tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"

# Characters tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53557 -U trinity -d trinity_characters -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"

# World tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"
```

### Check World Database Content

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c "
SELECT
    (SELECT COUNT(*) FROM creature) as creatures,
    (SELECT COUNT(*) FROM creature_template) as creature_templates,
    (SELECT COUNT(*) FROM item_template) as items,
    (SELECT COUNT(*) FROM spell_template) as spells;
"
```

## Troubleshooting

### Database Connection Errors

- Verify containers are running: `podman ps`
- Check ports are correct (53556/53557/53558 for PostgreSQL 3.3.5)
- Test connection: `PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "SELECT 1"`

### Schema Import Fails

- Check for PostgreSQL syntax errors in converted SQL
- Verify database exists: `PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -l`
- Check disk space in container volumes

### Reserved Word Errors

PostgreSQL has stricter reserved word handling than MySQL. If you see errors like:
- `syntax error at or near "rank"` - Column needs double-quote escaping
- `syntax error at or near "group"` - Column needs double-quote escaping

These should be fixed in the converter. Report issues with specific error messages.

### Missing DBC/vmap Files

- Verify DataDir path: should be `../build-client-data` when running from install directory
- Check `build-client-data/` contains `dbc/`, `maps/`, `vmaps/`

### Realm Not Showing in Client

- Verify realmlist entry exists:
  ```bash
  PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "SELECT * FROM realmlist"
  ```
- Check authserver started without errors
- Verify client `realmlist.wtf` points to `127.0.0.1`

## Differences from MySQL Setup

| Aspect | MySQL | PostgreSQL |
|--------|-------|------------|
| Base ports | 33506-33508 | 53556-53558 |
| Client tool | `mysql` | `psql` |
| Container prefix | `trinity-335-mysql-*` | `trinity-335-postgres-*` |
| Schema import | Automatic on first run | Manual (required before server start) |
| Auto-updates | Supported | Not yet supported |
| Install directory | `install-335-mysql/` | `install-335-postgresql/` |
| Identifier quoting | Backticks `` ` `` | Double quotes `"` |

## SQL Conversion Process

The PostgreSQL backend requires all SQL files to be converted from MySQL syntax. This section describes the conversion tools and workflow.

### Converter Tool

The MySQL to PostgreSQL converter is installed via the `postgres_tools` package:

```bash
cd contrib/postgres_tools
uv sync
```

### Converting Base Schema Files

The base schema files (auth, characters) are small and convert quickly:

```bash
cd contrib/postgres_tools

# Convert auth database schema
uv run mysql-to-postgres ../../sql/base/auth_database.sql \
  ../../sql/base/postgresql/auth_database.sql

# Convert characters database schema
uv run mysql-to-postgres ../../sql/base/characters_database.sql \
  ../../sql/base/postgresql/characters_database.sql
```

### Converting World Database (TDB)

The TDB world database is large (~280 MB) and requires special handling:

```bash
cd contrib/postgres_tools

# Convert TDB dump (takes several minutes)
uv run mysql-to-postgres \
  ~/Repos/github.com/wowemulation-dev/TDB/335/25101_2025_10_21/TDB_full_world_335.25101_2025_10_21.sql \
  ../../sql/base/postgresql/TDB_full_world_335.sql \
  --debug
```

The `--debug` flag shows conversion progress and statistics.

### Converting SQL Updates

When new SQL updates are added, they need to be converted:

```bash
cd contrib/postgres_tools

# Convert a single update file
uv run mysql-to-postgres \
  ../../sql/updates/world/3.3.5/2024_01_01_00_example.sql \
  ../../sql/updates/world/3.3.5/postgresql/2024_01_01_00_example.sql

# Convert all world updates
for f in ../../sql/updates/world/3.3.5/*.sql; do
    name=$(basename "$f")
    uv run mysql-to-postgres "$f" "../../sql/updates/world/3.3.5/postgresql/$name"
done
```

### What the Converter Handles

The converter automatically transforms:

| MySQL Syntax | PostgreSQL Equivalent |
|--------------|----------------------|
| `AUTO_INCREMENT` | `SERIAL` / `BIGSERIAL` |
| `TINYINT` | `SMALLINT` |
| `MEDIUMINT` | `INTEGER` |
| `INT UNSIGNED` | `BIGINT` (promoted for range) |
| `SMALLINT UNSIGNED` | `INTEGER` (promoted for range) |
| `DOUBLE` | `DOUBLE PRECISION` |
| `DATETIME` | `TIMESTAMP` |
| `LONGTEXT` / `MEDIUMTEXT` | `TEXT` |
| `TINYBLOB` / `BLOB` / etc. | `BYTEA` |
| `0xHEX` literals | `decode('HEX', 'hex')` |
| Backtick identifiers | Double-quoted identifiers |
| `ENGINE=InnoDB` | (removed) |
| `COLLATE utf8mb4_*` | (removed) |
| `ON DUPLICATE KEY UPDATE` | `ON CONFLICT DO UPDATE` |
| `REPLACE INTO` | `INSERT ... ON CONFLICT DO UPDATE` |

### Conversion Statistics Example

When converting the TDB world database, the converter reports:

```
DEBUG: Converted data types in 186 CREATE TABLE statements
DEBUG: Removed 208 column CHARACTER SET/COLLATE declarations
DEBUG: Converted 7 UNIQUE KEY to UNIQUE constraints
DEBUG: Removed 186 MySQL-specific clauses
DEBUG: Converted 803 hex literals to decode() function calls
DEBUG: Converted 328733 escaped single quotes
```

### Regenerating All PostgreSQL Files

To regenerate all PostgreSQL SQL files from scratch:

```bash
# 1. Clean existing PostgreSQL SQL files
rm -rf sql/base/postgresql/*.sql
rm -rf sql/updates/*/postgresql/*.sql

# 2. Convert base schemas
cd contrib/postgres_tools
uv run mysql-to-postgres ../../sql/base/auth_database.sql \
  ../../sql/base/postgresql/auth_database.sql
uv run mysql-to-postgres ../../sql/base/characters_database.sql \
  ../../sql/base/postgresql/characters_database.sql

# 3. Convert TDB world database
uv run mysql-to-postgres \
  ~/Repos/github.com/wowemulation-dev/TDB/335/25101_2025_10_21/TDB_full_world_335.25101_2025_10_21.sql \
  ../../sql/base/postgresql/TDB_full_world_335.sql --debug

# 4. Convert all update files
cd ../..
./test-dev-environment.sh convert-sql
```
