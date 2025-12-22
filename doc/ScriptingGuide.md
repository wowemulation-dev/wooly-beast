# Scripting Guide

This guide explains how to create C++ scripts for TrinityCore.

> **Note**: For the most current information, check the
> [TrinityCore Wiki](https://trinitycore.atlassian.net/wiki/).

## Creating a Custom Script

### 1. Create the Script File

Create a new file in the `scripts/Custom/` directory:

```text
src/server/scripts/Custom/myscript.cpp
```

### 2. Copy an Example

Find an appropriate example in `scripts/Examples/` and copy its contents.
Rename the classes to match your script.

### 3. Create the AddSC Function

Each script needs a registration function:

```cpp
void AddSC_myscript()
{
    new my_creature_script();
}
```

### 4. Register the Script

In `ScriptLoader.cpp`:

1. Add the function declaration near the top:

   ```cpp
   void AddSC_myscript();
   ```

1. Call it in `AddCustomScripts()`:

   ```cpp
   AddSC_myscript();
   ```

### 5. Update CMakeLists.txt

Add your script to `scripts/CMakeLists.txt`:

```cmake
set(scripts_STAT_SRCS
    ${scripts_STAT_SRCS}
    Custom/myscript.cpp
)
```

### 6. Implement the Script

Override the virtual functions you need. See the example scripts for patterns.

### 7. Database Binding

If the script is database-bound, add the script name to the appropriate table
(e.g., `creature_template.ScriptName`).

### 8. Build and Test

Recompile the server and restart. Your script should be active.
