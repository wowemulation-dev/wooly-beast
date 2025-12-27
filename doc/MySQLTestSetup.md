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
podman ps | grep trinity-335-mysql
```

Expected output shows three containers:
- `trinity-335-mysql-auth` (port 33506)
- `trinity-335-mysql-characters` (port 33507)
- `trinity-335-mysql-world` (port 33508)

The script automatically creates databases and the `trinity` user.

## 2. Add Realmlist Entry

The realmlist entry must exist before starting the servers:

```bash
podman exec -it trinity-335-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "
DELETE FROM realmlist WHERE id = 1;
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 12340);
"
```

Note: This step must be done after the authserver has run at least once to create the `realmlist` table, or you can run it after step 4 when authserver creates the schema.

## 3. Configure authserver

Create the configuration file:

```bash
cp install-335-mysql/etc/authserver.conf.dist install-335-mysql/etc/authserver.conf
```

Edit `install-335-mysql/etc/authserver.conf` and set:

```ini
# Database connection (port 33506 for 3.3.5 branch)
LoginDatabaseInfo = "127.0.0.1;33506;trinity;trinity;trinity_auth"

# MySQL executable for automatic schema updates
MySQLExecutable = "/usr/bin/mysql"

# Enable automatic updates for auth database only
Updates.EnableDatabases = 1
```

## 4. Configure worldserver

Create the configuration file:

```bash
cp install-335-mysql/etc/worldserver.conf.dist install-335-mysql/etc/worldserver.conf
```

Edit `install-335-mysql/etc/worldserver.conf` and set:

```ini
# Database connections (separate containers on different ports)
LoginDatabaseInfo     = "127.0.0.1;33506;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;33508;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;33507;trinity;trinity;trinity_characters"

# Client data location (relative to install directory)
DataDir = "../build-client-data"

# MySQL executable for automatic schema updates
MySQLExecutable = "/usr/bin/mysql"

# Enable automatic updates for world and characters databases only
# (auth is handled by authserver)
Updates.EnableDatabases = 6
```

### Updates.EnableDatabases Values

The value is a bitmask:
- 1 = Auth database
- 2 = Characters database
- 4 = World database
- 7 = All databases

Recommended setup:
- authserver: `1` (auth only)
- worldserver: `6` (characters + world)

## 5. Start Servers

The servers will automatically import base schemas from `sql/base/` on first run.

**Important:** Servers must be started from inside the `install-335-mysql/` directory. The `DataDir` configuration uses relative paths (`../build-client-data`) that resolve correctly only when the working directory is the install folder.

Start authserver in one terminal:

```bash
cd install-335-mysql
./bin/authserver
```

On first run, authserver will:
1. Connect to the auth database
2. Detect empty database and import `sql/base/auth_database.sql`
3. Apply any pending updates from `sql/updates/auth/`
4. Start listening on port 3724

After authserver creates the schema, add the realmlist entry (if not done earlier):

```bash
podman exec -it trinity-335-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "
INSERT INTO realmlist (id, name, address, localAddress, localSubnetMask, port, icon, flag, timezone, allowedSecurityLevel, gamebuild)
VALUES (1, 'Trinity', '127.0.0.1', '127.0.0.1', '255.255.255.0', 8085, 0, 0, 1, 0, 12340)
ON DUPLICATE KEY UPDATE name='Trinity';
"
```

Start worldserver in another terminal:

```bash
cd install-335-mysql
./bin/worldserver
```

On first run, worldserver will:
1. Connect to all three databases
2. Import `sql/base/characters_database.sql` if characters is empty
3. Prompt to import world database (TDB dump required)
4. Apply pending updates from `sql/updates/`
5. Load DBC and vmap files
6. Start listening on port 8085

### World Database Setup

When worldserver detects an empty world database, it will prompt for the TDB dump location. You can either:

1. Let the updater prompt and provide the path interactively
2. Pre-import the TDB dump manually:

```bash
podman exec -i trinity-335-mysql-world mysql -utrinity -ptrinity trinity_world \
  < ~/Repos/github.com/wowemulation-dev/TDB/335/25101_2025_10_21/TDB_full_world_335.25101_2025_10_21.sql
```

## 6. Expected Startup Indicators

**authserver:**
- `DatabasePool 'trinity_auth' opened successfully`
- `Added realm "Trinity" at 127.0.0.1:8085`
- `Network: Started listening on 0.0.0.0:3724`

**worldserver:**
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

The 3.3.5 branch uses these ports:

| Service | Port |
|---------|------|
| MySQL (auth) | 33506 |
| MySQL (characters) | 33507 |
| MySQL (world) | 33508 |
| authserver | 3724 |
| worldserver | 8085 |

## Troubleshooting

### "Could not update the Login database"

- Verify `MySQLExecutable = "/usr/bin/mysql"` is set
- Check MySQL client is installed: `which mysql`

### Database Connection Errors

- Verify containers are running: `podman ps`
- Check ports are correct (33506/33507/33508 for 3.3.5)
- Test connection: `podman exec -it trinity-335-mysql-auth mysql -utrinity -ptrinity -e "SELECT 1"`

### Missing DBC/vmap Files

- Verify DataDir path: should be `../build-client-data` when running from install directory
- Check `build-client-data/` contains `dbc/`, `maps/`, `vmaps/`

### Realm Not Showing in Client

- Verify realmlist entry exists: `podman exec trinity-335-mysql-auth mysql -utrinity -ptrinity trinity_auth -e "SELECT * FROM realmlist"`
- Check authserver started without errors
- Verify client `realmlist.wtf` points to `127.0.0.1`

### Schema Import Fails

- Check `Updates.EnableDatabases` is set correctly
- Verify `MySQLExecutable` path is correct
- Check disk space in container volumes
