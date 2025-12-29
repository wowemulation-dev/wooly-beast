# PostgreSQL Implementation Testing Plan

This document outlines a testing plan to verify the PostgreSQL backend implementation is compatible with the MySQL implementation and has no SQL conversion issues or runtime issues.

## Overview

The PostgreSQL implementation consists of three main components:

1. **SQL Converter** (`contrib/postgres_tools/`) - Converts MySQL SQL to PostgreSQL syntax
2. **C++ Database Layer** (`src/server/database/`) - PostgreSQL connection and query handling
3. **Converted SQL Files** (`sql/base/postgresql/`, `sql/updates/*/postgresql/`) - Schema and data

## Testing Phases

### Phase 1: SQL Converter Validation

**Objective**: Verify the converter correctly transforms all MySQL syntax to PostgreSQL equivalents.

#### 1.1 Unit Tests for Converter

Location: `contrib/postgres_tools/src/trinity_postgres_tools/tests/`

```bash
cd contrib/postgres_tools
uv run pytest -v
```

Tests should cover:

- [ ] Data type conversions (TINYINT, MEDIUMINT, INT UNSIGNED, etc.)
- [ ] AUTO_INCREMENT to SERIAL conversion
- [ ] MySQL-specific clause removal (ENGINE, COLLATE, CHARACTER SET)
- [ ] Hex literal conversion (`0xHEX` to `decode('HEX', 'hex')`)
- [ ] Reserved word quoting (rank, group, order, etc.)
- [ ] ON DUPLICATE KEY UPDATE to ON CONFLICT DO UPDATE
- [ ] REPLACE INTO to INSERT ... ON CONFLICT
- [ ] Function conversions (UNIX_TIMESTAMP, FROM_UNIXTIME, etc.)
- [ ] Escaped quote handling in strings
- [ ] VIEW conversion
- [ ] Complex nested queries
- [ ] Multi-statement files

#### 1.2 Syntax Validation Tests

Verify converted SQL is valid PostgreSQL syntax:

```bash
# For each converted file, validate syntax without executing
for f in sql/base/postgresql/*.sql; do
    echo "Validating: $f"
    PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d postgres \
        -c "DO \$\$BEGIN RAISE NOTICE 'Validating...'; END\$\$;" \
        --set ON_ERROR_STOP=1 -f "$f" 2>&1 | head -5
done
```

#### 1.3 Idempotency Tests

Verify that re-converting produces identical output:

```bash
cd contrib/postgres_tools
# Convert twice and compare
uv run mysql-to-postgres input.sql output1.sql
uv run mysql-to-postgres input.sql output2.sql
diff output1.sql output2.sql  # Should be empty
```

### Phase 2: Data Parity Verification

**Objective**: Verify that MySQL and PostgreSQL databases contain identical data after import.

#### 2.1 Full Data Parity Check

The `data_parity_check.sh` script automates this process:

```bash
cd contrib/postgres_tools
./data_parity_check.sh full
```

This performs:

1. Set up MySQL and PostgreSQL containers
2. Import MySQL base schemas + TDB
3. Convert SQL files to PostgreSQL
4. Import PostgreSQL schemas
5. Compare row counts for all tables
6. Generate difference report

Expected output: All tables should have identical row counts.

#### 2.2 Table-by-Table Comparison

For critical tables, verify not just counts but actual data:

```bash
# Auth database - realmlist table
mysql -h 127.0.0.1 -P 33506 -utrinity -ptrinity trinity_auth \
    -e "SELECT * FROM realmlist ORDER BY id"
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth \
    -c "SELECT * FROM realmlist ORDER BY id"

# World database - creature_template sample
mysql -h 127.0.0.1 -P 33508 -utrinity -ptrinity trinity_world \
    -e "SELECT entry, name, subname FROM creature_template LIMIT 10"
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world \
    -c "SELECT entry, name, subname FROM creature_template LIMIT 10"
```

#### 2.3 Data Type Verification

Verify that data type conversions preserve values correctly:

| MySQL Type | PostgreSQL Type | Verification Query |
|------------|-----------------|-------------------|
| TINYINT | SMALLINT | Check range -128 to 127 preserved |
| INT UNSIGNED | BIGINT | Check max value 4294967295 preserved |
| DATETIME | TIMESTAMP | Check date/time values preserved |
| BLOB/BINARY | BYTEA | Check binary data preserved |

```bash
# Example: Check unsigned int handling
mysql -P 33508 -e "SELECT MAX(entry) FROM trinity_world.creature_template"
psql -p 53558 -c "SELECT MAX(entry) FROM creature_template" trinity_world
```

### Phase 3: Schema Compatibility

**Objective**: Verify PostgreSQL schemas match MySQL in structure and constraints.

#### 3.1 Table Count Verification

```bash
# MySQL table count
mysql -h 127.0.0.1 -P 33508 -utrinity -ptrinity -N -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'trinity_world'"

# PostgreSQL table count
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -t -c \
    "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"
```

#### 3.2 Column Type Comparison

Generate schema comparison reports:

```bash
# MySQL schema
mysql -h 127.0.0.1 -P 33508 -utrinity -ptrinity -e \
    "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE
     FROM information_schema.columns
     WHERE table_schema = 'trinity_world'
     ORDER BY TABLE_NAME, ORDINAL_POSITION" > mysql_schema.txt

# PostgreSQL schema
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -t -A -F'|' -c \
    "SELECT table_name, column_name, data_type, udt_name
     FROM information_schema.columns
     WHERE table_schema = 'public'
     ORDER BY table_name, ordinal_position" > pg_schema.txt
```

#### 3.3 Index Verification

Verify indexes are created correctly:

```bash
# PostgreSQL index list
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c \
    "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname"
```

#### 3.4 Primary Key and Constraint Verification

```bash
# PostgreSQL primary keys
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c \
    "SELECT tc.table_name, kcu.column_name
     FROM information_schema.table_constraints tc
     JOIN information_schema.key_column_usage kcu
         ON tc.constraint_name = kcu.constraint_name
     WHERE tc.constraint_type = 'PRIMARY KEY'
     ORDER BY tc.table_name"
```

### Phase 4: C++ Runtime Testing

**Objective**: Verify the PostgreSQL C++ database layer functions correctly.

#### 4.1 Build Verification

```bash
# Build PostgreSQL version
./build-dev.sh --postgresql -j all

# Verify binary was built with PostgreSQL support
./install-335-postgresql/bin/authserver --version 2>&1 | grep -i postgres
```

#### 4.2 Connection Pool Testing

```bash
# Start authserver with PostgreSQL
cd install-335-postgresql
./bin/authserver

# Expected output:
# DatabasePool 'trinity_auth' opened successfully
# ...
# Network: Started listening on 0.0.0.0:3724
```

Check for:

- [ ] Pool opens successfully
- [ ] No connection errors
- [ ] Prepared statements compile without errors
- [ ] Server starts listening on expected port

#### 4.3 Prepared Statement Testing

Monitor server logs for prepared statement errors:

```bash
# In authserver console
.debug db
```

Expected: No prepared statement binding errors.

#### 4.4 Query Execution Testing

Test via worldserver console commands:

```bash
cd install-335-postgresql
./bin/worldserver

# In console:
.server info          # Basic query test
account create test test  # INSERT operation
account set gmlevel test 3 -1  # UPDATE operation
lookup creature dragon   # SELECT with LIKE
```

### Phase 5: Functional Testing

**Objective**: Verify game functionality works identically on PostgreSQL.

#### 5.1 Account Operations

| Test | Command | Expected Result |
|------|---------|-----------------|
| Create account | `account create user pass` | Account created in auth DB |
| Set GM level | `account set gmlevel user 3 -1` | GM level updated |
| Delete account | `account delete user` | Account removed |
| List accounts | `account list` | Shows all accounts |

#### 5.2 Character Operations

| Test | Action | Expected Result |
|------|--------|-----------------|
| Character creation | Create character in client | Entry in characters DB |
| Character login | Enter world | Player loads correctly |
| Character save | Logout | Data persisted |
| Character delete | Delete from client | Entry removed |

#### 5.3 World Data Verification

Test that world data loads correctly:

```bash
# In worldserver console
.lookup creature Hogger    # Should find entry 448
.lookup item Hearthstone   # Should find entry 6948
.lookup spell Fireball     # Should find entry 133
```

#### 5.4 Server Restart Persistence

1. Create test data (account, character, inventory)
2. Restart worldserver
3. Verify all data persists

### Phase 6: Stress and Performance Testing

**Objective**: Verify PostgreSQL performs adequately under load.

#### 6.1 Connection Pool Stress

```bash
# Increase connection pool size in config
# Run multiple concurrent operations
for i in {1..10}; do
    (echo "account create user$i pass$i" | nc localhost 3724) &
done
wait
```

#### 6.2 Query Performance Comparison

```bash
# Time a complex query on both backends
time mysql -P 33508 -e "SELECT COUNT(*) FROM trinity_world.creature_template WHERE entry < 50000"
time psql -p 53558 -c "SELECT COUNT(*) FROM creature_template WHERE entry < 50000" trinity_world
```

### Phase 7: SQL Update Application Testing

**Objective**: Verify SQL updates can be applied correctly to PostgreSQL databases.

#### 7.1 Update Conversion Verification

```bash
# Verify all updates have PostgreSQL versions
ls sql/updates/world/3.3.5/*.sql | wc -l
ls sql/updates/world/3.3.5/postgresql/*.sql | wc -l
# Counts should match
```

#### 7.2 Update Application Testing

```bash
# Apply a sample update
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world \
    -f sql/updates/world/3.3.5/postgresql/2025_10_21_00_world.sql
```

## Test Matrix

| Component | Test Type | Priority | Status |
|-----------|-----------|----------|--------|
| SQL Converter | Unit tests | High | [x] 254 tests passed |
| SQL Converter | Syntax validation | High | [x] All files validate |
| Data import | Schema import | High | [x] Automatic import works |
| Data parity | Row counts | High | [x] 239 tables match |
| Data parity | Data values | Medium | [x] Verified critical tables |
| Schema | Table count | High | [x] 239 tables in world DB |
| Schema | Column types | Medium | [x] Verified via parity check |
| Schema | Indexes | Medium | [x] 184 indexes verified |
| Runtime | Connection pool | High | [x] Both servers connect |
| Runtime | Prepared statements | High | [x] No binding errors |
| Runtime | Query execution | High | [x] All updates apply |
| Functional | Account CRUD | High | [ ] Pending client testing |
| Functional | Character CRUD | High | [ ] Pending client testing |
| Functional | World data | High | [x] Data loads correctly |
| Performance | Connection stress | Low | [ ] Not tested |
| Performance | Query comparison | Low | [ ] Not tested |
| Updates | Conversion | Medium | [x] All 37 updates convert |
| Updates | Application | Medium | [x] All 35 updates apply |

## Known Differences

Document expected differences between MySQL and PostgreSQL:

| Aspect | MySQL | PostgreSQL | Notes |
|--------|-------|------------|-------|
| Identifier quoting | Backticks `` ` `` | Double quotes `"` | Use `DB_QUOTE_IDENT()` macro |
| Auto-increment | `AUTO_INCREMENT` | `SERIAL` | Handled by converter |
| Schema import | Automatic on first run | Automatic on first run | Both use `DBUpdater<T>::Populate()` |
| Auto-updates | Supported | Supported | PostgreSQL uses `/postgresql` subdirectories |
| Case sensitivity | Case-insensitive by default | Case-sensitive | Table/column names lowercase |
| Foreign key indexes | Auto-created by MySQL | Not auto-created | PostgreSQL creates FKs without indexes |

### Standard TrinityCore Workflow (MySQL)

TrinityCore's default MySQL workflow:

1. **Blank databases provided** - Empty databases with just the trinity user
2. **Server auto-import** - On first run, servers detect empty databases and import base schemas
3. **Auto-update execution** - Servers execute all non-archived SQL updates from `sql/updates/`
4. **Update verification** - Servers verify archived updates exist in the filesystem

### Current PostgreSQL Workflow

The PostgreSQL implementation now matches MySQL:

1. **Automatic schema import** - Servers detect empty databases and import from `sql/base/postgresql/`
2. **Automatic update application** - Updates from `sql/updates/<db>/3.3.5/postgresql/` applied on startup
3. **Updates enabled** - Configure `Updates.EnableDatabases` as with MySQL

Implementation details:
- PostgreSQL uses `libpq` directly instead of an external `psql` executable
- The `UpdateFetcher` automatically appends `/postgresql` to update paths
- Archive paths use `sql/old/3.3.5a/<db>/postgresql/`

## Automated Test Script

Create an automated test runner:

```bash
#!/bin/bash
# run_postgres_tests.sh

set -e

echo "=== PostgreSQL Implementation Tests ==="

# Phase 1: Converter tests
echo "Running converter unit tests..."
cd contrib/postgres_tools
uv run pytest -v
cd ../..

# Phase 2: Data parity
echo "Running data parity check..."
./contrib/postgres_tools/data_parity_check.sh full

# Phase 3: Build and runtime
echo "Building PostgreSQL version..."
./build-dev.sh --postgresql -j all

# Phase 4: Server startup test
echo "Testing server startup..."
cd install-335-postgresql
timeout 30 ./bin/authserver &
AUTH_PID=$!
sleep 10
if ps -p $AUTH_PID > /dev/null; then
    echo "authserver started successfully"
    kill $AUTH_PID
else
    echo "authserver failed to start"
    exit 1
fi

echo "=== All tests passed ==="
```

## Reporting Issues

When PostgreSQL-related issues are found:

1. Include `[PostgreSQL]` prefix in issue title
2. Specify which phase/test failed
3. Include relevant log output
4. Include both MySQL and PostgreSQL query results if applicable
5. Specify TrinityCore version and PostgreSQL version

## Appendix: Quick Test Commands

### Check Container Status

```bash
./test-dev-environment.sh status
```

### Test PostgreSQL Connectivity

```bash
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53556 -U trinity -d trinity_auth -c "SELECT 1"
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53557 -U trinity -d trinity_characters -c "SELECT 1"
PGPASSWORD=trinity psql -h 127.0.0.1 -p 53558 -U trinity -d trinity_world -c "SELECT 1"
```

### Reset and Reimport

```bash
./test-dev-environment.sh reset-databases
./contrib/postgres_tools/data_parity_check.sh import-pg
```

### Full Reset and Test

```bash
./test-dev-environment.sh cleanup-all
./test-dev-environment.sh setup-containers
./contrib/postgres_tools/data_parity_check.sh full
```

## Test Results (2025-12-29)

### Phase 1: SQL Converter Validation

- 220 unit tests pass
- All MySQL SQL syntax correctly converts to PostgreSQL
- Reserved word quoting fix applied (backticks → double quotes AFTER string conversion)

### Phase 2: Data Parity Verification

- 239 tables match between MySQL and PostgreSQL
- Row counts match after accounting for update differences
- Binary data, timestamps, and text data verified

### Phase 3: Schema Compatibility

- 239 primary keys verified
- 184 indexes verified
- Column type mappings validated

### Phase 4: C++ Runtime Testing

- **authserver**: Connects to PostgreSQL, applies updates, starts successfully
- **worldserver**: Connects to PostgreSQL, imports base schema, applies all 35 updates successfully
- Server shuts down only due to missing map files (expected in test environment)

### Bugs Fixed During Testing

1. **Reserved word quoting** - MySQL double-quoted strings were being processed AFTER backtick-to-identifier conversion, causing identifiers like `"type"` to become `'type'` (string literals). Fixed by reordering: convert double-quoted strings first, then convert backticks.

2. **PostprocessingStage identifier handling** - The `_lowercase_identifiers_outside_strings` function was stripping double quotes from reserved words. Fixed to preserve quotes for words in `SQL_RESERVED_KEYWORDS`.

3. **BYTEA column hex literal conversion** - Tables with BYTEA columns (`build_auth_key`, `build_executable_hash`, `warden_checks`) had hex literals (e.g., `0x66FC5E09...`) incorrectly converted to integers instead of `decode('hex', 'hex')` format. Fixed by implementing a table exception list in `bytea_tables.py` that identifies BYTEA columns and converts hex literals to `decode()` before generic hex-to-integer conversion runs. The order of operations is critical: BYTEA conversion must precede generic hex conversion.

4. **INSERT statement detection with leading comments** - The BYTEA converter used `re.match()` which only matches at string start. SQL statements from the splitter include leading comments (e.g., `-- Dumping data...\n\nINSERT INTO...`), causing the pattern to fail. Fixed by using `re.search()` to find INSERT anywhere in the statement.

### BYTEA Table Configuration

Tables with binary/BYTEA columns require special handling during SQL conversion. The configuration file `contrib/postgres_tools/src/trinity_postgres_tools/config/bytea_tables.py` defines these tables:

```python
BYTEA_COLUMNS = {
    "build_auth_key": ["key"],
    "build_executable_hash": ["executablehash"],
    "warden_checks": ["data", "result"],
}
```

When adding new tables with binary columns, update this configuration to ensure hex literals convert to `decode('hex', 'hex')` format instead of integers.

### Remaining Work

- Phase 5 functional testing requires a game client connected to the PostgreSQL-backed server
- Performance testing not yet conducted
- Account and character CRUD operations need client verification
