# Character Database Cleanup

The CharacterDB cleanup routines remove old, non-existent, and erroneous
skills, talents, spells, and achievements from characters in the database.

## Configuration

Add an entry in the `worldstates` table (id: 20004) combining the following
flags (bitmask):

| Flag | Value | Description |
|------|-------|-------------|
| `CLEANING_FLAG_ACHIEVEMENT_PROGRESS` | 0x1 | Clean achievements |
| `CLEANING_FLAG_SKILLS` | 0x2 | Clean skills |
| `CLEANING_FLAG_SPELLS` | 0x4 | Clean spells |
| `CLEANING_FLAG_TALENTS` | 0x8 | Clean talents |
| `CLEANING_FLAG_QUESTSTATUS` | 0x10 | Clean quest status |

## Example

To clean up old talents, spells, and skills (but not achievements):

```text
CLEANING_FLAG_SKILLS + CLEANING_FLAG_SPELLS + CLEANING_FLAG_TALENTS = 2 + 4 + 8 = 14
```

Run this SQL on the **characters** database:

```sql
UPDATE worldstates SET value = 14 WHERE entry = 20004;
```

The cleanup runs when the core restarts.

## Warning

Back up your database before running cleanup operations. The TrinityCore
developer team is not responsible for any data loss.
