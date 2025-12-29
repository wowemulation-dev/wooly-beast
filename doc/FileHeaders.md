# TrinityCore File Headers Guide

> **Code Standards**: Consistent licensing headers for all TrinityCore files

---

## Purpose

This guide provides the **standard file headers** used throughout TrinityCore
to ensure:

- **Consistent licensing** across all source files
- **Legal compliance** with GPL-2.0-or-later license
- **Uniform code style**
- **Clear copyright attribution** to TrinityCore contributors

---

## Standard Headers

### C/C++ Source and Header Files

Use this header for all `.cpp`, `.c`, `.h`, and `.hpp` files:

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */
```

**Examples of files that need this header:**

- `src/server/game/Entities/Player/Player.cpp`
- `src/common/Utilities/Random.h`
- `src/server/scripts/Northrend/boss_example.cpp`

### CMake Build Files

Use this header for all CMake-related files:

```cmake
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
```

**Examples of files that need this header:**

- `CMakeLists.txt`
- `cmake/macros/FindMySQL.cmake`
- `src/server/CMakeLists.txt`

---

## When to Add Headers

### Always Add Headers To

- **New source files** you create
- **New header files** you create
- **New CMake files** you create
- **Modified files** that don't have headers yet

### File Types That Need Headers

| File Extension | Header Type | Required |
|----------------|-------------|----------|
| `.cpp`, `.cc` | C++ comment block | Yes |
| `.c` | C comment block | Yes |
| `.h`, `.hpp` | C++ comment block | Yes |
| `CMakeLists.txt` | CMake comment | Yes |
| `.cmake` | CMake comment | Yes |
| `.sql` | SQL comment | No |
| `.md` | Not needed | No |
| `.conf` | Not needed | No |

---

## Implementation Guide

### For New Files

When creating a new file, **always start with the appropriate header**:

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "YourHeader.h"

// Your code starts here...
```

### For Existing Files

When modifying files that don't have headers:

1. **Add the header** at the top of the file
1. **Leave a blank line** after the header
1. **Continue with existing includes/code**

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

// Existing includes below
#include "existing_include.h"
```

---

## Examples by File Type

### C++ Class Header Example

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#ifndef TRINITY_EXAMPLE_H
#define TRINITY_EXAMPLE_H

class ExampleClass
{
public:
    ExampleClass();
    ~ExampleClass();
};

#endif // TRINITY_EXAMPLE_H
```

### C++ Source File Example

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "ExampleClass.h"
#include "ScriptMgr.h"

ExampleClass::ExampleClass()
{
    // Implementation
}
```

### CMake File Example

```cmake
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors

CollectSourceFiles(
  ${CMAKE_CURRENT_SOURCE_DIR}
  PRIVATE_SOURCES
)
```

### Script File Example

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "ScriptMgr.h"
#include "InstanceScript.h"

class boss_example : public CreatureScript
{
public:
    boss_example() : CreatureScript("boss_example") { }

    // Script implementation...
};
```

---

## Guidelines

### Do's

- **Add headers to ALL new files**
- **Use exact formatting** shown above
- **Include headers in pull requests**
- **Check existing files** you modify
- **Use appropriate comment style** for file type

### Don'ts

- **Don't modify the header text** or formatting
- **Don't add additional copyright lines**
- **Don't use different license identifiers**
- **Don't forget headers** in new files
- **Don't add headers to non-code files** (like .md, .txt)

---

## Development Workflow

### Adding Headers to Multiple Files

For batch operations, you can use scripts:

```bash
# Find files missing headers (example)
find src/ -name "*.cpp" -exec grep -L "SPDX-License-Identifier" {} \;

# Add headers using your favorite editor
# vim, VS Code, CLion, etc. all support bulk operations
```

### IDE Integration

Most IDEs can be configured to automatically add headers:

<details>
<summary><strong>VS Code Template</strong></summary>

Create a file template in VS Code:

```json
{
    "cpp-header": {
        "prefix": "header",
        "body": [
            "/**",
            " * SPDX-License-Identifier: GPL-2.0-or-later",
            " *",
            " * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors",
            " */",
            "",
            "$0"
        ]
    }
}
```

</details>

<details>
<summary><strong>CLion Template</strong></summary>

Set up file templates in CLion:

1. File -> Settings -> Editor -> File and Code Templates
1. Add the header template for C++ files

</details>

---

## Common Issues

### Inconsistent Formatting

**Wrong**:

```cpp
/* SPDX-License-Identifier: GPL-2.0-or-later
   Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors */
```

**Correct**:

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */
```

### Missing Blank Lines

**Wrong**:

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */
#include "header.h"
```

**Correct**:

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */

#include "header.h"
```

---

## Legal Information

### Why These Headers Matter

- **Legal Protection**: Clear licensing terms for all code
- **SPDX Compliance**: Industry-standard license identification
- **GPL Compliance**: Meets GNU GPL requirements
- **International Standards**: Recognized licensing format

### License Details

- **License**: [GPL-2.0-or-later](https://spdx.org/licenses/GPL-2.0-or-later.html)
- **SPDX ID**: `GPL-2.0-or-later`
- **Copyright**: Collective copyright to TrinityCore and contributors
- **Year Range**: 2008 (project start) to current year

---

## Contributing Guidelines

### Pull Request Checklist

When submitting code:

- [ ] **All new files have headers**
- [ ] **Modified files have headers** (if they didn't before)
- [ ] **Headers use correct formatting**
- [ ] **No additional copyright lines added**
- [ ] **CMake files include CMake-style headers**

### Review Process

Maintainers will check for proper headers during code review. Missing or
incorrect headers may delay your pull request.

---

## Quick Reference

### Copy-Paste Headers

**C++ Files:**

```cpp
/**
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
 */
```

**CMake Files:**

```cmake
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Copyright 2008 - 2025, TrinityCore and the TrinityCore contributors
```
