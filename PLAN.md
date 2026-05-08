# SINON STRIKER — Remaining Development Plan

This plan only tracks work that is still left to do.

## 1. Combat UI Polish

**Goal:** Make battle flow easier to read and review.

### 1a. Full Combat Log Overlay
- Add a dedicated log viewer overlay in `battle_ui.py`.
- Keep PgUp / PgDn scrolling for the battle log.
- Add a toggle key, such as `L`, to open and close the overlay.
- Make sure the viewer can show the full history of the fight, not just the recent lines.

### 1b. Optional Log Quality-of-Life
- Improve log readability when many status effects trigger in one turn.
- Keep the recent combat log compact during normal play.

---

## 2. Hub Depth

**Goal:** Add more long-term progression and reasons to return to town.

### 2a. Respec Option
- Add a hub NPC or menu option to respec the chosen skill tree.
- Charge gold for respecs, with the price scaling by level or progress.
- Make sure respec updates the player cleanly without breaking save data.

### 2b. Bestiary
- Create a bestiary that tracks enemies encountered, kills, and first encounter floor.
- Add a hub entry or overlay to browse the bestiary.
- Store bestiary progress in save data.
- Show enemy notes, stats, and any special attack info that has been discovered.

### 2c. Quest System
- Add a quest board or quest-giver NPC in the hub.
- Support quest types such as:
  - Hunt: kill X of a given enemy
  - Collect: find items of a given rarity
  - Reach: clear a target floor
  - Boss: defeat a boss
- Limit the player to 3 active quests at a time.
- Save active quests and completed quest counts.

### 2d. Smithy Enhancement
- Add an upgrade tab to the Smithy.
- Let players improve gear rarity instead of only selling it.
- Preserve item identity, set name, and overall build direction during upgrades.
- Add an achievement for repeated upgrades.

---

## 3. Equipment Expansion

**Goal:** Give players more build variety through item slots and loot.

### 3a. Ring and Amulet Slots
- Add `Ring` and `Amulet` equipment slots.
- Decide which stats these items can roll, such as crit, accuracy, max SP, or status resistance.
- Extend loot generation to include these item types.
- Update hub vendors and battle UI to show the new slots.
- Extend save/load for the new equipment fields.

### 3b. Loot Table Tuning
- Rebalance item generation once the new slots exist.
- Make sure rings and amulets do not crowd out weapons and armor.

---

## 4. New Game Plus

**Goal:** Let players keep going after the main climb is complete.

### 4a. NG+ Mode
- Add a New Game Plus option from the title screen once the base run has been cleared far enough.
- Carry over selected progress such as achievements and bestiary data.
- Reset run-specific progress such as level, equipment, consumables, quests, and floor state.
- Apply stronger enemy scaling for NG+ runs.
- Show NG+ state clearly in save data and on the title screen.

---

## 5. Balance, Polish, and Audio

**Goal:** Finish the game feel and make the whole loop smoother.

### 5a. Balance Pass
- Review XP pacing.
- Review gold economy and shop pricing.
- Tune enemy stats across floors and biomes.
- Recheck rarity weights and loot rewards.
- Revisit skill costs and damage values after all remaining systems are in place.

### 5b. Visual Polish
- Improve screen shake and hit feedback.
- Add or refine damage number popups.
- Add enemy death and boss death effects.
- Smooth out transition fades between hub, dungeon, and battle states.

### 5c. Audio Pass
- Add missing SFX for remaining systems.
- Add or refine music variants for later-game zones and NG+.
- Normalize overall audio balance.

---

## 6. Remaining Achievements

- **Librarian** — Complete the bestiary.
- **Quest Master** — Complete 10 quests.
- **Artificer** — Upgrade 5 items at the Smithy.
- **Accessorized** — Equip a Ring and Amulet simultaneously.
- **Demi-God** — Reach level 50.
- **NG+ Conqueror** — Clear floor 10 on NG+.
- **Completionist** — Unlock all other achievements.
- **Speed Runner** — Clear a dungeon in under 2 minutes.
- **Pacifist** — Clear a floor without defeating any combat rooms.

---

## Implementation Order

| Priority | Key Deliverable |
|---|---|
| 1 | Combat log overlay |
| 2 | Respec, bestiary, and quests |
| 3 | Ring/amulet slots and smithy upgrades |
| 4 | NG+ |
| 5 | Balance, polish, audio, and remaining achievements |

