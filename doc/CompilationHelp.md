# Compilation Help

Before reporting compile errors on the issue tracker, follow these steps:

## Troubleshooting Steps

### 1. Clear the CMake Cache

The build system may have been modified with added or removed functionality.
Delete `CMakeCache.txt` and the `CMakeFiles` directory, then reconfigure.

### 2. Recreate Build Directory

Linking errors are often caused by stale build artifacts. Delete the entire
build directory, recreate it, and rebuild from scratch:

```bash
rm -rf build
mkdir build
cd build
cmake ..
make -j$(nproc)
```

### 3. Use a Clean Source Tree

We cannot support modified cores. If you have made changes to the source,
test with unmodified code first to rule out issues from your modifications.

### 4. Provide Proper Logs

When reporting compile errors, include:

- Full compile output (at least 20 lines before and after the error)
- Operating system and version
- Compiler and version
- CMake version
- Build configuration options

## Getting Help

- Check the [TrinityCore Wiki](https://trinitycore.atlassian.net/wiki/)
- Ask on [Discord](https://discord.trinitycore.org/)
