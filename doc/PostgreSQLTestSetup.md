# PostgreSQL Build Test Setup

This document describes the steps to verify the PostgreSQL build works correctly.

## Prerequisites

- PostgreSQL build completed: `./build-dev.sh --postgresql -j all` or `./test-dev-environment.sh build-postgres`
- Client data extracted to `build-335-client-data/` (maps, vmaps, dbc files)
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

## 2. Schema Import Options

PostgreSQL supports two import methods: automatic (recommended) and manual.

### Option A: Automatic Import (Recommended)

The TrinityCore servers can automatically import base schemas and apply updates on first run, just like MySQL. Each server is responsible for its own databases:

- **authserver**: Manages the auth database only
- **worldserver**: Manages characters and world databases only

Configure auto-updates in the config files:

```ini
# In authserver.conf
Updates.EnableDatabases = 1  # 1 = auth

# In worldserver.conf
Updates.EnableDatabases = 6  # 2 (characters) + 4 (world) = 6
# Note: worldserver should NOT update auth (value 1)
```

**Important: Start authserver first** when using empty databases. The worldserver connects to the auth database for account validation, so the auth schema must exist before worldserver can start properly.

On first startup with empty databases, the servers will:
1. Detect empty databases
2. Import base schemas from `sql/base/postgresql/`
3. Apply any pending updates from `sql/updates/<db>/3.3.5/postgresql/`

### Option B: Manual Import

For debugging or when you need more control, import schemas manually:

```bash
# Import auth database schema
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth \
  < sql/base/postgresql/auth_database.sql

# Import characters database schema
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53557 -U trinity -d trinity_characters \
  < sql/base/postgresql/characters_database.sql

# Import world database (TDB) - takes several minutes
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world \
  < sql/base/postgresql/TDB_full_world_335.sql
```

## 3. Add Realmlist Entry

The realmlist entry is added automatically when using auto-import. For manual imports:

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

# Source directory for SQL files (required for auto-updates)
SourceDirectory = "/path/to/wooly-beast"

# Enable automatic updates (1 = auth database)
Updates.EnableDatabases = 1
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
DataDir = "../build-335-client-data"

# Source directory for SQL files (required for auto-updates)
SourceDirectory = "/path/to/wooly-beast"

# Enable automatic updates (2 = characters, 4 = world, 6 = both)
Updates.EnableDatabases = 6

# Disable console for automated testing
Console.Enable = 0
```

## 6. Start Servers

**Important notes:**
- Servers must be started from inside the `install-335-postgresql/` directory (DataDir uses relative paths)
- **Start authserver first** and wait for it to complete database setup before starting worldserver
- Each server handles its own databases - authserver updates auth, worldserver updates characters and world

Start authserver in one terminal:

```bash
cd install-335-postgresql
./bin/authserver
```

Expected startup indicators:
- `DatabasePool 'trinity_auth' opened successfully`
- `Database Auth is empty, auto populating it...` (first run only)
- `Applied update "auth_database.sql" successfully`
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

### Check Update History

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "
SELECT state, COUNT(*) FROM updates GROUP BY state;
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

- Verify DataDir path: should be `../build-335-client-data` when running from install directory
- Check `build-335-client-data/` contains `dbc/`, `maps/`, `vmaps/`

### Realm Not Showing in Client

- Verify realmlist entry exists:
  ```bash
  PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "SELECT * FROM realmlist"
  ```
- Check authserver started without errors
- Verify client `realmlist.wtf` points to `127.0.0.1`

### "Dirty Files" Warning on Startup

If you see warnings like "X dirty files applied to your database, but they are now missing", this means:
- The `updates` table references files that don't exist in the expected path
- Archived updates should be in `sql/old/3.3.5a/<db>/postgresql/`
- Run the converter with `-d` flag to regenerate archived updates

### Encoding Errors During Conversion

If the converter fails with errors like `'utf-8' codec can't decode byte 0x92`, this indicates Windows-1252 encoding in the source file. Common issues:
- Smart quotes (`'` → 0x92) instead of ASCII apostrophes (`'`)
- Em dashes, ellipsis, or other Windows-specific characters

Fix by editing the original MySQL file to use ASCII equivalents:
- Replace smart quotes with standard apostrophes
- For SQL strings, use `''` (two single quotes) to escape apostrophes

## Update System Internals

The TrinityCore update system tracks applied SQL files in two tables within each database.

### The `updates` Table

Tracks every SQL file that has been applied:

```sql
SELECT name, hash, state, speed FROM updates ORDER BY name LIMIT 5;
```

States:
- `RELEASED` - Current updates in `sql/updates/<db>/3.3.5/postgresql/`
- `ARCHIVED` - Historical updates in `sql/old/3.3.5a/<db>/postgresql/`

### The `updates_include` Table

Defines which directories the updater searches for SQL files:

```sql
SELECT * FROM updates_include;
```

PostgreSQL base schemas set these paths:
- `$/sql/updates/<db>/3.3.5/postgresql` (state: RELEASED)
- `$/sql/old/3.3.5a/<db>/postgresql` (state: ARCHIVED)

The `$` is replaced with `SourceDirectory` from the config file.

### How Update Discovery Works

1. Server reads `updates_include` to find search directories
2. For each directory, recursively finds `.sql` files
3. Compares found files against `updates` table
4. Applies any new files, recording them in `updates`
5. Warns about "dirty" files (in `updates` but not on disk)

For PostgreSQL, `UpdateFetcher.cpp` appends `/postgresql` to update paths automatically.

### Code References

The PostgreSQL update path logic is in `src/server/database/Updater/UpdateFetcher.cpp`:

- Lines ~175-180: Sets update path to `/sql/updates/<db>/3.3.5/postgresql`
- Lines ~198-202: Sets archive path to `/sql/old/3.3.5a/<db>/postgresql`

Key preprocessor checks:
```cpp
#ifdef WITH_POSTGRESQL
    // PostgreSQL uses subdirectory for SQL files
    std::string archivePath = ... + "/postgresql";
#else
    // MySQL uses main directory
    std::string archivePath = ...;
#endif
```

## Differences from MySQL Setup

| Aspect | MySQL | PostgreSQL |
|--------|-------|------------|
| Base ports | 33506-33508 | 53556-53558 |
| Client tool | `mysql` | `psql` |
| Container prefix | `trinity-335-mysql-*` | `trinity-335-postgres-*` |
| Schema import | Automatic on first run | Automatic on first run |
| Auto-updates | Supported | Supported |
| Install directory | `install-335-mysql/` | `install-335-postgresql/` |
| Identifier quoting | Backticks `` ` `` | Double quotes `"` |
| Update paths | `sql/updates/<db>/3.3.5/` | `sql/updates/<db>/3.3.5/postgresql/` |
| Archive paths | `sql/old/3.3.5a/<db>/` | `sql/old/3.3.5a/<db>/postgresql/` |

## SQL Conversion Process

The PostgreSQL backend requires all SQL files to be converted from MySQL syntax. This section describes the conversion tools and workflow.

### Converter Tool

The MySQL to PostgreSQL converter is installed via the `postgres_tools` package:

```bash
cd contrib/postgres_tools
uv sync
```

### Converting Single Files

```bash
cd contrib/postgres_tools

# Convert a single file
uv run mysql-to-postgres input.sql output.sql

# With debug output
uv run mysql-to-postgres input.sql output.sql --debug
```

### Converting Directories

The converter supports batch conversion of entire directories:

```bash
cd contrib/postgres_tools

# Convert all SQL files in a directory (creates postgresql/ subdirectory)
uv run mysql-to-postgres -d /path/to/sql/updates/auth/3.3.5

# Result: /path/to/sql/updates/auth/3.3.5/postgresql/*.sql
```

The `-d` flag:
- Recursively finds all `.sql` files
- Preserves directory structure in the output
- Creates a `postgresql/` subdirectory automatically
- Skips files already in `postgresql/` directories

### Converting Archived Updates

To regenerate all archived updates for PostgreSQL:

```bash
cd contrib/postgres_tools

# Convert auth archives
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/auth

# Convert characters archives
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/characters

# Convert world archives
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/world

# Convert TDB migration directories
for dir in ../../sql/old/3.3.5a/TDB*/; do
    uv run mysql-to-postgres -d "$dir"
done
```

Current file counts (as of initial conversion):

| Directory | Files |
|-----------|-------|
| `sql/old/3.3.5a/auth/` | 121 |
| `sql/old/3.3.5a/characters/` | 91 |
| `sql/old/3.3.5a/world/` | 6,853 |
| `sql/old/3.3.5a/TDB*/` | 4,550 |
| **Total** | **11,615** |

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
| `MODIFY COLUMN` | `ALTER COLUMN TYPE` |
| `CHANGE column` | `RENAME COLUMN` + `ALTER COLUMN TYPE` |
| `DROP PRIMARY KEY` | `DROP CONSTRAINT table_pkey` |
| `RENAME TABLE` | `ALTER TABLE RENAME TO` |
| `AFTER column` | (removed - PostgreSQL doesn't support column ordering) |
| `CONVERT TO CHARACTER SET` | (removed - PostgreSQL uses database-level encoding) |

### Regenerating All PostgreSQL Files

To regenerate all PostgreSQL SQL files from scratch:

```bash
# 1. Clean existing PostgreSQL SQL files
rm -rf sql/base/postgresql/*.sql
rm -rf sql/updates/*/3.3.5/postgresql/*.sql
rm -rf sql/old/3.3.5a/*/postgresql/

# 2. Convert base schemas
cd contrib/postgres_tools
uv run mysql-to-postgres ../../sql/base/auth_database.sql \
  ../../sql/base/postgresql/auth_database.sql
uv run mysql-to-postgres ../../sql/base/characters_database.sql \
  ../../sql/base/postgresql/characters_database.sql

# 3. Convert TDB world database
uv run mysql-to-postgres \
  ~/Repos/github.com/TrinityCore/TDB/335/25101_2025_10_21/TDB_full_world_335.25101_2025_10_21.sql \
  ../../sql/base/postgresql/TDB_full_world_335.sql --debug

# 4. Convert update directories
uv run mysql-to-postgres -d ../../sql/updates/auth/3.3.5
uv run mysql-to-postgres -d ../../sql/updates/characters/3.3.5
uv run mysql-to-postgres -d ../../sql/updates/world/3.3.5

# 5. Convert archived updates
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/auth
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/characters
uv run mysql-to-postgres -d ../../sql/old/3.3.5a/world
for dir in ../../sql/old/3.3.5a/TDB*/; do
    uv run mysql-to-postgres -d "$dir"
done
```
