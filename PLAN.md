# SINON STRIKER — Development Plan

## Phase 1 — Combat Depth & Variety

**Goal:** Make every fight feel distinct with minimal refactoring.

### Features

#### 1a. New Status Effects
- **Frozen** — Skip next turn, then takes +50% damage from the next hit that lands. Added via skills/enemy moves. Implement in `character.tick_status_effects()` and `combat_manager._advance_to_menu()`.
- **Bleed** — Take 4 damage/turn for 4 turns. Bypasses DEF. Stackable intensity (1-3), not duration refresh.
- **Confused** — 50% chance to attack self instead of enemy. Check in `combat_manager._enemy_attack()` and player action resolution.
- **Regen** — Heal 6 HP/turn for 3 turns. Added to `tick_status_effects()` in the buff category.

#### 1b. Unique Enemy Attacks
Every enemy type gets a signature move (currently only Brute, Golem, and Boss have specials):

| Enemy | Move | Trigger | Effect |
|---|---|---|---|
| Slime | Split | Every 4 turns | Heals 15 HP, adds 1 poison stack to player |
| Dragon | Fire Breath | 30% chance | 1.3x ATK + Burn (3 turns, 6 dmg) |
| Wisp | Life Drain | Every 3 turns | 1.2x ATK, heals for 50% of damage dealt |
| Cultist | Dark Hex | 40% chance | 1.0x ATK + Confused (2 turns) |
| Brute | Brute Smash | Every 3 turns | Existing — 1.5x ATK, 25% stun chance |
| Golem | Crush | Every 3 turns | Existing — 2x ATK, ignores 50% DEF |
| Stalker | Backstab | 30% chance | 1.5x ATK, ignores evasion, adds Bleed (2 turns) |
| Boss (Warden) | Warden's Wrath | Every 3 turns | Existing — 2x ATK, plus Phase 2 at 50% HP |

#### 1c. Status Effect UI Indicators
- Small colored icons next to HP bars in `battle_ui.py` showing active status effects on both player and enemy.
- Burn = orange flame, Poison = green droplet, Stun = yellow star, Vulnerable = purple cracked shield, Focused = cyan eye, Frozen = blue snowflake, Bleed = red drop, Confused = pink swirl, Regen = green cross.

#### 1d. Scrollable Full Combat Log
- Extend existing `scroll_log_up/down` in `battle_ui.py` to support PgUp/PgDn for full log review.
- Add a log viewer overlay toggle with a dedicated key (e.g., `L`).

#### 1e. New Achievements
- **Frozen Solid** — Inflict Frozen on 10 enemies. Counter: `frozen_inflicted`, threshold: 10.
- **Bloodletter** — Apply Bleed 20 times. Counter: `bleed_applied`, threshold: 20.
- **Confusion Reigns** — Cause an enemy to hit itself via Confused. One-shot trigger on `confuse_self_hit`.
- **Survivalist** — Heal 500 HP total via Regen. Counter: `regen_healed`, threshold: 500.

**Files touched:** `character.py`, `combat_manager.py`, `battle_ui.py`, `achievements.py`  
**Refactor risk:** Low — additive branches in existing methods, no interface changes.

---

## Phase 2 — Skill Tree + Class System

**Goal:** Give players meaningful build choices from the start. Centerpiece feature.

### Data Model: SkillRegistry

New file: `skills.py`

```python
class SkillTree(Enum):
    VANGUARD = "Vanguard"       # Warrior tank
    BERSERKER = "Berserker"     # Warrior damage
    PYROMANCY = "Pyromancy"     # Mage fire/dot
    ARCANIST = "Arcanist"       # Mage control/debuff
    ASSASSIN = "Assassin"       # Rogue burst
    TRICKSTER = "Trickster"     # Rogue evasion/poison
    SURVIVAL = "Survival"       # Neutral (all classes)

class PlayerClass(Enum):
    WARRIOR = "Warrior"
    MAGE = "Mage"
    ROGUE = "Rogue"
```

Skill defs extend the existing SKILL_DEFS format with `tree` and `unlock_level` fields.

### 2a. Skill Trees (12 skills total)

**Survival Tree (Neutral — all classes)**
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Mend | 1 | 12 | Heal self 25% max HP |
| 2 | Iron Will | 5 | 15 | +30% DEF for 3 turns |
| 3 | Adrenaline | 10 | 20 | +25% ATK for 3 turns, self Vulnerable 1 turn |
| 4 | Last Stand | 15 | 25 | Damage = missing HP × 0.6, cannot be reduced below 1 HP this turn |

**Warrior Class**

*Vanguard Tree (tank/support)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Shield Bash | 1 | 15 | 1.4x ATK, Stun 1 turn |
| 2 | Fortify | 5 | 18 | +50% DEF for 2 turns, self Taunt (enemy forced to target) |
| 3 | Retaliation | 10 | 22 | 1.0x ATK, bonus damage = damage taken last turn × 0.5 |
| 4 | Aegis Strike | 15 | 30 | 2.0x ATK, gain DEF+10 permanently |

*Berserker Tree (risk/reward)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Blood Rage | 1 | 10 | 1.5x ATK, self Bleed 2 turns |
| 2 | Reckless Swing | 5 | 18 | 2.2x ATK, self Vulnerable 2 turns |
| 3 | Death Wish | 10 | 20 | 1.8x ATK, damage scales with missing HP (up to 2.5x at 20% HP) |
| 4 | Annihilate | 15 | 35 | 3.0x ATK, costs 15% current HP to use |

**Mage Class**

*Pyromancy Tree (burn/dot)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Fireball | 1 | 15 | 1.5x ATK, Burn 3 turns (8 dmg) |
| 2 | Inferno | 5 | 22 | 1.0x ATK, Burn 5 turns (10 dmg), hits all status-inflicting effects |
| 3 | Conflagration | 10 | 28 | 2.0x ATK, target takes +50% from Burn damage for 3 turns |
| 4 | Meteor | 15 | 35 | 2.5x ATK, Burn 4 turns (12 dmg), 30% chance to Stun |

*Arcanist Tree (control/debuff)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Frost Bolt | 1 | 14 | 1.3x ATK, Frozen 1 turn |
| 2 | Hex | 5 | 18 | 0.8x ATK, Confused 3 turns |
| 3 | Mana Siphon | 10 | 20 | 1.0x ATK, restore 10 SP on hit |
| 4 | Time Warp | 15 | 30 | 1.8x ATK, enemy skips 2 turns (Stun 2) |

**Rogue Class**

*Assassin Tree (single-target burst)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Backstab | 1 | 15 | 1.8x ATK, ignores 50% DEF |
| 2 | Expose Weakness | 5 | 18 | 1.0x ATK, target Vulnerable 3 turns |
| 3 | Execute | 10 | 25 | 2.5x ATK if target <40% HP, else 1.2x ATK |
| 4 | Death Mark | 15 | 30 | 1.5x ATK, mark target — next attack on marked target is guaranteed crit |

*Trickster Tree (poison/evasion)*
| Tier | Skill | Level | SP | Effect |
|---|---|---|---|---|
| 1 | Poison Dart | 1 | 12 | 1.2x ATK, Poison 3 turns (stacks) |
| 2 | Smoke Bomb | 5 | 16 | 0.5x ATK, +25% evasion for 3 turns |
| 3 | Envenom | 10 | 22 | 1.5x ATK, Poison 4 turns (stacks), Bleed 2 turns |
| 4 | Thousand Cuts | 15 | 28 | 0.5x ATK × 4 hits, each hit applies 1 Poison stack |

### 2b. Class System
- **Class selection** at New Game: after confirming "New Game", a popup offers Warrior / Mage / Rogue with stat previews.
- **Stat differences:**

| Stat | Warrior | Mage | Rogue |
|---|---|---|---|
| Base HP | 120 | 90 | 100 |
| Base ATK | 18 | 12 | 15 |
| Base DEF | 8 | 4 | 5 |
| Max SP | 50 | 75 | 55 |
| Base Crit | 5% | 5% | 10% |
| Base Eva | 5% | 5% | 10% |

- **Tree selection:** At level 1, player picks one specialized tree for their class. All classes also get Survival tree.
- **Respec option:** Add a hub NPC or menu option to respec skill tree choice (costs gold, scales with level).

### 2c. Skill Unlock by Level
- Replace static `SKILL_DEFS` in `combat_manager.py` with calls to `SkillRegistry`.
- `SkillRegistry.get_available_skills(player)` returns list filtered by class, chosen tree, and level.
- SP costs scale: base SP + (skill tier - 1) × 5 additional SP (SP costs listed above already include scaling).
- SP regen: Restore 10 SP per floor completed (in dungeon exit logic).

### 2d. Save/Load Changes
- Add to save schema: `player_class`, `chosen_tree`
- Add: `unlocked_skills` (list of skill IDs) — derived from level, but stored for safety
- Backward compatible: if loading old save without class data, default to Warrior + Berserker

### 2e. New Achievements
- **Class Master: Warrior** — Reach level 20 as Warrior
- **Class Master: Mage** — Reach level 20 as Mage
- **Class Master: Rogue** — Reach level 20 as Rogue
- **Scholar** — Unlock all 8 skills for your class
- **Jack of All Trades** — Use 10 different skills in a single dungeon run
- **Untouchable** — Win 5 fights without taking damage (Rogue synergy)

**Files touched:** `new: skills.py`, `character.py`, `combat_manager.py`, `main.py`, `title_screen.py`, `save_manager.py`, `hub_screen.py`, `achievements.py`  
**Refactor risk:** Moderate — new module, combat_manager reads from registry, main.py adds class pick flow, save schema extension.

---

## Phase 3 — Dungeon & Exploration

**Goal:** Dungeon runs feel different run-to-run and floor-to-floor.

### 3a. Dungeon Biome Themes (3 Zones)

| Zone | Floors | Visual Theme | Enemy Pool Additions | Music |
|---|---|---|---|---|
| The Depths | 1–4 | Cave/rock, warm torchlight | Slime, Dragon, Cultist | Current dungeon music |
| The Catacombs | 5–9 | Crypt/stone, blue torchlight | Brute, Wisp, Stalker | New track (or darker variant) |
| The Abyss | 10+ | Void/dark, purple particles | Golem, all elites more common, Boss every 5 floors | New track (tense/ominous) |

- Biome changes: background color tint, particle effects (dust/sparks per biome), enemy pool weighting.
- Implement in `dungeon.py:generate_dungeon()` — pass biome based on floor.
- Implement in `dungeon_ui.py` — biome-aware background drawing.

### 3b. Shrine Room Type
- New `RoomType.SHRINE` with a procedural icon/glow.
- Offers 3 blessing choices (pick 1):
  - **Blessing of Might** — +20% ATK for the run
  - **Blessing of Fortitude** — +20% DEF for the run
  - **Blessing of Vitality** — Regen 5 HP/turn for the run
- Blessings stored on `DungeonRun` instance, applied in combat via `Character.run_blessings` dict.
- 10% chance to appear as a room (replacing a LOOT room).

### 3c. Dungeon Minimap
- Row of room icons at top of screen in `dungeon_ui.py`.
- Past rooms: dim completed icons. Current room: pulsing highlight. Future rooms: hidden (?) or grayed out outline.
- Shows room type icons (sword for combat, chest for loot, etc.).
- Option to toggle full map overlay with a key.

### 3d. Trap Room Type
- New `RoomType.TRAP` — 8% chance per mid-room roll.
- Effects (random):
  - Spike trap: lose 15% max HP
  - Poison gas: gain Poison 2 turns (carries into combat)
  - Collapse: Stun 1 turn on next combat
- Rogue class bonus: 50% chance to auto-dodge traps.

### 3e. New Achievements
- **Tourist** — Visit all 3 dungeon biomes
- **Blessed** — Use a shrine
- **Devout** — Use 10 shrines
- **Light-Footed** — Dodge a trap (Rogue passive)

**Files touched:** `dungeon.py`, `dungeon_ui.py`, `audio.py`, `achievements.py`, `character.py`  
**Refactor risk:** Moderate — new room types, biome data in dungeon.py, UI additions.

---

## Phase 4 — Hub, NPCs & Depth

**Goal:** The hub feels alive with NPCs, quests, and knowledge systems.

### 4a. Bestiary
- New file: `bestiary.py`
- Tracks per-enemy: encountered (bool), kills (int), floor first encountered.
- New hub location card or overlay (press B in hub).
- Shows enemy name, description, stats, special move, and kill count.
- Unlocks automatically on first encounter of each enemy type.
- Data stored in save file.

### 4b. Quest System
- New file: `quests.py`
- An NPC appears as a new hub location: "Quest Board" or "Guildmaster".
- Quest types:
  - **Hunt:** Kill X of enemy Y — rewards gold
  - **Collect:** Find X items of rarity Y+ — rewards item
  - **Reach:** Clear floor X — rewards XP
  - **Boss:** Defeat a boss — rewards Legendary item
- 3 active quests max. Complete to claim reward, then new quest spawns.
- Progress tracked in save file. Counter quests update after each battle.
- Quest state saved: `active_quests` list, `completed_quests` count.

### 4c. Equipment Slots: Ring + Amulet
- New `ItemSlot.RING` and `ItemSlot.AMULET` in `item.py`.
- Ring stats: +crit% or +acc%. Amulet stats: +max SP or status resist%.
- New equipment entries in `character.equipment` dict.
- New base names: Ring names (Band, Loop, Signet, Circlet), Amulet names (Charm, Pendant, Talisman, Locket).
- LootGenerator extended: 8% ring, 7% amulet (drawn from weapon/armor %).
- Sell/buy at Smithy/Merchant.
- Save schema extended for ring and amulet slots.
- Battle UI equipment display extended.

### 4d. Smithy Enhancement
- New option in Smithy: "Upgrade" tab (toggle between Sell and Upgrade with Tab).
- Costs scale with current rarity:
  - Common → Rare: 100g + 50g per stat point
  - Rare → Epic: 300g + 100g per stat point
  - Epic cap: cannot upgrade to Legendary (Legendary must be found)
- Base stats increase, rarity prefix/color updates. Set name preserved.
- Achievement: **Artificer** — Upgrade 5 items.

### 4e. New Achievements
- **Librarian** — Complete the bestiary (encounter all 8 enemies)
- **Quest Master** — Complete 10 quests
- **Artificer** — Upgrade 5 items at the Smithy
- **Accessorized** — Equip a Ring and Amulet simultaneously

**Files touched:** `new: bestiary.py`, `new: quests.py`, `item.py`, `character.py`, `combat_manager.py`, `save_manager.py`, `hub_screen.py`, `battle_ui.py`, `main.py`, `achievements.py`  
**Refactor risk:** Moderate — two new modules, equipment slot plumbing through multiple files, hub sub-state additions.

---

## Phase 5 — Polish, Balance & NG+

**Goal:** Full-featured, polished, replayable experience.

### 5a. New Game Plus
- After reaching floor 15+ and returning to title, "New Game Plus" option appears.
- NG+ changes:
  - Enemies scale 1.5x harder (HP/ATK/DEF multiplier on top of floor scaling)
  - Carry over: bestiary, achievement progress, a starting gold bonus (15% of previous gold)
  - Reset: level, equipment, consumables, quests, floor progress
  - NG+ badge visible on save file
- Implement in `main.py` (title screen option) and `save_manager.py` (NG+ flag).

### 5b. Balance Pass
- **XP curve:** Review `character._calc_xp_to_next()`. Current: 50 + level×25. Slightly steep at high levels — may need smoothing post-level 20.
- **Gold economy:** Review shop prices vs. dungeon rewards. Ensure Merchant gear feels worth buying vs. finding in dungeons.
- **Enemy stats:** Tune per-biome enemy pools to ensure smooth difficulty curve.
- **Rarity weights:** Review `RARITY_WEIGHTS` per floor range to ensure Legendaries feel special but not impossible.
- **Skill balance:** Playtest all 12 skills — adjust SP costs and damage multipliers.

### 5c. Visual Polish
- **Screen shake:** More pronounced on crits and boss attacks. Decay curve for smoother feel.
- **Damage numbers:** Floating damage numbers that rise and fade above targets (optional toggle).
- **Enemy death animation:** Fade-out + particle burst on enemy death. Boss gets a special death sequence.
- **Level-up celebration:** Enhanced visual — full screen flash, particle ring expanding outward.
- **Transition polish:** Smoother fades between hub/dungeon/battle states.

### 5d. Full Audio Pass
- New SFX for: all 12 skills, Frozen/Bleed/Confused/Regen application, Shrine activation, Trap trigger, quest complete, enhancement success, NG+ start.
- New music tracks: Catacombs theme, Abyss theme (or variants of existing with filters).
- Audio balance: normalize all SFX to similar perceived loudness.

### 5e. Final Achievement Set
- **Demi-God** — Reach level 50
- **NG+ Conqueror** — Clear floor 10 on NG+
- **Completionist** — Unlock all other achievements
- **Speed Runner** — Clear a dungeon in under 2 minutes
- **Pacifist** — Clear a floor without defeating any combat rooms (via Rest/Loot/Exit path)

**Files touched:** `main.py`, `save_manager.py`, `dungeon.py`, `item.py`, `character.py`, `combat_manager.py`, `battle_ui.py`, `dungeon_ui.py`, `audio.py`, `achievements.py`  
**Refactor risk:** Light to moderate — tuning numbers, adding visual effects, audio assets.

---

## Implementation Order Summary

| Phase | Key Deliverable | Files | Risk | Est. Scope |
|---|---|---|---|---|
| 1 | Status effects, enemy moves, UI polish | 4 | Low | ~300 lines |
| 2 | 12-skill tree, 3 classes, level-gated unlocks | 8 | Moderate | ~800 lines |
| 3 | 3 biomes, shrines, minimap, trap rooms | 6 | Moderate | ~500 lines |
| 4 | Bestiary, quests, ring/amulet, enhancement | 9 | Moderate | ~700 lines |
| 5 | NG+, balance, VFX, audio, final achievements | 10 | Light | ~400 lines |

**Total estimated new code:** ~2,700 lines across all phases.
