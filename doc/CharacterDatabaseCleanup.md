# Character Database Cleanup Guide

> **Database Maintenance**: Remove outdated and invalid character data

---

## What is Character Database Cleanup?

The Character Database Cleanup system removes **obsolete data** from player characters, including:

- **Achievements** that no longer exist
- **Skills** that have been removed or changed
- **Spells** that are no longer valid
- **Talents** from old talent trees
- **Quest status** for removed quests

This helps maintain database integrity and prevents issues with invalid data.

---

## How It Works

Cleanup is controlled by setting a **bitmask value** in the `worldstates` table. The server checks this setting on startup and performs the requested cleanup operations.

### Cleanup Flags

| Flag Name | Value | Description |
|-----------|-------|-------------|
| `CLEANING_FLAG_ACHIEVEMENT_PROGRESS` | `0x1` (1) | Remove invalid achievement progress |
| `CLEANING_FLAG_SKILLS` | `0x2` (2) | Remove obsolete skills |
| `CLEANING_FLAG_SPELLS` | `0x4` (4) | Remove invalid spells |
| `CLEANING_FLAG_TALENTS` | `0x8` (8) | Remove old talent data |
| `CLEANING_FLAG_QUESTSTATUS` | `0x10` (16) | Remove invalid quest status |

---

## Setting Up Cleanup

### Step 1: Choose What to Clean

Decide which types of data you want to clean up. You can combine multiple flags using addition.

### Step 2: Calculate the Bitmask

Add the values of the flags you want to enable.

**Example Calculations:**

```text
Clean skills + spells + talents (but keep achievements):
CLEANING_FLAG_SKILLS + CLEANING_FLAG_SPELLS + CLEANING_FLAG_TALENTS
= 2 + 4 + 8 = 14

Clean everything:
1 + 2 + 4 + 8 + 16 = 31

Clean only invalid spells:
4
```

### Step 3: Update the Database

Connect to your **characters database** and update the worldstates table:

```sql
-- Example: Clean skills, spells, and talents (value = 14)
UPDATE worldstates SET value = 14 WHERE entry = 20004;

-- Check current setting
SELECT * FROM worldstates WHERE entry = 20004;
```

### Step 4: Restart the Server

The cleanup runs automatically when the worldserver starts. Monitor the server logs for cleanup progress.

---

## Common Cleanup Scenarios

<details>
<summary><strong>After Major Game Updates</strong></summary>

When TrinityCore updates remove or change game content:

```sql
-- Clean everything after major content changes
UPDATE worldstates SET value = 31 WHERE entry = 20004;
```

**For**: Major version updates, talent system changes, spell reworks.

</details>

<details>
<summary><strong>Achievement System Issues</strong></summary>

If players have invalid achievement progress:

```sql
-- Clean only achievement data
UPDATE worldstates SET value = 1 WHERE entry = 20004;
```

**For**: After achievement system updates or database imports.

</details>

<details>
<summary><strong>Selective Cleanup</strong></summary>

For specific issues while preserving other data:

```sql
-- Clean spells and talents, keep achievements and skills
-- SPELLS (4) + TALENTS (8) = 12
UPDATE worldstates SET value = 12 WHERE entry = 20004;
```

**For**: Targeted fixes for specific systems.

</details>

<details>
<summary><strong>Disable Cleanup</strong></summary>

To turn off automatic cleanup:

```sql
-- Disable all cleanup
UPDATE worldstates SET value = 0 WHERE entry = 20004;
```

**For**: After cleanup is complete or for production servers.

</details>

---

## Important Safety Information

### Before Running Cleanup

1. **Backup Your Database**

   ```bash
   # Create backup before cleanup
   mysqldump -u root -p trinity_characters > characters_backup.sql
   ```

1. **Test on Development Server**
   - Run cleanup on a copy of your database first
   - Verify the results are what you expected
   - Check for any unexpected data loss

1. **Notify Players**
   - Inform players about potential character changes
   - Schedule cleanup during low-activity periods
   - Explain what data will be affected

### During Cleanup

- **Server Performance**: Cleanup can be CPU and I/O intensive
- **Startup Time**: Server startup may take longer than usual
- **Database Locking**: Some tables may be locked during cleanup

### After Cleanup

```sql
-- Verify cleanup completed
SELECT * FROM worldstates WHERE entry = 20004;

-- Disable cleanup to prevent re-running
UPDATE worldstates SET value = 0 WHERE entry = 20004;
```

---

## Monitoring Cleanup Progress

### Server Logs

Watch server logs for cleanup messages:

```bash
# Monitor worldserver logs
tail -f logs/worldserver.log | grep -i cleanup

# Look for completion messages
grep "Character database cleanup completed" logs/worldserver.log
```

### Database Verification

Check if specific data was cleaned:

```sql
-- Check for orphaned achievements
SELECT COUNT(*) FROM character_achievement ca
LEFT JOIN achievement_reward ar ON ca.achievement = ar.entry
WHERE ar.entry IS NULL;

-- Check for invalid spells
SELECT COUNT(*) FROM character_spell cs
LEFT JOIN spell_template st ON cs.spell = st.entry
WHERE st.entry IS NULL;
```

---

## Troubleshooting

<details>
<summary><strong>Cleanup Doesn't Run</strong></summary>

**Possible causes**:

- WorldState entry doesn't exist
- Value is set to 0 (disabled)
- Database connection issues

**Solutions**:

```sql
-- Ensure the worldstate entry exists
INSERT INTO worldstates (entry, value, comment)
VALUES (20004, 14, 'Character cleanup flags')
ON DUPLICATE KEY UPDATE value = 14;
```

</details>

<details>
<summary><strong>Server Startup Hangs</strong></summary>

**Possible causes**:

- Large database requiring extensive cleanup
- Insufficient system resources

**Solutions**:

- Increase server timeout settings
- Run cleanup during off-peak hours
- Clean smaller datasets incrementally

</details>

<details>
<summary><strong>Data Loss Concerns</strong></summary>

**If you notice unexpected data loss**:

1. Stop the server immediately
1. Restore from backup
1. Review your cleanup flags
1. Test on a development database first

</details>

---

## Technical Details

### Cleanup Process Flow

1. **Server Startup**: WorldServer reads cleanup flags from worldstates
1. **Flag Processing**: Each enabled flag triggers specific cleanup routines
1. **Database Scanning**: System identifies invalid/obsolete data
1. **Safe Removal**: Data is removed with foreign key integrity checks
1. **Completion**: Cleanup status is logged and flags are reset

### Performance Impact

| Database Size | Cleanup Time | Memory Usage |
|---------------|--------------|--------------|
| **Small** (< 1GB) | 1-5 minutes | Low |
| **Medium** (1-10GB) | 5-30 minutes | Moderate |
| **Large** (> 10GB) | 30+ minutes | High |

---

## Guidelines

### When to Run Cleanup

- **After major TrinityCore updates**
- **Following database schema changes**
- **When players report character issues**
- **During scheduled maintenance windows**

### Cleanup Schedule

```sql
-- Monthly maintenance cleanup (conservative)
UPDATE worldstates SET value = 6 WHERE entry = 20004;  -- Skills + Spells

-- Quarterly full cleanup
UPDATE worldstates SET value = 31 WHERE entry = 20004; -- Everything

-- Always disable after completion
UPDATE worldstates SET value = 0 WHERE entry = 20004;
```

### Monitoring Guidelines

- Monitor server performance during cleanup
- Check database size before and after
- Verify player reports of missing data
- Document cleanup results

---

## Quick Reference

### Common Bitmask Values

| Value | Cleans | Use Case |
|-------|--------|----------|
| `0` | Nothing | Disable cleanup |
| `1` | Achievements only | Achievement fixes |
| `6` | Skills + Spells | Regular maintenance |
| `14` | Skills + Spells + Talents | After talent changes |
| `31` | Everything | Major updates |

### SQL Commands

```sql
-- Enable full cleanup
UPDATE worldstates SET value = 14 WHERE entry = 20004;

-- Check current setting
SELECT * FROM worldstates WHERE entry = 20004;

-- Disable cleanup
UPDATE worldstates SET value = 0 WHERE entry = 20004;
```

---

## Disclaimer

> **Important**: The TrinityCore team is not responsible for data loss or issues from using the character database cleanup system. Database administrators are responsible for:
>
> - Creating backups before running cleanup
> - Testing cleanup operations on development systems
> - Understanding each cleanup flag
> - Monitoring the cleanup process
>
> Use this system at your own risk and follow database administration practices.
