# Compilation Help and Troubleshooting

> **Quick Help**: Common solutions for compilation issues with TrinityCore

---

## Before Reporting Compilation Issues

Before reporting compilation problems on our issue tracker, try these troubleshooting steps:

### Step 1: Clean Your Build Environment

<details>
<summary><strong>Clear CMake Cache</strong></summary>

CMake sometimes holds onto old configuration data. Clear it:

```bash
# Remove CMake cache files
rm -f CMakeCache.txt
rm -rf CMakeFiles/

# Or delete entire build directory (recommended)
rm -rf build/
mkdir build && cd build
```

**Why this helps**: Build system updates can cause conflicts with old cache files.

</details>

<details>
<summary><strong>Recreate Build Directory</strong></summary>

Start with a fresh build directory:

```bash
# Remove and recreate build directory
cd TrinityCore
rm -rf build/
mkdir build && cd build

# Reconfigure from scratch
cmake ../ -DCMAKE_INSTALL_PREFIX=../install
```

**Why this helps**: Linking errors are caused by stale object files or configuration.

</details>

### Step 2: Use a Clean Source Tree

**Important**: We cannot support modified cores.

```bash
# Check for modifications
git status

# Reset to clean state if needed
git checkout .
git clean -fd

# Update to latest version
git pull origin cata_classic
```

**Why this helps**: Custom modifications can introduce incompatibilities.

### Step 3: Provide Complete Error Logs

When reporting issues, include:

- **Full compilation command** that failed
- **Complete error message** (not just the last line)
- **20 lines before and after** the error
- **Your system information** (OS, compiler version, etc.)

---

## Common Compilation Issues

### CMake Configuration Errors

<details>
<summary><strong>"CMake Error: Could not find a package configuration file"</strong></summary>

**Problem**: Missing dependencies or incorrect paths

**Solutions**:

```bash
# Install missing dependencies (Ubuntu/Debian)
sudo apt install libboost-all-dev libmysqlclient-dev libssl-dev

# macOS with Homebrew
brew install boost mysql openssl

# Clear cache and reconfigure
rm CMakeCache.txt
cmake ../ -DCMAKE_INSTALL_PREFIX=../install
```

</details>

<details>
<summary><strong>"No CMAKE_CXX_COMPILER could be found"</strong></summary>

**Problem**: Missing or incompatible compiler

**Solutions**:

```bash
# Ubuntu/Debian: Install GCC
sudo apt install build-essential gcc g++

# macOS: Install Xcode command line tools
xcode-select --install

# Windows: Install Visual Studio with C++ workload
```

</details>

### Compilation Errors

<details>
<summary><strong>Out of Memory Errors</strong></summary>

**Problem**: System runs out of memory during compilation

**Solutions**:

```bash
# Reduce parallel jobs
make -j2  # Instead of -j$(nproc)

# Add swap space (Linux)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Use Release build (uses less memory)
cmake ../ -DCMAKE_BUILD_TYPE=Release
```

</details>

### Linking Errors

<details>
<summary><strong>"undefined reference" or "unresolved external symbol"</strong></summary>

**Problem**: Missing libraries or object files

**Solutions**:

```bash
# Clean rebuild (common fix)
rm -rf build/
mkdir build && cd build
cmake ../ -DCMAKE_INSTALL_PREFIX=../install
make -j$(nproc)

# Check library installation
ldconfig -p | grep mysql    # Linux: Check MySQL libs
ldconfig -p | grep boost    # Linux: Check Boost libs
```

</details>

---

## Advanced Troubleshooting

### Debug Build Information

```bash
# Enable verbose output
cmake ../ -DCMAKE_VERBOSE_MAKEFILE=ON

# Build with verbose output
make VERBOSE=1

# Or with CMake
cmake --build . --verbose
```

### Check System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CMake** | 3.28 | Latest |
| **GCC** | 11 | 13+ |
| **Clang** | 14 | 18+ |
| **Visual Studio** | 2022 | 2022 |
| **RAM** | 4 GB | 8+ GB |
| **Storage** | 5 GB | 10+ GB |

### Environment Variables

```bash
# Set compiler explicitly
export CC=gcc
export CXX=g++

# Set library paths (if needed)
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig
```

---

## Getting Help

### Before Asking for Help

1. **Tried all steps above**
1. **Using clean, unmodified source code**
1. **Have complete error logs ready**
1. **Checked system requirements**

### Where to Get Help

- **[Community Forums](https://community.trinitycore.org)** - Post detailed compilation issues
- **[Discord #development](https://discord.trinitycore.org/)** - Real-time help
- **[GitHub Issues](https://github.com/TrinityCore/TrinityCore/issues)** - Report bugs with full logs

### Creating a Good Issue Report

Include this information:

```markdown
**Operating System**: Ubuntu 22.04 / Windows 11 / macOS 13
**Compiler**: GCC 10.0 / Clang 12 / MSVC 2022
**CMake Version**: 3.24.1
**Database**: MySQL 8.0+ / PostgreSQL 16+

**Error Message**:
[Paste complete error here with 20 lines of context]

**Build Command**:
cmake ../ -DCMAKE_INSTALL_PREFIX=../install
make -j4

**What I tried**:
- Cleared CMake cache
- Recreated build directory
- Used clean source tree
```

---

## Summary

**Compilation issues are solved by**:

1. **Cleaning your build environment** (remove build directory)
1. **Using clean, unmodified source code**
1. **Installing all required dependencies**
1. **Using supported compilers and versions**
