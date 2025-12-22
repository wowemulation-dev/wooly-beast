# TrinityCore Linux Installation Guide

> **Linux/Unix Installation**: Complete guide for building TrinityCore on Linux
> systems
>
> **Documentation Notice**: For the most up-to-date installation information,
> check the [TrinityCore Wiki](https://trinitycore.info/).

---

## Overview

Installing TrinityCore on Linux requires these dependencies. This guide covers **Ubuntu/Debian**, **CentOS/RHEL**, and **Arch Linux** distributions.

---

## System Requirements

### Minimum Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **OS** | Ubuntu 20.04+ / Debian 11+ / CentOS 8+ | 64-bit required |
| **RAM** | 4 GB | 8 GB recommended for compilation |
| **Storage** | 10 GB free space | For source + build + databases |
| **CPU** | 2 cores | More cores = faster compilation |

### Required Software

- **Compiler**: GCC 8+ or Clang 7+
- **CMake**: Version 3.24 or newer
- **Database**: MySQL 5.7+ or MySQL 8.0+
- **Libraries**: Boost, OpenSSL, Zlib

---

## Step 1: Install Dependencies

### Ubuntu/Debian

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install build tools
sudo apt install -y \
    git \
    cmake \
    make \
    gcc \
    g++ \
    build-essential

# Install MySQL
sudo apt install -y \
    mysql-server \
    libmysqlclient-dev

# Install additional libraries
sudo apt install -y \
    libssl-dev \
    libboost-all-dev \
    zlib1g-dev \
    libbz2-dev
```

### CentOS/RHEL/Fedora

```bash
# Install development tools
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
    git \
    cmake \
    gcc \
    gcc-c++ \
    make

# Install MySQL
sudo dnf install -y \
    mysql-server \
    mysql-devel

# Install additional libraries
sudo dnf install -y \
    openssl-devel \
    boost-devel \
    zlib-devel \
    bzip2-devel
```

### Arch Linux

```bash
# Update system
sudo pacman -Syu

# Install build tools
sudo pacman -S \
    git \
    cmake \
    make \
    gcc \
    base-devel

# Install MySQL
sudo pacman -S \
    mysql \
    mysql-clients

# Install additional libraries
sudo pacman -S \
    openssl \
    boost \
    zlib \
    bzip2
```

---

## Step 2: Set Up Database

### MySQL Setup

```bash
# Start MySQL service
sudo systemctl start mysql
sudo systemctl enable mysql

# Secure installation (set root password)
sudo mysql_secure_installation

# Create databases
mysql -u root -p << EOF
CREATE DATABASE trinity_auth;
CREATE DATABASE trinity_characters;
CREATE DATABASE trinity_world;
CREATE DATABASE trinity_hotfixes;

CREATE USER 'trinity'@'localhost' IDENTIFIED BY 'trinity';
GRANT ALL PRIVILEGES ON trinity_auth.* TO 'trinity'@'localhost';
GRANT ALL PRIVILEGES ON trinity_characters.* TO 'trinity'@'localhost';
GRANT ALL PRIVILEGES ON trinity_world.* TO 'trinity'@'localhost';
GRANT ALL PRIVILEGES ON trinity_hotfixes.* TO 'trinity'@'localhost';
FLUSH PRIVILEGES;
EOF
```

---

## Step 3: Download Source Code

```bash
# Clone TrinityCore repository
git clone https://github.com/TrinityCore/TrinityCore.git
cd TrinityCore

# Switch to cata_classic branch
git checkout cata_classic

# Check out submodules
git submodule update --init --recursive
```

---

## Step 4: Build TrinityCore

### Create Build Directory

```bash
# Create separate build directory
mkdir build && cd build
```

### Configure Build

<details>
<summary><strong>Basic Build</strong></summary>

```bash
# Basic build
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/home/$(whoami)/server \
    -DTOOLS=1 \
    -DWITH_WARNINGS=1
```

</details>

<details>
<summary><strong>Development Build with Debugging</strong></summary>

```bash
# Development build with debugging
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/home/$(whoami)/server \
    -DCMAKE_BUILD_TYPE=Debug \
    -DTOOLS=1 \
    -DWITH_WARNINGS=1 \
    -DWITH_COREDEBUG=1
```

</details>

### Compile and Install

```bash
# Compile using all CPU cores
make -j$(nproc)

# Install to specified directory
make install

# Verify installation
ls ~/server/bin/  # Should show authserver, worldserver, etc.
```

---

## Build Configuration Options

### Common CMake Flags

| Flag | Description | Default | Example |
|------|-------------|---------|---------|
| `CMAKE_INSTALL_PREFIX` | Installation directory | `/usr/local` | `/home/user/server` |
| `CMAKE_BUILD_TYPE` | Build optimization | `Release` | `Debug`, `RelWithDebInfo` |
| `SERVERS` | Build server executables | `ON` | `OFF` (tools only) |
| `TOOLS` | Build extraction tools | `ON` | `OFF` (servers only) |
| `SCRIPTS` | Script loading method | `dynamic` | `static`, `none` |
| `WITH_WARNINGS` | Show compiler warnings | `ON` | `OFF` |
| `WITH_COREDEBUG` | Debug information | `OFF` | `ON` |
| `BUILD_TESTING` | Enable unit tests | `OFF` | `ON` |

### Example Configurations

```bash
# Minimal server-only build
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/opt/trinitycore \
    -DTOOLS=0 \
    -DSCRIPTS=static

# Development build with testing
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/home/$(whoami)/server \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_TESTING=1 \
    -DWITH_COREDEBUG=1

# Production build optimized
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/opt/trinitycore \
    -DCMAKE_BUILD_TYPE=Release \
    -DSCRIPTS=static \
    -DTOOLS=1
```

---

## Step 5: Import Database Schemas

### Download World and Hotfixes Databases

The world and hotfixes databases (TDB) must be downloaded separately from the
[TrinityCore releases](https://github.com/TrinityCore/TrinityCore/releases).

```bash
# Download the TDB files (check releases for latest version)
# Example: TDB_full_world_442.25051_2025_05_11.7z
#          TDB_full_hotfixes_442.25051_2025_05_11.7z

# Extract and copy to sql/base/
7z x TDB_full_world_442.*.7z
7z x TDB_full_hotfixes_442.*.7z
cp TDB_full_world_442.*.sql /path/to/TrinityCore/sql/base/
cp TDB_full_hotfixes_442.*.sql /path/to/TrinityCore/sql/base/
```

### Import Schemas

```bash
# Navigate to TrinityCore directory
cd /path/to/TrinityCore

# Import base schemas
mysql -u trinity -p trinity_auth < sql/base/auth_database.sql
mysql -u trinity -p trinity_characters < sql/base/characters_database.sql
mysql -u trinity -p trinity_world < sql/base/TDB_full_world_*.sql
mysql -u trinity -p trinity_hotfixes < sql/base/TDB_full_hotfixes_*.sql

# Apply any pending updates (if auto-update is disabled)
mysql -u trinity -p trinity_auth < sql/updates/auth/*.sql
mysql -u trinity -p trinity_characters < sql/updates/characters/*.sql
mysql -u trinity -p trinity_world < sql/updates/world/*.sql
mysql -u trinity -p trinity_hotfixes < sql/updates/hotfixes/*.sql
```

---

## Step 6: Configuration

### Copy Configuration Files

```bash
# Copy configuration templates
cp ~/server/etc/authserver.conf.dist ~/server/etc/authserver.conf
cp ~/server/etc/worldserver.conf.dist ~/server/etc/worldserver.conf
```

### Configure Database Connections

Edit the configuration files (`~/server/etc/authserver.conf` and `~/server/etc/worldserver.conf`):

```ini
LoginDatabaseInfo     = "127.0.0.1;3306;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;3306;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;3306;trinity;trinity;trinity_characters"
HotfixDatabaseInfo    = "127.0.0.1;3306;trinity;trinity;trinity_hotfixes"
```

---

## Step 7: Launch Servers

### Manual Startup

```bash
# Start authentication server
cd ~/server/bin
./authserver

# In another terminal, start world server
cd ~/server/bin
./worldserver
```

### Using Screen/Tmux

```bash
# Using screen
screen -S authserver ~/server/bin/authserver
screen -S worldserver ~/server/bin/worldserver

# Using tmux
tmux new-session -d -s authserver ~/server/bin/authserver
tmux new-session -d -s worldserver ~/server/bin/worldserver
```

### System Service (Optional)

<details>
<summary><strong>Create systemd services</strong></summary>

Create `/etc/systemd/system/trinitycore-auth.service`:

```ini
[Unit]
Description=TrinityCore Auth Server
After=network.target mysql.service

[Service]
Type=simple
User=trinity
WorkingDirectory=/home/trinity/server/bin
ExecStart=/home/trinity/server/bin/authserver
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/trinitycore-world.service`:

```ini
[Unit]
Description=TrinityCore World Server
After=network.target mysql.service trinitycore-auth.service

[Service]
Type=simple
User=trinity
WorkingDirectory=/home/trinity/server/bin
ExecStart=/home/trinity/server/bin/worldserver
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start services:

```bash
sudo systemctl enable trinitycore-auth trinitycore-world
sudo systemctl start trinitycore-auth trinitycore-world
```

</details>

---

## Troubleshooting

### Compilation Issues

<details>
<summary><strong>CMake configuration fails</strong></summary>

**Common causes and solutions**:

```bash
# Missing dependencies
sudo apt install libboost-all-dev libmysqlclient-dev libssl-dev

# Clear CMake cache
rm -rf CMakeCache.txt CMakeFiles/
```

</details>

<details>
<summary><strong>Out of memory during compilation</strong></summary>

```bash
# Reduce parallel jobs
make -j2  # Instead of -j$(nproc)

# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

</details>

### Database Issues

<details>
<summary><strong>Connection refused errors</strong></summary>

```bash
# Check if database is running
sudo systemctl status mysql
sudo systemctl start mysql  # Start if stopped

# Check firewall
sudo ufw allow 3306/tcp

# Test connection manually
mysql -u trinity -p -h 127.0.0.1
```

</details>

<details>
<summary><strong>Import errors</strong></summary>

```bash
# Check file permissions
chmod +r sql/base/*.sql

# Check database exists
mysql -u trinity -p -e "SHOW DATABASES;"

# Import with verbose output
mysql -u trinity -p trinity_auth -v < sql/base/auth_database.sql
```

</details>

### Runtime Issues

<details>
<summary><strong>Servers won't start</strong></summary>

```bash
# Check configuration
~/server/bin/authserver --help
~/server/bin/worldserver --help

# Check logs
tail -f ~/server/logs/*.log

# Test configuration
~/server/bin/authserver --dry-run
```

</details>

---

## Performance Tuning

### Database Optimization

**MySQL** (`/etc/mysql/mysql.conf.d/mysqld.cnf`):

```ini
[mysqld]
innodb_buffer_pool_size = 1G
max_connections = 200
query_cache_size = 64M
query_cache_type = 1
```

### Server Configuration

Common performance settings:

```ini
# worldserver.conf
MapUpdateInterval = 100
InstanceUpdateTimeLimit = 5000
PlayerLimit = 100
```

---

## Post-Installation

### Verification Checklist

- [ ] Servers start without errors
- [ ] Database connections work
- [ ] Game client can connect to server
- [ ] Character creation works
- [ ] Basic gameplay functions (movement, chat, etc.)

### Security Considerations

```bash
# Firewall rules
sudo ufw enable
sudo ufw allow 8085/tcp   # AuthServer
sudo ufw allow 8086/tcp   # WorldServer (if external access needed)

# Database security
# - Use strong passwords
# - Limit database user permissions
# - Consider SSL connections for remote databases
```

### Monitoring

```bash
# Monitor server processes
htop
ps aux | grep -E "(auth|world)server"

# Monitor database
mysql -u trinity -p -e "SHOW PROCESSLIST;"

# Check logs
tail -f ~/server/logs/*.log
```

---

## Additional Resources

### Official Documentation

- **[TrinityCore Wiki](https://trinitycore.info/)** - Comprehensive documentation
- **[Installation Requirements](https://trinitycore.info/en/install/requirements)** - Detailed requirements
- **[Server Setup Guide](https://trinitycore.atlassian.net/wiki/spaces/tc/pages/10977409/Server+Setup)** - Post-installation configuration

### Community Support

- **[Forums](https://community.trinitycore.org)** - Community support
- **[Discord](https://discord.gg/TrinityCore)** - Real-time help
- **[GitHub Issues](https://github.com/TrinityCore/TrinityCore/issues)** - Bug reports

---

## Quick Command Reference

```bash
# Build commands
mkdir build && cd build
cmake ../ -DCMAKE_INSTALL_PREFIX=/home/$(whoami)/server -DTOOLS=1
make -j$(nproc)
make install

# Database setup (download TDB from GitHub releases first)
mysql -u trinity -p trinity_auth < sql/base/auth_database.sql
mysql -u trinity -p trinity_characters < sql/base/characters_database.sql
mysql -u trinity -p trinity_world < sql/base/TDB_full_world_*.sql
mysql -u trinity -p trinity_hotfixes < sql/base/TDB_full_hotfixes_*.sql

# Start servers
~/server/bin/authserver &
~/server/bin/worldserver &
```
