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
podman ps | grep trinity-cata-postgres
```

Expected output shows four containers:
- `trinity-cata-postgres-auth` (port 54366)
- `trinity-cata-postgres-characters` (port 54367)
- `trinity-cata-postgres-world` (port 54368)
- `trinity-cata-postgres-hotfixes` (port 54369)

The script automatically creates databases and the `trinity` user.

## 2. Schema Import Options

PostgreSQL supports two import methods: automatic (recommended) and manual.

### Option A: Automatic Import (Recommended)

The TrinityCore servers can automatically import base schemas and apply updates on first run, just like MySQL. Each server is responsible for its own databases:

- **bnetserver**: Manages the auth database only
- **worldserver**: Manages characters, world, and hotfixes databases

Configure auto-updates in the config files:

```ini
# In bnetserver.conf
Updates.EnableDatabases = 1  # 1 = auth

# In worldserver.conf
Updates.EnableDatabases = 14  # 2 (characters) + 4 (world) + 8 (hotfixes) = 14
# Note: worldserver should NOT update auth (value 1)
```

**Important: Start bnetserver first** when using empty databases. The worldserver connects to the auth database for account validation, so the auth schema must exist before worldserver can start properly.

On first startup with empty databases, the servers will:
1. Detect empty databases
2. Import base schemas from `sql/base/postgresql/`
3. Apply any pending updates from `sql/updates/<db>/cata_classic/postgresql/`

### Option B: Manual Import

For debugging or when you need more control, import schemas manually:

```bash
# Import auth database schema
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth \
  < sql/base/postgresql/auth_database.sql

# Import characters database schema
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54367 -U trinity -d characters \
  < sql/base/postgresql/characters_database.sql

# Import world database (TDB) - takes several minutes
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54368 -U trinity -d world \
  < sql/base/postgresql/TDB_full_world_442.sql

# Import hotfixes database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54369 -U trinity -d hotfixes \
  < sql/base/postgresql/TDB_full_hotfixes_442.sql
```

## 3. Add Realmlist Entry

The realmlist entry is added automatically when using auto-import. For manual imports:

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "
DELETE FROM realmlist WHERE id = 1;
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 15595);
"
```

## 4. Configure bnetserver

Create the configuration file:

```bash
cp install-cata-postgresql/etc/bnetserver.conf.dist install-cata-postgresql/etc/bnetserver.conf
```

Edit `install-cata-postgresql/etc/bnetserver.conf` and set:

```ini
# Database connection (port 54366 for PostgreSQL cata_classic branch)
LoginDatabaseInfo = "127.0.0.1;54366;trinity;trinity;auth"

# Source directory for SQL files (required for auto-updates)
SourceDirectory = "/path/to/wooly-beast"

# Enable automatic updates (1 = auth database)
Updates.EnableDatabases = 1
```

## 5. Configure worldserver

Create the configuration file:

```bash
cp install-cata-postgresql/etc/worldserver.conf.dist install-cata-postgresql/etc/worldserver.conf
```

Edit `install-cata-postgresql/etc/worldserver.conf` and set:

```ini
# Database connections (separate containers on different ports)
LoginDatabaseInfo     = "127.0.0.1;54366;trinity;trinity;auth"
WorldDatabaseInfo     = "127.0.0.1;54368;trinity;trinity;world"
CharacterDatabaseInfo = "127.0.0.1;54367;trinity;trinity;characters"
HotfixDatabaseInfo    = "127.0.0.1;54369;trinity;trinity;hotfixes"

# Client data location (relative to install directory)
DataDir = "../build-client-data"

# Source directory for SQL files (required for auto-updates)
SourceDirectory = "/path/to/wooly-beast"

# Enable automatic updates (2 = characters, 4 = world, 8 = hotfixes, 14 = all three)
Updates.EnableDatabases = 14

# Disable console for automated testing
Console.Enable = 0
```

## 6. Start Servers

**Important notes:**
- Servers must be started from inside the `install-cata-postgresql/` directory (DataDir uses relative paths)
- **Start bnetserver first** and wait for it to complete database setup before starting worldserver
- Each server handles its own databases - bnetserver updates auth, worldserver updates characters, world, and hotfixes

Start bnetserver in one terminal:

```bash
cd install-cata-postgresql
./bin/bnetserver
```

Expected startup indicators:
- `DatabasePool 'auth' opened successfully`
- `Database Login is empty, auto populating it...` (first run only)
- `Applied update "auth_database.sql" successfully`
- `Added realm "Trinity" at 127.0.0.1:8085`
- `Network: Started listening on 0.0.0.0:1119`

Start worldserver in another terminal:

```bash
cd install-cata-postgresql
./bin/worldserver
```

Expected startup indicators:
- `DatabasePool 'world' opened successfully`
- `DatabasePool 'characters' opened successfully`
- `DatabasePool 'hotfixes' opened successfully`
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

Update the client realmlist and launch the client. For Cata Classic, you'll need the appropriate client version (4.4.x).

## Port Reference

The cata_classic branch PostgreSQL setup uses these ports:

| Service | Port |
|---------|------|
| PostgreSQL (auth) | 54366 |
| PostgreSQL (characters) | 54367 |
| PostgreSQL (world) | 54368 |
| PostgreSQL (hotfixes) | 54369 |
| bnetserver | 1119 |
| worldserver | 8085 |

## Quick Test Commands

### Verify PostgreSQL Connectivity

```bash
# Test auth database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "SELECT 1"

# Test characters database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54367 -U trinity -d characters -c "SELECT 1"

# Test world database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54368 -U trinity -d world -c "SELECT 1"

# Test hotfixes database
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54369 -U trinity -d hotfixes -c "SELECT 1"
```

### Check Table Counts

```bash
# Auth tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"

# Characters tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54367 -U trinity -d characters -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"

# World tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54368 -U trinity -d world -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"

# Hotfixes tables
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54369 -U trinity -d hotfixes -c "
SELECT schemaname, COUNT(*) as tables FROM pg_tables WHERE schemaname = 'public' GROUP BY schemaname;
"
```

### Check Update History

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "
SELECT state, COUNT(*) FROM updates GROUP BY state;
"
```

### Check World Database Content

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 54368 -U trinity -d world -c "
SELECT
    (SELECT COUNT(*) FROM creature) as creatures,
    (SELECT COUNT(*) FROM creature_template) as creature_templates,
    (SELECT COUNT(*) FROM item_template) as items;
"
```

## Troubleshooting

### Database Connection Errors

- Verify containers are running: `podman ps`
- Check ports are correct (54366/54367/54368/54369 for PostgreSQL cata_classic)
- Test connection: `PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "SELECT 1"`

### Schema Import Fails

- Check for PostgreSQL syntax errors in converted SQL
- Verify database exists: `PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -l`
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
  PGPASSWORD=trinity psql -h 127.0.0.1 -p 54366 -U trinity -d auth -c "SELECT * FROM realmlist"
  ```
- Check bnetserver started without errors
- Verify client connects to correct address

### "Dirty Files" Warning on Startup

If you see warnings like "X dirty files applied to your database, but they are now missing", this means:
- The `updates` table references files that don't exist in the expected path
- Archived updates should be in `sql/old/cata_classic/<db>/postgresql/`
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
- `RELEASED` - Current updates in `sql/updates/<db>/cata_classic/postgresql/`
- `ARCHIVED` - Historical updates in `sql/old/cata_classic/<db>/postgresql/`

### The `updates_include` Table

Defines which directories the updater searches for SQL files:

```sql
SELECT * FROM updates_include;
```

PostgreSQL base schemas set these paths:
- `$/sql/updates/<db>/cata_classic/postgresql` (state: RELEASED)
- `$/sql/old/cata_classic/<db>/postgresql` (state: ARCHIVED)

The `$` is replaced with `SourceDirectory` from the config file.

### How Update Discovery Works

1. Server reads `updates_include` to find search directories
2. For each directory, recursively finds `.sql` files
3. Compares found files against `updates` table
4. Applies any new files, recording them in `updates`
5. Warns about "dirty" files (in `updates` but not on disk)

For PostgreSQL, `UpdateFetcher.cpp` appends `/postgresql` to update paths automatically.

## Differences from MySQL Setup

| Aspect | MySQL | PostgreSQL |
|--------|-------|------------|
| Base ports | 33606-33609 | 54366-54369 |
| Client tool | `mysql` | `psql` |
| Container prefix | `trinity-cata-mysql-*` | `trinity-cata-postgres-*` |
| Schema import | Automatic on first run | Automatic on first run |
| Auto-updates | Supported | Supported |
| Install directory | `install-cata-mysql/` | `install-cata-postgresql/` |
| Identifier quoting | Backticks `` ` `` | Double quotes `"` |
| Update paths | `sql/updates/<db>/cata_classic/` | `sql/updates/<db>/cata_classic/postgresql/` |
| Archive paths | `sql/old/cata_classic/<db>/` | `sql/old/cata_classic/<db>/postgresql/` |

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
uv run mysql-to-postgres -d /path/to/sql/updates/auth/cata_classic

# Result: /path/to/sql/updates/auth/cata_classic/postgresql/*.sql
```

The `-d` flag:
- Recursively finds all `.sql` files
- Preserves directory structure in the output
- Creates a `postgresql/` subdirectory automatically
- Skips files already in `postgresql/` directories

### Regenerating All PostgreSQL Files

To regenerate all PostgreSQL SQL files from scratch:

```bash
# 1. Clean existing PostgreSQL SQL files
rm -rf sql/base/postgresql/*.sql
rm -rf sql/updates/*/cata_classic/postgresql/*.sql

# 2. Convert base schemas
cd contrib/postgres_tools
uv run mysql-to-postgres ../../sql/base/auth_database.sql \
  ../../sql/base/postgresql/auth_database.sql
uv run mysql-to-postgres ../../sql/base/characters_database.sql \
  ../../sql/base/postgresql/characters_database.sql

# 3. Convert TDB world database
uv run mysql-to-postgres \
  ~/Repos/github.com/TrinityCore/TDB/cata_classic/25051_2025_05_11/TDB_full_world_442.25051_2025_05_11.sql \
  ../../sql/base/postgresql/TDB_full_world_442.sql --debug

# 4. Convert TDB hotfixes database
uv run mysql-to-postgres \
  ~/Repos/github.com/TrinityCore/TDB/cata_classic/25051_2025_05_11/TDB_full_hotfixes_442.25051_2025_05_11.sql \
  ../../sql/base/postgresql/TDB_full_hotfixes_442.sql --debug

# 5. Convert update directories
uv run mysql-to-postgres -d ../../sql/updates/auth/cata_classic
uv run mysql-to-postgres -d ../../sql/updates/characters/cata_classic
uv run mysql-to-postgres -d ../../sql/updates/world/cata_classic
uv run mysql-to-postgres -d ../../sql/updates/hotfixes/cata_classic
```
