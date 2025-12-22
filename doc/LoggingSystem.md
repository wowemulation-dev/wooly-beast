# TrinityCore Logging System Guide

> **Log4j-Style Logging**: Guide to TrinityCore's logging system

---

## Overview

TrinityCore uses a **log4j-inspired logging system** with two main components:

- **Loggers**: Categorize and filter messages by type and level
- **Appenders**: Control where messages are output (console, file, database)

This system controls what gets logged and where it goes.

---

## Loggers: What to Log

### Logger Hierarchy

Loggers follow a **hierarchical naming system** similar to Java packages:

```text
root
├── server
│   ├── server.world
│   ├── server.auth
│   └── server.database
├── entities
│   ├── entities.player
│   │   └── entities.player.character
│   ├── entities.creature
│   └── entities.gameobject
└── sql
    ├── sql.dev
    └── sql.updates
```

### Logger Inheritance

Child loggers inherit settings from their parents:

| Logger Name | Assigned Level | Inherited Level | Notes |
|-------------|---------------|----------------|-------|
| `root` | `INFO` | `INFO` | Base logger |
| `server` | None | `INFO` | Inherits from root |
| `server.world` | `DEBUG` | `DEBUG` | Overrides inheritance |

---

## Log Levels

Logging levels in order of severity:

| Level | Value | Use Case | Example |
|-------|-------|----------|---------|
| **TRACE** | 1 | Very detailed debugging | Function entry/exit |
| **DEBUG** | 2 | Development debugging | Variable values |
| **INFO** | 3 | General information | Server startup events |
| **WARN** | 4 | Warning conditions | Deprecated features |
| **ERROR** | 5 | Error conditions | Failed operations |
| **FATAL** | 6 | Critical errors | Server crash conditions |
| **DISABLED** | 0 | No logging | Turn off logger |

### Level Filtering

- A logger will only output messages **at or above** its configured level
- `TRACE < DEBUG < INFO < WARN < ERROR < FATAL`
- Example: Logger set to `INFO` will show `INFO`, `WARN`, `ERROR`, and `FATAL` messages

---

## Appenders: Where to Log

### Appender Types

| Type | ID | Description | Use Case |
|------|----|--------------|-----------|
| **Console** | 1 | Terminal/command prompt output | Development, real-time monitoring |
| **File** | 2 | Log files on disk | Production logging, debugging |
| **Database** | 3 | Database table storage | Centralized logging, analysis |

### Appender Configuration Format

```ini
Appender.Name = Type,LogLevel,Flags,Optional1,Optional2,Optional3
```

**Parameters:**

- **Type**: Appender type (1=Console, 2=File, 3=Database)
- **LogLevel**: Minimum level to log (0-6)
- **Flags**: Output formatting options (see below)
- **Optional1-3**: Type-specific parameters

---

## Formatting Flags

Flags control how log messages are formatted (combine by adding values):

| Flag | Value | Description | Example Output |
|------|-------|-------------|----------------|
| **Timestamp** | 1 | Add timestamp prefix | `2024-06-07 14:30:15 Message` |
| **Log Level** | 2 | Add level prefix | `INFO Message` |
| **Filter Type** | 4 | Add logger name | `[SERVER] Message` |
| **Date in Filename** | 8 | Timestamp in filename | `Server_2024-06-07_14-30-15.log` |
| **Backup on Overwrite** | 16 | Backup existing files | `Server.log.bak` |

**Example**: `Flags = 7` (1+2+4) = Timestamp + Level + Filter Type

---

## Configuration Examples

### Console Appender

```ini
# Basic console output
Appender.Console = 1,3,6

# Console with colors
Appender.ConsoleColor = 1,2,1,"13 11 9 5 3 1"
```

**Console Colors:**

- 0=Black, 1=Red, 2=Green, 3=Brown, 4=Blue, 5=Magenta
- 6=Cyan, 7=Grey, 8=Yellow, 9=Light Red, 10=Light Green
- 11=Light Blue, 12=Light Magenta, 13=Light Cyan, 14=White
- Format: `"fatal error warn info debug trace"`

### File Appender

```ini
# Basic file logging
Appender.Server = 2,2,7,Server.log,w

# File with timestamp in name
Appender.ServerTimed = 2,3,15,Server.log,a

# Multiple log files
Appender.Error = 2,5,3,Error.log,a
Appender.Debug = 2,2,7,Debug.log,w
```

**File Parameters:**

- **Filename**: Can use `%s` for dynamic names
- **Mode**: `w` (overwrite) or `a` (append)
- **MaxFileSize**: Optional size limit in bytes

### Database Appender

```ini
# Log to database
Appender.DB = 3,3,0
```

Creates entries in the database logs table.

---

## Logger Configuration

### Logger Format

```ini
Logger.name = LogLevel,AppenderList
```

**Parameters:**

- **LogLevel**: Minimum level for this logger (0-6)
- **AppenderList**: Space-separated list of appenders

### Logger Examples

```ini
# Root logger - catches everything
Logger.root = 3,Console Server

# Specific system loggers
Logger.server = 2,Console Debug
Logger.entities.player = 4,Console Error
Logger.sql.dev = 1,SQLDebug

# Disable specific logger
Logger.annoying.system = 0,
```

---

## Complete Configuration Examples

### Example 1: Development Setup

**Goal**: Log errors to console and file, with detailed debugging

```ini
# Appenders
Appender.Console = 1,5,6                    # Console: ERROR and above, with level/filter
Appender.Server = 2,5,7,Server.log,w       # File: ERROR and above, full formatting
Appender.Debug = 2,2,7,Debug.log,w         # File: DEBUG and above, full formatting

# Loggers
Logger.root = 5,Console Server              # Root: ERROR level, console + file
Logger.server = 2,Debug                     # Server: DEBUG level, debug file only
```

**What happens:**

- ERROR messages go to console and Server.log
- All server DEBUG+ messages go to Debug.log
- Other systems only log ERROR+ to console and Server.log

### Example 2: Production Setup

**Goal**: Minimal console output, comprehensive file logging

```ini
# Appenders
Appender.Console = 1,4,2                    # Console: WARN+, level only
Appender.Server = 2,3,15,Server.log,a      # File: INFO+, timestamp in filename
Appender.Error = 2,5,7,Error.log,a         # File: ERROR+, full formatting

# Loggers
Logger.root = 3,Console Server Error        # Root: INFO level, all appenders
```

### Example 3: Debugging Specific Systems

**Goal**: Debug guild system while ignoring other messages

```ini
# Appenders
Appender.Console = 1,1,0                    # Console: All levels, no formatting
Appender.Guild = 2,1,7,Guild.log,w         # File: TRACE+, full formatting

# Loggers
Logger.guild = 1,Console Guild              # Guild: TRACE level
Logger.entities.player = 3,Console         # Player: INFO level
# No root logger = other systems ignored
```

---

## Using Logging in Code

### C++ Logging Macros

```cpp
// Basic logging
TC_LOG_TRACE("logger.name", "Detailed trace message");
TC_LOG_DEBUG("logger.name", "Debug information");
TC_LOG_INFO("logger.name", "General information");
TC_LOG_WARN("logger.name", "Warning message");
TC_LOG_ERROR("logger.name", "Error occurred");
TC_LOG_FATAL("logger.name", "Fatal error");

// Formatted logging
TC_LOG_INFO("player", "Player %s (ID: %u) logged in", name.c_str(), id);
TC_LOG_ERROR("database", "Failed to execute query: %s", query.c_str());
```

### Common Logger Names

| Logger | Purpose | Example Usage |
|--------|---------|---------------|
| `server` | General server events | Startup, shutdown |
| `player` | Player actions | Login, logout, level up |
| `guild` | Guild system | Guild creation, member changes |
| `sql` | Database queries | Query execution, errors |
| `spells` | Spell system | Spell casting, effects |
| `combat` | Combat mechanics | Damage, healing, threat |
| `scripts` | Script execution | Script errors, debug info |

---

## Troubleshooting

### No Logs Appearing

<details>
<summary><strong>Check Configuration</strong></summary>

1. **Verify logger exists**:

   ```ini
   Logger.root = 3,Console  # Must have root logger
   ```

1. **Check log levels**:

   ```cpp
   TC_LOG_INFO("test", "Message");  // Requires logger level 3 or lower
   ```

1. **Verify appender configuration**:

   ```ini
   Appender.Console = 1,3,0  # Console appender must exist
   ```

</details>

### File Logging Not Working

<details>
<summary><strong>Common Issues</strong></summary>

- **File permissions**: Ensure server can write to log directory
- **Invalid file path**: Check file path exists and is writable
- **Disk space**: Ensure sufficient disk space for log files

```bash
# Check file permissions (Linux)
ls -la logs/
chmod 755 logs/
```

</details>

### Too Many/Few Messages

<details>
<summary><strong>Adjust Log Levels</strong></summary>

```ini
# Too many messages - increase level
Logger.root = 4,Console  # WARN and above only

# Too few messages - decrease level
Logger.root = 2,Console  # DEBUG and above

# Silence specific logger
Logger.chatty.system = 0,
```

</details>

---

## Performance Considerations

### Optimization Tips

- **Use appropriate levels**: Don't set everything to TRACE in production
- **Limit file appenders**: Multiple file appenders can impact I/O
- **Rotate large files**: Use log rotation for long-running servers
- **Database logging**: Can be slower than file logging

### Log File Management

```bash
# Log rotation (Linux)
# Add to /etc/logrotate.d/trinitycore
/path/to/trinitycore/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

---

## Quick Reference

### Default Configuration

```ini
# Minimal working configuration
Appender.Console = 1,2,0
Appender.Server = 2,2,0,Server.log,w
Logger.root = 3,Console Server
```

### Log Level Hierarchy

```text
0 = DISABLED (no logging)
1 = TRACE    (everything)
2 = DEBUG    (debug and above)
3 = INFO     (info and above)
4 = WARN     (warnings and above)
5 = ERROR    (errors and above)
6 = FATAL    (fatal errors only)
```

### Common Flag Combinations

| Flags | Description | Example Output |
|-------|-------------|----------------|
| `0` | No formatting | `Message` |
| `3` | Timestamp + Level | `2024-06-07 14:30:15 INFO Message` |
| `7` | Full formatting | `2024-06-07 14:30:15 INFO [FILTER] Message` |
| `15` | File with timestamp | Creates `Server_2024-06-07_14-30-15.log` |
