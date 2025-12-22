# Logging System

TrinityCore uses a log4j-style logging system with loggers and appenders.

## Overview

The logging system has two components:

- **Loggers**: Named entities that categorize log messages
- **Appenders**: Output destinations (console, file, database)

## Loggers

Loggers follow a hierarchical naming scheme. A logger is an ancestor of
another if its name followed by a dot is a prefix of the descendant name.

Example hierarchy:

- `entities` (parent of `entities.player`)
- `entities.player` (parent of `entities.player.character`)
- `entities.player.character`

### Log Levels

| Level | Value | Description |
|-------|-------|-------------|
| DISABLED | 0 | Logging disabled |
| TRACE | 1 | Finest detail |
| DEBUG | 2 | Debug information |
| INFO | 3 | Informational |
| WARN | 4 | Warnings |
| ERROR | 5 | Errors |
| FATAL | 6 | Fatal errors |

A log request is enabled if its level is greater than or equal to the
logger's level. Loggers without an assigned level inherit from their parent.

## Appenders

Appenders define where log messages are written.

### Appender Configuration

Format: `Type,LogLevel,Flags,optional1,optional2`

**Type:**

- `1` - Console
- `2` - File
- `3` - Database

**Flags (bitmask):**

| Flag | Value | Description |
|------|-------|-------------|
| Timestamp | 1 | Prefix timestamp |
| Log Level | 2 | Prefix log level |
| Filter Type | 4 | Prefix filter type |
| File Timestamp | 8 | Append timestamp to filename (File only) |
| Backup | 16 | Backup existing file (File with mode=w only) |

**Console Colors** (optional1 for Type=1):

Format: `"fatal error warn info debug trace"`

| Value | Color |
|-------|-------|
| 0 | Black |
| 1 | Red |
| 2 | Green |
| 3 | Brown |
| 4 | Blue |
| 5 | Magenta |
| 6 | Cyan |
| 7 | Grey |
| 8 | Yellow |
| 9 | Light Red |
| 10 | Light Green |
| 11 | Light Blue |
| 12 | Light Magenta |
| 13 | Light Cyan |
| 14 | White |

**File options:**

- `optional1`: Filename (supports `%u` for dynamic names)
- `optional2`: Mode (`a` = append, `w` = overwrite)

### Logger Configuration

Format: `LogLevel,AppenderList`

The appender list uses spaces as separators.

## Examples

### Example 1: Basic Error Logging

Log errors to console and file:

```text
Appender.Console=1,5,6
Appender.Server=2,5,7,Server.log,w
Logger.root=5,Console Server
```

### Example 2: Info Level with Timestamps

```text
Appender.Console=1,5,6
Appender.Server=2,4,15,Server.log
Logger.root=4,Console Server
```

### Example 3: Debug Specific Systems

Debug guilds and character events:

```text
Appender.Console=1,1
Appender.SQLDev=2,2,0,SQLDev.log
Logger.guild=1,Console
Logger.entities.player.character=3,Console
Logger.sql.dev=3,SQLDev
```

## Default Configuration

If the root logger cannot be configured, the system creates defaults:

- Logger `root` with level ERROR
- Logger `server` with level INFO
- Appender `Console` for console output
