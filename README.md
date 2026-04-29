# TrinityCore

<div align="center">
  <img src="https://trinitycore.org/images/logo.png" alt="TrinityCore Logo" width="200">
  <br>
  <em>Open Source World of Warcraft Server Emulator</em>
  <br><br>

  <a href="https://trinitycore.org">Website</a> •
  <a href="https://community.trinitycore.org">Forums</a> •
  <a href="https://trinitycore.info">Wiki</a> •
  <a href="https://discord.trinitycore.org">Discord</a>
  <br><br>

  [![Build Status](https://github.com/wowemulation-dev/wooly-beast/actions/workflows/gcc-build.yml/badge.svg?branch=cata_classic&event=push)](https://github.com/wowemulation-dev/wooly-beast/actions?query=workflow%3AGCC+branch%3Acata_classic+event%3Apush)
  [![Documentation](https://img.shields.io/badge/docs-wiki-blue.svg)](https://trinitycore.info)
  [![License](https://img.shields.io/github/license/wowemulation-dev/wooly-beast.svg)](LICENSE)
</div>

---

## What is TrinityCore?

**TrinityCore** is open-source server software that lets you create your own **World of Warcraft** private server. You can play with friends, learn how MMO servers work, or contribute to game preservation.

### Supported Game Versions

- **Cataclysm Classic** - *This branch*
- **Wrath of the Lich King (3.3.5a)** - *3.3.5 branch*

---

## Why Choose TrinityCore?

- **Server Features**: Authentication, character management, and world simulation
- **Database Support**: MySQL/MariaDB and PostgreSQL database backends
- **Scripting System**: Customize quests, NPCs, and game mechanics
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **Community**: Regular updates and community support
- **Open Source**: No costs or limitations

---

## Quick Start Guide

### Step 1: What You Need

Before starting, make sure you have:

#### Required Software

- **Operating System**: Windows 10+, Ubuntu 20.04+, or macOS 10.15+
- **C++ Compiler**: C++20 compatible - GCC 11+, Clang 14+, or Visual Studio 2022+
- **CMake**: Version 3.30 or newer
- **Git**: For downloading the source code

#### Database (one of)

- **MySQL/MariaDB**: MySQL 8.0+ or MariaDB 10.6+ (enforced at startup)
- **PostgreSQL**: Version 16+ (compile with `-DWITH_POSTGRESQL=1`)

#### Additional Requirements

- **Boost Libraries**: Version 1.86 or newer
- **OpenSSL**: Version 3.0 or newer

---

### Step 2: Installation by Platform

<details>
<summary><strong>Windows Installation</strong></summary>

#### Install Prerequisites

1. **Download and install [Visual Studio 2022](https://visualstudio.microsoft.com/downloads/)**
   - Choose "Community" (free version)
   - Include "Desktop development with C++"

2. **Install MySQL**: Download from [MySQL Downloads](https://dev.mysql.com/downloads/installer/)

3. **Install Git**: Download from [git-scm.com](https://git-scm.com/downloads)

#### Build TrinityCore

1. **Clone the repository:**

   ```cmd
   git clone -b cata_classic https://github.com/wowemulation-dev/wooly-beast.git
   cd wooly-beast
   ```

2. **Create build directory:**

   ```cmd
   mkdir build
   cd build
   ```

3. **Configure the build:**

   ```cmd
   cmake ../ -DCMAKE_INSTALL_PREFIX=../install
   ```

4. **Build the project:**
   - Open `TrinityCore.sln` in Visual Studio
   - Right-click the solution and select "Build Solution"
   - Wait for compilation to complete (this may take 20-60 minutes)

</details>

<details>
<summary><strong>Linux Installation (Ubuntu/Debian)</strong></summary>

#### Install Prerequisites

```bash
# Update your system
sudo apt update && sudo apt upgrade -y

# Install build tools
sudo apt install -y git cmake make build-essential

# Install MySQL/MariaDB
sudo apt install -y libmysqlclient-dev mysql-server

# Install additional dependencies
sudo apt install -y libssl-dev libboost-all-dev
```

#### Build TrinityCore

```bash
# Clone the repository
git clone -b cata_classic https://github.com/wowemulation-dev/wooly-beast.git
cd wooly-beast

# Create and enter build directory
mkdir build && cd build

# Configure
cmake ../ -DCMAKE_INSTALL_PREFIX=../install

# Build (use all CPU cores for faster compilation)
make -j$(nproc)

# Install
make install
```

</details>

<details>
<summary><strong>macOS Installation</strong></summary>

#### Install Prerequisites

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install git cmake boost openssl mysql
```

#### Build TrinityCore

```bash
# Clone and build (same as Linux)
git clone -b cata_classic https://github.com/wowemulation-dev/wooly-beast.git
cd wooly-beast
mkdir build && cd build

# Configure and build
cmake ../ -DCMAKE_INSTALL_PREFIX=../install
make -j$(sysctl -n hw.ncpu)
make install
```

</details>

---

## Database Setup

### Create Databases

```sql
CREATE DATABASE auth;
CREATE DATABASE characters;
CREATE DATABASE world;
CREATE DATABASE hotfixes;
```

### Import Base Schemas (MySQL)

```bash
mysql -u root -p trinity_auth < sql/base/auth_database.sql
mysql -u root -p trinity_characters < sql/base/characters_database.sql
```

For the world and hotfixes databases, you need to download and import the full database releases from the TrinityCore releases page.

For PostgreSQL setup, see [PostgreSQL Test Setup](doc/PostgreSQLTestSetup.md). PostgreSQL SQL files must first be generated using the [conversion tools](contrib/postgres_tools/README.md).

### Configuration

Edit the configuration files in the `etc/` directory:

```ini
# MySQL (default)
LoginDatabaseInfo     = "127.0.0.1;3306;trinity;trinity;trinity_auth"
WorldDatabaseInfo     = "127.0.0.1;3306;trinity;trinity;trinity_world"
CharacterDatabaseInfo = "127.0.0.1;3306;trinity;trinity;trinity_characters"
HotfixDatabaseInfo    = "127.0.0.1;3306;trinity;trinity;trinity_hotfixes"

# PostgreSQL (when compiled with WITH_POSTGRESQL=1)
#LoginDatabaseInfo     = "127.0.0.1;5432;trinity;trinity;trinity_auth"
#WorldDatabaseInfo     = "127.0.0.1;5432;trinity;trinity;trinity_world"
#CharacterDatabaseInfo = "127.0.0.1;5432;trinity;trinity;trinity_characters"
#HotfixDatabaseInfo    = "127.0.0.1;5432;trinity;trinity;trinity_hotfixes"
```

---

## Build Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `SERVERS` | Build server executables | ON | `-DSERVERS=1` |
| `TOOLS` | Build extraction tools | ON | `-DTOOLS=1` |
| `SCRIPTS` | Script loading method | static | `-DSCRIPTS=dynamic` |
| `BUILD_TESTING` | Enable unit tests | OFF | `-DBUILD_TESTING=1` |
| `WITH_WARNINGS` | Enable compiler warnings | ON | `-DWITH_WARNINGS=0` |
| `WITH_COREDEBUG` | Enable core debugging | OFF | `-DWITH_COREDEBUG=1` |
| `WITH_POSTGRESQL` | Use PostgreSQL instead of MySQL | OFF | `-DWITH_POSTGRESQL=1` |

### Script Loading Options

- **`static`**: Scripts compiled into the server (faster, requires recompile for changes)
- **`dynamic`**: Scripts loaded as libraries (slower, can reload without recompiling)
- **`none`**: No scripts (minimal server for testing)

---

## Getting Help

### Documentation

- **[Installation Guide](https://trinitycore.info/en/install/requirements)** - Detailed step-by-step instructions
- **[Database Setup](https://trinitycore.info/en/home)** - Database configuration help
- **[Troubleshooting](https://trinitycore.info/en/home)** - Common problems and solutions

### Community Support

- **[Community Forums](https://community.trinitycore.org)** - Ask questions and share knowledge
- **[Discord Chat](https://discord.trinitycore.org)** - Real-time help and discussion
- **[Issue Tracker](https://github.com/wowemulation-dev/wooly-beast/issues)** - Report bugs and request features

### Getting Support Tips

1. **Search first** - Check if your question has been answered before
2. **Be specific** - Include your OS, database type, and error messages
3. **Show your work** - Share what you've tried and what did not work
4. **Be patient** - Volunteers help in their free time

---

## Contributing

TrinityCore thrives thanks to contributors like you. Here is how to get involved:

### For Beginners

- **Report bugs** you encounter
- **Improve documentation** - fix typos, add clarity
- **Test new features** and provide feedback
- **Help others** in forums and Discord

### For Developers

1. **Fork** the repository on GitHub
2. **Create a branch** for your feature: `git checkout -b feature/amazing-feature`
3. **Make your changes** following our coding standards
4. **Test thoroughly**
5. **Submit a pull request** with a clear description

#### Development Guidelines

- Follow existing code style and conventions
- Add tests for new functionality
- Update documentation for user-facing changes

---

## Frequently Asked Questions

<details>
<summary><strong>How long does compilation take?</strong></summary>

Compilation time varies by system:

- **Modern computer**: 10-20 minutes
- **Average computer**: 30-60 minutes
- **Older system**: 1-2 hours

Using `make -j$(nproc)` (Linux) or building in Release mode (Windows) will be faster.
</details>

<details>
<summary><strong>Is this legal?</strong></summary>

TrinityCore itself is legal open-source software. However:

- You need a **legal copy** of World of Warcraft to extract game data
- Running a private server may have legal implications in your jurisdiction
- This is for **educational and personal use only**
- Check your local laws before proceeding

</details>

---

## Legal Information

- **License**: TrinityCore is released under the [GNU GPL v2 License](LICENSE)
- **Purpose**: This software is for **educational purposes only**
- **Trademarks**: World of Warcraft and Warcraft are trademarks of Blizzard Entertainment, Inc.
- **Disclaimer**: Check your local laws before using this software

---

## Credits

TrinityCore is built on the work of thousands of developers over many years:

- **Original MaNGOS team** - Foundation of the codebase
- **TrinityCore developers** - Continued development and improvements
- **Community contributors** - Bug reports, testing, and code contributions

**Thanks to all our [contributors](https://github.com/TrinityCore/TrinityCore/graphs/contributors)**

---

<div align="center">
  <strong>TrinityCore: Making World of Warcraft emulation accessible to everyone</strong>
</div>
