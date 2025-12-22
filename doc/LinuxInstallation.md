# Linux Installation

This guide covers installing TrinityCore on Linux systems.

> **Note**: For the most current information, see
> <https://www.trinitycore.info/>.

## Prerequisites

Install the required dependencies for your distribution. See the
[requirements documentation](https://www.trinitycore.info/display/tc/Requirements).

## Building

### 1. Create Build Directory

```bash
mkdir build
cd build
```

### 2. Configure with CMake

```bash
cmake ../ \
    -DCMAKE_INSTALL_PREFIX=/home/trinity/server \
    -DTOOLS=1 \
    -DWITH_WARNINGS=1
```

### 3. Compile

```bash
make -j$(nproc)
```

### 4. Install

```bash
make install
```

## CMake Options

| Option | Description |
|--------|-------------|
| `SERVERS` | Build worldserver and authserver |
| `SCRIPTS` | Build core with scripts included |
| `TOOLS` | Build map/mmap/vmap extraction tools |
| `USE_SCRIPTPCH` | Use precompiled headers for scripts |
| `USE_COREPCH` | Use precompiled headers for servers |
| `WITH_WARNINGS` | Show all warnings during compile |
| `WITH_COREDEBUG` | Include additional debug code |
| `CMAKE_INSTALL_PREFIX` | Installation directory |
| `NOJEM` | Disable jemalloc (advanced) |
| `CONF_DIR` | Configuration directory |
| `CMAKE_C_FLAGS` | Custom C compiler flags (advanced) |
| `CMAKE_CXX_FLAGS` | Custom C++ compiler flags (advanced) |
| `CMAKE_BUILD_TYPE` | Build type: Release, MinSizeRel, RelWithDebInfo, Debug |

## Post-Installation

1. Apply database updates as needed
1. Configure the server by editing files in the configuration directory
1. Extract game data using the tools (maps, vmaps, mmaps)
1. Start the servers

## Windows Users

For Windows installation, refer to the
[TrinityCore documentation](https://www.trinitycore.info/).
