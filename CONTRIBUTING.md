# TrinityCore Contributor Guidelines

Welcome to the TrinityCore community! This document guides you through our
contribution process.

## Our Philosophy

TrinityCore is built by the community, for the community. We believe in:

- **Collaboration**: Working together makes the project stronger
- **Respect**: Treating each other with kindness and consideration
- **Quality**: Writing maintainable code
- **Learning**: Helping each other grow as developers

## Before You Start

1. **Get Familiar**: Take some time to understand the project's architecture
   and coding patterns
1. **Check Issues**: Look at our
   [issue tracker](https://github.com/TrinityCore/TrinityCore/issues) for
   tasks labeled "good first issue"
1. **Join the Community**: Join our [Discord server](#communication-channels)
   to ask questions

## Communication Channels

- **[Discord Server](https://discord.trinitycore.org/)**: Real-time discussions
- **[Forums](https://community.trinitycore.org/)**: In-depth discussions
- **[Issue Tracker](https://github.com/TrinityCore/TrinityCore/issues)**: For
  bug reports and feature requests
- **[Wiki](https://trinitycore.atlassian.net/wiki/)**: For documentation and guides

## Development Environment Setup

### Required Tools

- **Git**: For version control
- **CMake**: 3.24 or newer
- **C++ Compiler**: C++20 compatible
  - GCC 11.1.0+
  - Clang 11.0.0+ (AppleClang 12.0.5+)
  - Visual Studio 2022 17.2+
- **Database**: MySQL 5.7+ or MySQL 8.0+

### Recommended IDE Extensions

- **C/C++ Extensions**: For syntax highlighting and IntelliSense
- **CMake Tools**: For CMake integration
- **EditorConfig**: To automatically apply our code style
- **Clang-Format**: For automatic code formatting
- **CMake Format**: For consistent CMake files

### Setting Up Your Environment

```bash
# Clone the repository
git clone https://github.com/TrinityCore/TrinityCore.git
cd TrinityCore

# Switch to cata_classic branch
git checkout cata_classic

# Create a build directory
mkdir build && cd build

# Configure the project (adjust paths as needed)
cmake ../ -DCMAKE_INSTALL_PREFIX=../install -DTOOLS=1

# Build the project
cmake --build . --config Release
```

### Using Code Formatting Tools

We provide configuration files for clang-format and cmake-format for consistent
code style:

```bash
# Format C++ files using clang-format
clang-format -i path/to/your/file.cpp

# Format CMake files using cmake-format
cmake-format -i path/to/your/CMakeLists.txt
```

Many IDEs and editors support using these configurations automatically.

## Code Style Guidelines

We follow a consistent code style to maintain readability. The project provides
configuration files for automated formatting tools to make this easier:

- **`.clang-format`**: Configuration for automatically formatting C++ code
- **`.cmake-format`**: Configuration for consistently formatting CMake files

These tools ensure your contributions match our style. Key style points:

### General Formatting

- Use **4 spaces** for indentation (not tabs)
- Line length should not exceed **120 characters**
- Use **Unix-style line endings** (LF, not CRLF)
- Add a newline at the end of each file

### Naming Conventions

- **Classes and Structs**: `PascalCase`
- **Functions and Methods**: `camelCase`
- **Variables**: `camelCase`
- **Constants and Enums**: `ALL_CAPS_WITH_UNDERSCORES`
- **Member Variables**: `camelCase` with no prefix

### C++ Specific

- Use C++20 features when appropriate
- Prefer `nullptr` over `NULL` or `0`
- Use `enum class` instead of plain `enum`
- Use braces for all control structures, even single-line statements

```cpp
// Use this
if (condition) {
    doSomething();
}

// Not this
if (condition)
    doSomething();
```

### SQL Style

- Keywords in **UPPERCASE**
- Table and column names in `snake_case`
- Each field on a new line for complex queries
- Include comments explaining the purpose of complex queries

```sql
-- Example of a well-formatted query
SELECT
    c.name,
    c.level
FROM
    characters c
WHERE
    c.account = 1
    AND c.level > 10
ORDER BY
    c.level DESC;
```

## Git Workflow

### Branches

- **cata_classic**: Stable development branch for Cataclysm Classic
- **[YOUR_USERNAME]/[FEATURE_NAME]**: Your feature/bugfix branch

### Commit Messages

We follow a structured commit message format:

```text
[Type]: Short summary (max 50 chars)

Detailed explanation of what this commit does.
Include the motivation for the change and how it differs
from previous behavior. (wrap at 72 characters)

Fixes #123
```

Where `[Type]` is one of:

- **Core**: For core server code changes
- **DB**: For database changes
- **Scripts**: For script changes
- **Build**: For build system changes
- **Docs**: For documentation changes
- **Tools**: For development tool changes

Examples:

```text
Core: Fix warrior rage generation calculation

Corrects an issue where warriors would generate excessive rage
when taking damage above a certain threshold.

Fixes #4321
```

```text
DB: Update creature_template for Northrend rares

Updates stats and loot tables for rare spawns in Northrend zones.
Creatures now have appropriate level and item level drops.

Fixes #5432
```

### Pull Request Process

1. **Create a branch** from `cata_classic` for your changes
1. **Make your changes**, following our code style
1. **Test thoroughly** to ensure your changes work as expected
1. **Create a pull request** with a clear description of your changes
1. **Address feedback** from reviewers
1. Once approved, your changes will be merged

### Useful Resources

When creating patches, read:

- [C++ Development Standards](https://trinitycore.atlassian.net/wiki/spaces/tc/pages/2130103/C+Development+Standards)
- [WDB Fields](https://community.trinitycore.org/topic/58-wdb-fields/)
- [Git Squash](https://ariejan.net/2011/07/05/git-squash-your-latests-commits-into-one/)

We suggest creating one branch for each C++ fix. This allows you to work on
multiple fixes without waiting for your pull request to be merged.

## Testing Guidelines

Testing is essential to maintain the quality of TrinityCore:

### Unit Tests

- Add unit tests for new functionality
- Ensure existing tests pass with your changes

### Manual Testing

- Test your changes in-game when applicable
- Verify changes work on both Windows and Linux platforms

### Performance Considerations

- Be mindful of performance, especially for frequently executed code
- Use benchmarks to measure performance impact of significant changes

## Database Contributions

When making database changes:

1. Create SQL update files in the appropriate directory
1. Follow the naming convention: `YYYY_MM_DD_NN_database.sql`
1. Include comments explaining the purpose of changes
1. Test changes with MySQL before submitting

Since it is unlikely that your Pull Request will be merged on the day you open
it, use a future date to avoid merge conflicts (e.g., `2099_01_01_00_world.sql`).

When doing changes to `auth` or `characters` database, remember to update the
base files in `/sql/base/`.

For SQL-only fixes, please [create a ticket](https://github.com/TrinityCore/TrinityCore/issues/new/choose).

## Reporting Issues

Before reporting a bug, make sure you are using the latest core and database
revision. Read
[The TrinityCore Issuetracker and You](https://community.trinitycore.org/topic/37-the-trinitycore-issuetracker-and-you/)
before creating a ticket.

If you have problems with TrinityCore installation, read
[Trouble with your Trinity install](https://community.trinitycore.org/topic/13962-trouble-with-your-trinity-install-starting-login-readme-1st-faqs/).

### Mandatory Information

When creating a ticket, include:

- **Branch**: `cata_classic`
- **Commit hash**: The full commit hash (not "unknown" or "archived"). If you
  see "TrinityCore rev. unknown 1970-01-01", read
  [this fix](https://community.trinitycore.org/topic/345-howto-properly-install-git-on-windows-fix-trinitycore-rev-1970-01-01-000000-0000/).
- **Affected entries**: Creature/item/quest IDs with links to wowhead
- **Clear description**: Title and description of the bug

When reporting a crash, you **must** compile in debug mode. Release dumps do
not contain enough information for debugging.

Example issue format:

```text
Title: DB/Quest: The Collapse

Branch: cata_classic
Commit: 63f96a282307

The quest "The Collapse" (https://www.wowhead.com/cata/quest=11706)
lacks the final event.
```

## First-Time Contributor Tips

New to TrinityCore? Here are some tips:

1. **Start small**: Fix a minor bug or improve documentation
1. **Ask questions**: Don't hesitate to seek help in our Discord
1. **Be patient**: Review may take time, especially for larger changes
1. **Stay engaged**: Respond promptly to feedback on your contributions
1. **Use the formatting tools**: Use clang-format and cmake-format
   configurations to ensure your code meets our style guidelines

## Code of Conduct

We expect all contributors to:

- Be respectful and inclusive in all interactions
- Provide constructive feedback
- Accept criticism gracefully
- Focus on what's best for the community
- Show empathy towards other community members

## Recognition

Your work will be:

- Acknowledged in the project's contributor list
- Recognized in release notes for significant contributions
- Appreciated by the whole community

## License Information

By contributing to TrinityCore, you agree that your contributions will be
licensed under the project's [GNU GPL v2](LICENSE.md).

---

Thank you for contributing to TrinityCore. If you have questions or need help,
reach out to the community.
