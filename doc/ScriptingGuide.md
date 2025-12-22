# TrinityCore Scripting Guide

> **Note**: This documentation may not always be up-to-date. For the latest
> information, check the [TrinityCore Wiki](https://trinitycore.info/).
>
> **Advanced Guide**: For comprehensive scripting documentation, visit the
> [TrinityCore Wiki Scripting Section](https://trinitycore.atlassian.net/wiki/spaces/tc/pages/2130344/Scripting).

---

## What is TrinityCore Scripting?

TrinityCore uses **C++ scripts** to implement custom game mechanics like:

- **Dungeon and Raid Bosses** - Complex AI behaviors and mechanics
- **Quest Scripts** - Custom quest objectives and rewards
- **Game Events** - Seasonal events and world events
- **Items and Spells** - Custom effects and behaviors
- **World Scripts** - Server-wide mechanics and systems

---

## Quick Start Guide

### Step 1: Set Up Your Environment

Before writing scripts, ensure you have:

- **TrinityCore source code** compiled and working
- **Development environment** (Visual Studio, CLion, VS Code, etc.)
- **Basic C++ knowledge** and familiarity with TrinityCore structure

### Step 2: Choose Your Script Type

TrinityCore provides several script base classes:

| Script Type | Use Case | Base Class |
|-------------|----------|------------|
| **Creature Scripts** | NPC AI, boss mechanics | `CreatureScript` |
| **Spell Scripts** | Custom spell effects | `SpellScript` |
| **Item Scripts** | Item use effects | `ItemScript` |
| **Quest Scripts** | Quest rewards, objectives | `QuestScript` |
| **Instance Scripts** | Dungeon/raid mechanics | `InstanceScript` |
| **Game Object Scripts** | Interactive objects | `GameObjectScript` |

---

## Creating Your First Script

### Step 1: Create the Script File

Create a new file in the `src/server/scripts/Custom/` directory:

```cpp
/*
 * This file is part of the TrinityCore Project. See AUTHORS file for Copyright information
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2 of the License, or (at your
 * option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#include "ScriptMgr.h"
#include "Player.h"
#include "CreatureScript.h"

class my_custom_npc : public CreatureScript
{
public:
    my_custom_npc() : CreatureScript("my_custom_npc") { }

    bool OnGossipHello(Player* player, Creature* creature) override
    {
        player->GetSession()->SendNotification("Hello from custom script!");
        return true;
    }
};

// Register the script
void AddSC_my_custom_scripts()
{
    new my_custom_npc();
}
```

### Step 2: Add to CMakeLists.txt

Edit `src/server/scripts/CMakeLists.txt` and add your file:

```cmake
# Find the Custom section and add your script
set(scripts_STAT_SRCS
  # ... existing files ...
  Custom/my_custom_script.cpp
  # ... more files ...
)
```

### Step 3: Register in Script Loader

Edit `src/server/scripts/Custom/custom_script_loader.cpp`:

```cpp
// Add your function declaration above AddCustomScripts()
void AddSC_my_custom_scripts();

// Add the call in AddCustomScripts()
void AddCustomScripts()
{
    AddSC_my_custom_scripts();  // Add this line
}
```

### Step 4: Add Database Entry

Connect the script to an NPC in your database:

```sql
-- Update an existing NPC or create a new one
UPDATE creature_template SET ScriptName = 'my_custom_npc' WHERE entry = 123456;
```

### Step 5: Compile and Test

1. **Recompile** TrinityCore
1. **Restart** the server
1. **Test** your script by interacting with the NPC

---

## Script Examples

### Boss Script Example

```cpp
class boss_custom_encounter : public CreatureScript
{
public:
    boss_custom_encounter() : CreatureScript("boss_custom_encounter") { }

    struct boss_custom_encounterAI : public BossAI
    {
        boss_custom_encounterAI(Creature* creature) : BossAI(creature, DATA_CUSTOM_BOSS) { }

        void Reset() override
        {
            BossAI::Reset();
            events.ScheduleEvent(EVENT_SPECIAL_ABILITY, 10000);
        }

        void UpdateAI(uint32 diff) override
        {
            if (!UpdateVictim())
                return;

            events.Update(diff);

            while (uint32 eventId = events.ExecuteEvent())
            {
                switch (eventId)
                {
                    case EVENT_SPECIAL_ABILITY:
                        DoCastVictim(SPELL_SPECIAL_ATTACK);
                        events.ScheduleEvent(EVENT_SPECIAL_ABILITY, 15000);
                        break;
                }
            }

            DoMeleeAttackIfReady();
        }
    };

    CreatureAI* GetAI(Creature* creature) const override
    {
        return new boss_custom_encounterAI(creature);
    }
};
```

### Spell Script Example

```cpp
class spell_custom_effect : public SpellScript
{
    PrepareSpellScript(spell_custom_effect);

    void HandleDamage(SpellEffIndex /*effIndex*/)
    {
        Unit* caster = GetCaster();
        Unit* target = GetHitUnit();

        if (!caster || !target)
            return;

        // Custom damage calculation
        int32 damage = GetHitDamage();
        damage *= 2; // Double damage
        SetHitDamage(damage);
    }

    void Register() override
    {
        OnEffectHitTarget += SpellEffectFn(spell_custom_effect::HandleDamage, EFFECT_0, SPELL_EFFECT_SCHOOL_DAMAGE);
    }
};

class spell_custom_effect_AuraScript : public AuraScript
{
    PrepareAuraScript(spell_custom_effect_AuraScript);

    void OnApply(AuraEffect const* /*effect*/, AuraEffectHandleModes /*mode*/)
    {
        if (Unit* target = GetTarget())
            target->GetSession()->SendNotification("Custom aura applied!");
    }

    void Register() override
    {
        OnEffectApply += AuraEffectApplyFn(spell_custom_effect_AuraScript::OnApply, EFFECT_0, SPELL_AURA_MOD_DAMAGE_DONE, AURA_EFFECT_HANDLE_REAL);
    }
};

// Register both scripts
void AddSC_custom_spells()
{
    RegisterSpellScript(spell_custom_effect);
    RegisterSpellAndAuraScriptPair(spell_custom_effect, spell_custom_effect_AuraScript);
}
```

### Quest Script Example

```cpp
class quest_custom_objective : public QuestScript
{
public:
    quest_custom_objective() : QuestScript("quest_custom_objective") { }

    void OnQuestStatusChange(Player* player, Quest const* /*quest*/) override
    {
        player->GetSession()->SendNotification("Quest status changed via script!");
    }

    void OnQuestReward(Player* player, Quest const* quest, uint32 /*opt*/) override
    {
        // Give custom reward
        player->AddItem(12345, 1); // Add custom item
        player->GiveXP(1000, nullptr); // Bonus XP
        player->GetSession()->SendNotification("Custom quest reward given!");
    }
};
```

---

## Advanced Scripting Concepts

### Event System

TrinityCore uses an event-driven system for timing:

```cpp
enum Events
{
    EVENT_SPELL_CAST = 1,
    EVENT_MOVEMENT,
    EVENT_SPECIAL_ABILITY
};

// In your AI class
void Reset() override
{
    events.Reset();
    events.ScheduleEvent(EVENT_SPELL_CAST, 5000);  // 5 seconds
}

void UpdateAI(uint32 diff) override
{
    events.Update(diff);

    while (uint32 eventId = events.ExecuteEvent())
    {
        switch (eventId)
        {
            case EVENT_SPELL_CAST:
                DoCastVictim(SPELL_ID);
                events.ScheduleEvent(EVENT_SPELL_CAST, urand(8000, 12000));
                break;
        }
    }
}
```

### Instance Scripts

For dungeons and raids:

```cpp
class instance_custom_dungeon : public InstanceMapScript
{
public:
    instance_custom_dungeon() : InstanceMapScript("instance_custom_dungeon", MAP_ID) { }

    InstanceScript* GetInstanceScript(InstanceMap* map) const override
    {
        return new instance_custom_dungeon_InstanceMapScript(map);
    }

    struct instance_custom_dungeon_InstanceMapScript : public InstanceScript
    {
        instance_custom_dungeon_InstanceMapScript(InstanceMap* map) : InstanceScript(map) { }

        void OnCreatureCreate(Creature* creature) override
        {
            switch (creature->GetEntry())
            {
                case NPC_BOSS:
                    bossGUID = creature->GetGUID();
                    break;
            }
        }

        void SetData(uint32 type, uint32 data) override
        {
            switch (type)
            {
                case DATA_BOSS_DIED:
                    // Handle boss death
                    break;
            }
        }

    private:
        ObjectGuid bossGUID;
    };
};
```

---

## Essential References

### Finding Examples

Look at existing scripts for guidance:

```bash
# Find creature scripts
find src/server/scripts/ -name "*.cpp" -exec grep -l "CreatureScript" {} \;

# Find spell scripts
find src/server/scripts/ -name "*.cpp" -exec grep -l "SpellScript" {} \;

# Search for specific mechanics
grep -r "DoCastVictim" src/server/scripts/
```

### Common Include Files

```cpp
#include "ScriptMgr.h"        // Required for all scripts
#include "Player.h"           // Player interactions
#include "Creature.h"         // Creature/NPC scripts
#include "GameObject.h"       // GameObject scripts
#include "SpellScript.h"      // Spell scripts
#include "InstanceScript.h"   // Instance/dungeon scripts
#include "Chat.h"             // Chat commands
#include "WorldSession.h"     // Session management
```

### Common Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `DoCastVictim()` | Cast spell on current target | `DoCastVictim(SPELL_FIREBALL);` |
| `DoCastSelf()` | Cast spell on self | `DoCastSelf(SPELL_HEAL);` |
| `DoResetThreat()` | Reset threat/aggro | `DoResetThreat();` |
| `SendNotification()` | Send message to player | `player->GetSession()->SendNotification("Hello!");` |
| `AddItem()` | Give item to player | `player->AddItem(12345, 1);` |

---

## Debugging Scripts

### Common Issues

<details>
<summary><strong>Script Not Loading</strong></summary>

**Check these items:**

- Script is added to `CMakeLists.txt`
- `AddSC_` function is called in `ScriptLoader.cpp`
- Database `ScriptName` matches script constructor
- Server was recompiled after adding script

</details>

<details>
<summary><strong>Compilation Errors</strong></summary>

**Common causes:**

- Missing include files
- Incorrect function signatures
- Typos in class/function names
- Missing virtual function overrides

**Solution**: Check existing scripts for correct syntax.

</details>

<details>
<summary><strong>Script Crashes Server</strong></summary>

**Safety checks to add:**

```cpp
// Always check for null pointers
if (!player || !creature)
    return;

// Validate spell IDs exist
if (!sSpellMgr->GetSpellInfo(SPELL_ID))
    return;

// Check object validity
if (!creature->IsAlive())
    return;
```

</details>

### Debug Tools

```cpp
// Add debug logging
TC_LOG_INFO("scripts", "Custom script: Player %s interacted with NPC",
    player->GetName().c_str());

// Console output for testing
ChatHandler(player->GetSession()).SendSysMessage("Debug message");

// Use assertions for development
ASSERT(player);
```

---

## Best Practices

### Code Quality

- **Follow naming conventions** (snake_case for functions, PascalCase for classes)
- **Add meaningful comments** explaining complex logic
- **Always check for null pointers** before using objects
- **Test thoroughly** on a development server first
- **Study existing scripts** before writing new ones

### Architecture

- **Keep scripts focused** - one script per mechanic
- **Use events system** for timing instead of counters
- **Organize files logically** in appropriate directories
- **Follow TrinityCore conventions** for consistency

### Performance

- **Avoid expensive operations** in frequently called functions
- **Cache frequently used data** instead of repeated lookups
- **Profile scripts** that handle many players/creatures
- **Use appropriate timers** for periodic actions

---

## Quick Reference

### Script Registration Template

```cpp
void AddSC_my_script_name()
{
    new my_creature_script();
    RegisterSpellScript(my_spell_script);
    new my_quest_script();
}
```

### CMakeLists.txt Entry

```cmake
Custom/my_script.cpp
```

### custom_script_loader.cpp Entry

```cpp
void AddSC_my_script_name();  // Declaration

void AddCustomScripts()
{
    AddSC_my_script_name();   // Registration
}
```

---

## Additional Resources

### Official Documentation

- **[TrinityCore Wiki](https://trinitycore.atlassian.net/wiki)** - Official documentation
- **[API Documentation](https://trinitycore.info/en/doxygen/)** - Code reference
- **[Community Forums](https://community.trinitycore.org)** - Ask for help

### Community Resources

- **[Discord #scripting](https://discord.trinitycore.org/)** - Real-time scripting help
- **[GitHub Examples](https://github.com/TrinityCore/TrinityCore/tree/cata_classic/src/server/scripts)** - Browse existing scripts
- **[YouTube Tutorials](https://www.youtube.com/results?search_query=trinitycore+scripting)** - Video guides

---

## Important Notes

> **Documentation Status**: This guide provides basic scripting information. For the most current and comprehensive scripting documentation, always refer to the [TrinityCore Wiki](https://trinitycore.atlassian.net/wiki/spaces/tc/pages/2130344/Scripting).
>
> **Learning Path**: Start with simple creature scripts before attempting complex spell or instance scripts. Study existing scripts in the codebase to understand best practices.
>
> **Server Stability**: Always test scripts thoroughly on a development server before deploying to production. Poorly written scripts can crash the server or cause data corruption.
