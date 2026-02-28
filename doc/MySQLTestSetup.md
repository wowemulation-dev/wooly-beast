# MySQL Build Test Setup

This document describes the steps to verify the MySQL build works correctly.

## Prerequisites

- MySQL build completed: `./build-dev.sh --mysql -j all`
- Client data extracted to `build-client-data/` (maps, vmaps, dbc files)
- Podman installed for database containers
- MySQL client installed: `/usr/bin/mysql`

## 1. Database Setup

Start the MySQL containers:

```bash
./test-dev-environment.sh setup-mysql
```

Verify the containers are running:

```bash
podman ps | grep trinity-cata-mysql
```

Expected output shows four containers:
- `trinity-cata-mysql-auth` (port 33606)
- `trinity-cata-mysql-characters` (port 33607)
- `trinity-cata-mysql-world` (port 33608)
- `trinity-cata-mysql-hotfixes` (port 33609)

The script automatically creates databases and the `trinity` user.

## 2. Add Realmlist Entry

The realmlist entry must exist before starting the servers:

```bash
podman exec -it trinity-cata-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "
DELETE FROM realmlist WHERE id = 1;
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 15595);
"
```

Note: This step must be done after the authserver has run at least once to create the `realmlist` table, or you can run it after step 4 when authserver creates the schema.

## 3. Configure authserver

Create the configuration file:

```bash
cp install-cata/etc/authserver.conf.dist install-cata/etc/authserver.conf
```

Edit `install-cata/etc/authserver.conf` and set:

```ini
# Database connection (port 33606 for cata_classic branch)
LoginDatabaseInfo = "127.0.0.1;33606;trinity;trinity;trinity_auth"

# MySQL executable for automatic schema updates
MySQLExecutable = "/usr/bin/mysql"

# Enable automatic updates for auth database only
Updates.EnableDatabases = 1
```

## 4. Configure worldserver

Create the configuration file:

```bash
cp install-cata/etc/worldserver.conf.dist install-cata/etc/worldserver.conf
```

Edit `install-cata/etc/worldserver.conf` and set:

```ini
# Database connections (separate containers on different ports)
LoginDatabaseInfo     = "127.0.0.1;33606;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;33608;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;33607;trinity;trinity;trinity_characters"
HotfixDatabaseInfo    = "127.0.0.1;33609;trinity;trinity;trinity_hotfixes"

# Client data location (relative to install directory)
DataDir = "../build-client-data"

# MySQL executable for automatic schema updates
MySQLExecutable = "/usr/bin/mysql"

# Enable automatic updates for world, characters, and hotfix databases
# (auth is handled by authserver)
Updates.EnableDatabases = 14
```

### Updates.EnableDatabases Values

The value is a bitmask:
- 1 = Auth database
- 2 = Characters database
- 4 = World database
- 8 = Hotfix database
- 15 = All databases

Recommended setup:
- authserver: `1` (auth only)
- worldserver: `14` (characters + world + hotfix)

## 5. Start Servers

The servers will automatically import base schemas from `sql/base/` on first run.

**Important:** Servers must be started from inside the `install-cata/` directory. The `DataDir` configuration uses relative paths (`../build-client-data`) that resolve correctly only when the working directory is the install folder.

Start authserver in one terminal:

```bash
cd install-cata
./bin/authserver
```

On first run, authserver will:
1. Connect to the auth database
2. Detect empty database and import `sql/base/auth_database.sql`
3. Apply any pending updates from `sql/updates/auth/`
4. Start listening on port 3724

After authserver creates the schema, add the realmlist entry (if not done earlier):

```bash
podman exec -it trinity-cata-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 15595)
ON DUPLICATE KEY UPDATE name='Trinity';
"
```

Start worldserver in another terminal:

```bash
cd install-cata
./bin/worldserver
```

On first run, worldserver will:
1. Connect to all four databases
2. Import `sql/base/characters_database.sql` if characters is empty
3. Prompt to import world database (TDB dump required)
4. Import hotfix database if empty
5. Apply pending updates from `sql/updates/`
6. Load DBC and vmap files
7. Start listening on port 8085

### World Database Setup

When worldserver detects an empty world database, it will prompt for the TDB dump location. You can either:

1. Let the updater prompt and provide the path interactively
2. Pre-import the TDB dump manually:

```bash
podman exec -i trinity-cata-mysql-world mysql -utrinity -ptrinity trinity_world \
  < ~/Repos/github.com/TrinityCore/TDB/cata_classic/25051_2025_05_18/TDB_full_world_442.25051_2025_05_18.sql
```

## 6. Expected Startup Indicators

**authserver:**
- `DatabasePool 'trinity_auth' opened successfully`
- `Added realm "Trinity" at 127.0.0.1:8085`
- `Network: Started listening on 0.0.0.0:3724`

**worldserver:**
- `DatabasePool 'trinity_world' opened successfully`
- `DatabasePool 'trinity_characters' opened successfully`
- `DatabasePool 'trinity_hotfixes' opened successfully`
- `Loading DBC files...` (verifies DataDir)
- `Loading vmaps...` (verifies vmap extraction)
- `World initialized`

## 7. Create Test Account

In the worldserver console:

```
account create testuser testpass
account set gmlevel testuser 3 -1
```

## Port Reference

The cata_classic branch uses these ports:

| Service | Port |
|---------|------|
| MySQL (auth) | 33606 |
| MySQL (characters) | 33607 |
| MySQL (world) | 33608 |
| MySQL (hotfixes) | 33609 |
| authserver | 3724 |
| worldserver | 8085 |

## Troubleshooting

### "Could not update the Login database"

- Verify `MySQLExecutable = "/usr/bin/mysql"` is set
- Check MySQL client is installed: `which mysql`

### Database Connection Errors

- Verify containers are running: `podman ps`
- Check ports are correct (33606/33607/33608/33609 for cata_classic)
- Test connection: `podman exec -it trinity-cata-mysql-auth mysql -utrinity -ptrinity -e "SELECT 1"`

### Missing DBC/vmap Files

- Verify DataDir path: should be `../build-client-data` when running from install directory
- Check `build-client-data/` contains `dbc/`, `maps/`, `vmaps/`

### Realm Not Showing in Client

- Verify realmlist entry exists: `podman exec trinity-cata-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "SELECT * FROM realmlist"`
- Check authserver started without errors
- Verify client `realmlist.wtf` points to `127.0.0.1`

### Schema Import Fails

- Check `Updates.EnableDatabases` is set correctly
- Verify `MySQLExecutable` path is correct
- Check disk space in container volumes
