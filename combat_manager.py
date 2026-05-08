"""
Combat Manager - handles the turn-based state machine for battles.

States:
  WAIT         -> Initial state, waiting to start
  MENU_SELECT  -> Player is browsing the command menu (waiting for selection)
  SKILL_SELECT -> Player is browsing the skill sub-menu
  ITEM_SELECT  -> Player is browsing the item sub-menu
  PLAYER_ACTION -> Action confirmed, executing player move
  ENEMY_TURN   -> Enemy automatically attacks after a delay
  INVENTORY    -> Equipment management overlay
  VICTORY      -> Enemy HP <= 0
  DEFEAT       -> Player HP <= 0
"""

from enum import Enum, auto
import random
from character import Character, Enemy
from item import LootGenerator, ItemSlot, Consumable, Weapon, Armor, Rarity, pop_from_stack, merge_into_stack
from skills import SkillRegistry


class TurnState(Enum):
    WAIT = auto()
    MENU_SELECT = auto()
    SKILL_SELECT = auto()
    ITEM_SELECT = auto()
    PLAYER_ACTION = auto()
    ENEMY_TURN = auto()
    INVENTORY = auto()
    VICTORY = auto()
    DEFEAT = auto()


class MenuAction(Enum):
    ATTACK = auto()
    SKILL  = auto()
    ITEM   = auto()


MENU_OPTIONS = [MenuAction.ATTACK, MenuAction.SKILL, MenuAction.ITEM]


class CombatManager:
    """Manages the turn-based combat flow between a player and an enemy."""

    ENEMY_DELAY_MS = 1000

    def __init__(self, player: Character, enemy: Enemy, sound_manager=None, ach_manager=None, is_boss: bool = False, floor: int = 1, quest_manager=None, bestiary_manager=None):
        self.player = player
        self.enemy = enemy
        self._state = TurnState.WAIT
        self._log: list[str] = []
        self._enemy_timer: int = 0
        self._snd = sound_manager
        self._ach_manager = ach_manager
        self._quest_manager = quest_manager
        self._bestiary_manager = bestiary_manager
        self.in_dungeon = False  # set True when in a dungeon run
        self.is_boss = is_boss
        self.floor = floor

        # Menu selection tracking
        self.selected_index: int = 0
        self.sub_selected_index: int = 0

        # Inventory cursor tracking
        self.inv_cursor: int = 0
        self.inv_section: str = "bag"  # "equipped" or "bag"
        self.inv_equip_cursor: int = 0  # 0 = weapon, 1 = armor
        self.inv_scroll_offset: int = 0
        self._gold_dropped: int = 0
        self._xp_gained: int = 0
        self._level_ups: list = []
        self.victory_phase: str = "rewards"  # "rewards" or "level_up"
        self._last_hit_info = None
        self._last_status_tick = None
        self._shake_source = None
        self._player_confused: bool = False
        self._enemy_turn_count: int = 0
        self._boss_phase2_triggered: bool = False

        # Dynamic skill list from registry
        self._available_skills = SkillRegistry.get_available_skills(player)

        # Apply dungeon blessings (from shrine)
        self._apply_blessings()

        # Kick off the first round
        self._advance_to_menu()

    # ------------------------------------------------------------------ #
    #  Properties                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_player_turn(self) -> bool:
        """True when the player can act (browsing menu or confirming action)."""
        return self._state in (TurnState.MENU_SELECT, TurnState.SKILL_SELECT, TurnState.ITEM_SELECT, TurnState.PLAYER_ACTION, TurnState.INVENTORY)

    @property
    def combat_active(self) -> bool:
        """True while combat is in an active turn (not Victory/Defeat)."""
        return self._state in (
            TurnState.WAIT,
            TurnState.MENU_SELECT,
            TurnState.SKILL_SELECT,
            TurnState.ITEM_SELECT,
            TurnState.PLAYER_ACTION,
            TurnState.ENEMY_TURN,
            TurnState.INVENTORY,
        )

    @property
    def selected_index(self) -> int:
        """Return the currently highlighted menu index."""
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int):
        self._selected_index = max(0, min(value, len(MENU_OPTIONS) - 1))

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> TurnState:
        """Return the current turn state."""
        return self._state

    @state.setter
    def state(self, value: TurnState):
        self._state = value

    def move_menu_up(self):
        """Move the menu selection up by one."""
        if self.state != TurnState.MENU_SELECT:
            return
        self.selected_index -= 1

    def move_menu_down(self):
        """Move the menu selection down by one."""
        if self.state != TurnState.MENU_SELECT:
            return
        self.selected_index += 1

    def confirm_action(self):
        """Confirm the currently selected menu action."""
        if self.state != TurnState.MENU_SELECT:
            return

        action = MENU_OPTIONS[self._selected_index]

        if action == MenuAction.ATTACK:
            self._sfx("menu_confirm")
            self.state = TurnState.PLAYER_ACTION
            self._execute_attack()
        elif action == MenuAction.SKILL:
            self.sub_selected_index = 0
            self.state = TurnState.SKILL_SELECT
        elif action == MenuAction.ITEM:
            self.sub_selected_index = 0
            if self.player.consumables:
                self.state = TurnState.ITEM_SELECT
            else:
                self._add_log("No consumable items!")

    # ------------------------------------------------------------------ #
    #  Sub-menu navigation (Skill / Item)                                #
    # ------------------------------------------------------------------ #

    def _sub_menu_length(self) -> int:
        """Return the number of options in the current sub-menu."""
        if self.state == TurnState.SKILL_SELECT:
            return max(1, len(self._available_skills))
        elif self.state == TurnState.ITEM_SELECT:
            return max(1, len(self.player.consumables))
        return 0

    def move_sub_up(self):
        """Move the sub-menu cursor up."""
        if self.state not in (TurnState.SKILL_SELECT, TurnState.ITEM_SELECT):
            return
        self.sub_selected_index = max(0, self.sub_selected_index - 1)

    def move_sub_down(self):
        """Move the sub-menu cursor down."""
        if self.state not in (TurnState.SKILL_SELECT, TurnState.ITEM_SELECT):
            return
        max_idx = self._sub_menu_length() - 1
        self.sub_selected_index = min(max_idx, self.sub_selected_index + 1)

    def cancel_sub_menu(self):
        """Return from sub-menu back to MENU_SELECT."""
        if self.state in (TurnState.SKILL_SELECT, TurnState.ITEM_SELECT):
            self.state = TurnState.MENU_SELECT

    def confirm_sub_action(self):
        """Confirm the selected skill or consumable."""
        if self.state == TurnState.SKILL_SELECT:
            self._confirm_skill()
        elif self.state == TurnState.ITEM_SELECT:
            self._confirm_item()

    def _confirm_skill(self):
        skill = self._available_skills[self.sub_selected_index]
        if skill["name"] in self.player.skill_cooldowns:
            self._sfx("error")
            self._add_log(f"{skill['name']} is on cooldown!")
            return
        if self.player.sp < skill.get("cost", 0):
            self._sfx("error")
            self._add_log(f"Not enough SP! Need {skill['cost']}, have {self.player.sp}.")
            return
        self._execute_skill(skill)

    def _confirm_item(self):
        """Execute the selected consumable item use."""
        if not self.player.consumables:
            return
        item = self.player.consumables[self.sub_selected_index]
        self._sfx("item_use")

        missing = self.player.max_hp - self.player.current_hp
        healed = min(item.hp_restore, missing)
        self.player.current_hp += healed

        qty = item.quantity
        pop_from_stack(self.player.consumables, self.sub_selected_index)
        if qty > 1:
            self._add_log(f"Hero uses {item.name} x{qty - 1} left! Restored {healed} HP!")
        else:
            self._add_log(f"Hero uses {item.name}! Restored {healed} HP!")

        # Clamp cursor
        if self.player.consumables and self.sub_selected_index >= len(self.player.consumables):
            self.sub_selected_index = max(0, len(self.player.consumables) - 1)
        elif not self.player.consumables:
            self.state = TurnState.MENU_SELECT
            return

        self.state = TurnState.MENU_SELECT

    # ------------------------------------------------------------------ #
    #  Inventory management                                              #
    # ------------------------------------------------------------------ #

    def open_inventory(self):
        """Open the inventory overlay (only from MENU_SELECT)."""
        if self.state != TurnState.MENU_SELECT:
            return
        self.inv_cursor = 0
        self.inv_scroll_offset = 0
        self.state = TurnState.INVENTORY

    def close_inventory(self):
        """Close the inventory and return to MENU_SELECT."""
        if self.state != TurnState.INVENTORY:
            return
        self.state = TurnState.MENU_SELECT

    def move_inv_up(self):
        """Move the inventory cursor up."""
        if self.state != TurnState.INVENTORY:
            return
        if self.inv_section == "bag" and self.player.inventory:
            self.inv_cursor = (self.inv_cursor - 1) % len(self.player.inventory)
            if self.inv_cursor < self.inv_scroll_offset:
                self.inv_scroll_offset = self.inv_cursor
        elif self.inv_section == "equipped":
            self.inv_equip_cursor = (self.inv_equip_cursor - 1) % 4

    def move_inv_down(self):
        """Move the inventory cursor down."""
        if self.state != TurnState.INVENTORY:
            return
        if self.inv_section == "bag" and self.player.inventory:
            self.inv_cursor = (self.inv_cursor + 1) % len(self.player.inventory)
        elif self.inv_section == "equipped":
            self.inv_equip_cursor = (self.inv_equip_cursor + 1) % 4

    def toggle_inv_section(self):
        """Switch between equipped and bag sections in inventory."""
        if self.state != TurnState.INVENTORY:
            return
        self.inv_section = "equipped" if self.inv_section == "bag" else "bag"
        self.inv_cursor = 0
        self.inv_equip_cursor = 0
        self.inv_scroll_offset = 0

    def sort_inventory(self):
        """Sort bag inventory by rarity (highest first), then by stat value."""
        RANK = {Rarity.LEGENDARY: 3, Rarity.EPIC: 2, Rarity.RARE: 1, Rarity.COMMON: 0}
        self.player.inventory.sort(
            key=lambda it: (RANK.get(it.rarity, 0), it.atk if isinstance(it, Weapon) else it.defense),
            reverse=True,
        )
        self.inv_cursor = 0
        self.inv_scroll_offset = 0

    def equip_selected(self):
        """Equip the inventory item under the cursor. Swaps out old gear."""
        if self.state != TurnState.INVENTORY:
            return
        if self.inv_section != "bag":
            return
        if not self.player.inventory:
            return

        item = self.player.inventory[self.inv_cursor]
        old_item = self.player.equip(item)
        self.player.inventory.pop(self.inv_cursor)

        if old_item is not None:
            self.player.inventory.append(old_item)

        if self.player.inventory and self.inv_cursor >= len(self.player.inventory):
            self.inv_cursor = len(self.player.inventory) - 1
        elif not self.player.inventory:
            self.inv_cursor = 0

        self._add_log(f"Equipped {item.name}!")

    def unequip_selected(self):
        """Unequip the selected item."""
        if self.state != TurnState.INVENTORY:
            return

        if self.inv_section == "equipped":
            slot_key = ["weapon", "armor", "ring", "amulet"][self.inv_equip_cursor]
            old_item = self.player.unequip_slot(slot_key)
            if old_item is not None:
                self.player.inventory.append(old_item)
                self._add_log(f"Unequipped {old_item.name}!")
        else:
            if not self.player.inventory:
                return
            item = self.player.inventory[self.inv_cursor]
            slot_key = {
                ItemSlot.WEAPON: "weapon",
                ItemSlot.ARMOR: "armor",
                ItemSlot.RING: "ring",
                ItemSlot.AMULET: "amulet",
            }.get(item.slot, "weapon")
            old_item = self.player.unequip_slot(slot_key)
            if old_item is not None:
                self.player.inventory.append(old_item)
                self._add_log(f"Unequipped {old_item.name}!")

    def _execute_skill(self, skill: dict):
        cost = skill.get("cost", 0)
        self.player.sp -= cost
        self._sfx("skill")
        if self._ach_manager:
            self._ach_manager.inc("skills_used")

        # Confused: 50% chance to hit self (only for damage skills)
        if skill.get("damage_mult", 0) > 0 and getattr(self, '_player_confused', False) and random.random() < 0.5:
            self._player_confused = False
            damage = max(1, int(self.player.atk * skill["damage_mult"] * 0.5))
            actual = self.player.take_damage(damage)
            self._last_hit_info = {"target": "player", "damage": actual, "is_crit": False, "confused_self": True}
            self._add_log(f"{self.player.name} is confused and hits themselves with {skill['name']}! ({actual} damage)")
            self._sfx("player_hit")
            if self._ach_manager:
                self._ach_manager.unlock("confuse_self_hit")
            if not self.player.is_alive:
                self.state = TurnState.DEFEAT
                self._add_log(f"{self.player.name} has fallen... Defeat.")
            else:
                self._advance_to_enemy_turn()
            return
        self._player_confused = False

        # ── Non-damage skills (heal / buff) ──
        if skill.get("damage_mult", 0) == 0:
            # Heal skill (Mend)
            if "heal_pct" in skill:
                heal = int(self.player.max_hp * skill["heal_pct"])
                heal = min(heal, self.player.max_hp - self.player.current_hp)
                self.player.current_hp += heal
                self._sfx("item_use")
                self._add_log(f"{self.player.name} uses {skill['name']}! Heals {heal} HP!")

            # Buff skill
            elif "buff" in skill:
                self._sfx("buff")
                self.player.add_status(skill["buff"], "buff", skill.get("buff_duration", 3))
                self._add_log(f"{self.player.name} uses {skill['name']}! {skill.get('desc', '')}")

            # Last Stand
            elif skill.get("special") == "last_stand":
                missing = self.player.max_hp - self.player.current_hp
                damage = max(1, int(missing * 0.6))
                actual = self.enemy.take_damage(damage)
                self._last_hit_info = {"target": "enemy", "damage": actual, "is_crit": False}
                self._add_log(f"{self.player.name} uses Last Stand! Deals {actual} damage! (missing HP: {missing})")
                self._sfx("skill")
                self._shake_source = "player"
                if not self.enemy.is_alive:
                    self._mark_victory_progress()
                    if self._ach_manager:
                        self._ach_manager.inc("kills")
                    self._award_xp()
                    self.state = TurnState.VICTORY
                    self._add_log(f"{self.enemy.name} defeated! Victory!")
                    self._sfx("boss_defeated" if self.is_boss else "victory")
                    self._award_gold()
                    self._drop_loot()
                    return

            self._advance_to_enemy_turn()
            return

        # ── Damage skills ──
        if not self._check_hit(self.player, self.enemy):
            self._last_hit_info = {"target": "enemy", "damage": 0, "is_crit": False, "missed": True}
            self._add_log(f"{self.player.name}'s {skill['name']} missed!")
            self._sfx("miss")
            self._advance_to_enemy_turn()
            return

        total_atk = self.player.atk
        total_def = self.enemy.defn

        # Handle ignore_def_pct (Assassin Backstab)
        if skill.get("ignore_def_pct", 0) > 0:
            total_def = int(total_def * (1.0 - skill["ignore_def_pct"]))

        focused_bonus = self.player.consume_focused()

        # Death Mark: auto-crit if target is marked
        is_marked = self.player._death_marked
        is_crit = is_marked or random.random() < self.player.crit_chance
        if is_marked:
            self.player._death_marked = False
        crit_mult = 1.8 if is_crit else 1.0

        # Damage multiplier
        base_mult = skill["damage_mult"]

        # Execute: 2.5x if target < 40% HP
        if skill.get("special") == "execute":
            if self.enemy.current_hp < self.enemy.max_hp * 0.4:
                base_mult = 2.5

        # Death Wish: scale with missing HP
        if skill.get("special") == "death_wish":
            hp_pct = self.player.current_hp / self.player.max_hp if self.player.max_hp > 0 else 1.0
            base_mult = 1.8 + (1.0 - hp_pct) * 0.7  # 1.8 to 2.5

        # Retaliation bonus
        retaliation_bonus = 0
        if skill.get("special") == "retaliation":
            retaliation_bonus = int(self.player._damage_taken_last_turn * 0.5)

        # Multi-hit (Thousand Cuts)
        if skill.get("hits", 0) > 1:
            total_damage = 0
            total_crits = 0
            for hit_i in range(skill["hits"]):
                hit_crit = random.random() < self.player.crit_chance
                hit_mult = crit_mult if hit_crit else 1.0
                hit_dmg = max(1, int(total_atk * base_mult * hit_mult - total_def) + focused_bonus)
                actual = self.enemy.take_damage(hit_dmg)
                total_damage += actual
                if hit_crit:
                    total_crits += 1
                # Apply poison on each hit
                if self.enemy.is_alive and skill.get("status_effect"):
                    dur = skill.get("status_duration", 3)
                    self.enemy.add_status(skill["status_effect"], "debuff", dur, {})
                focused_bonus = 0  # Only first hit gets focus bonus
                if not self.enemy.is_alive:
                    break
            actual = total_damage
            is_crit = total_crits > 0
            self._last_hit_info = {"target": "enemy", "damage": actual, "is_crit": is_crit}
            self._add_log(f"{self.player.name} uses {skill['name']}! {skill['hits']} hits for {actual} damage!")
            self._sfx("skill")
            if is_crit:
                self._sfx("crit")
                self._shake_source = "player"
        else:
            damage = max(1, int(total_atk * base_mult * crit_mult - total_def) + focused_bonus + retaliation_bonus)
            actual = self.enemy.take_damage(damage)
            self._last_hit_info = {"target": "enemy", "damage": actual, "is_crit": is_crit}

            crit_tag = "CRITICAL! " if is_crit else ""
            focus_tag = f"Astral Focus bonus: +{focused_bonus}! " if focused_bonus > 0 else ""
            ret_tag = f"Retaliation bonus: +{retaliation_bonus}! " if retaliation_bonus > 0 else ""
            mark_tag = "DEATH MARK! " if is_marked else ""
            self._add_log(f"{self.player.name} uses {skill['name']}! {mark_tag}{crit_tag}{ret_tag}{focus_tag}Deals {actual} damage! (ATK:{total_atk} vs DEF:{total_def})")
            self._sfx("skill")
            if is_crit:
                self._sfx("crit")
                self._shake_source = "player"

        # ── Post-hit effects ──

        # Self-debuff
        if "self_effect" in skill:
            self.player.add_status(skill["self_effect"], "debuff", skill.get("self_effect_duration", 1), {})
            self._add_log(f"{self.player.name} is now {skill['self_effect'].capitalize()}!")

        # Self-debuff from data (Blood Rage: bleed)
        if skill.get("self_effect_data"):
            for eff_name, eff_info in skill["self_effect_data"].items():
                self.player.add_status(eff_name, "debuff", eff_info.get("duration", 2), {})
                self._add_log(f"{self.player.name} is now bleeding!")

        # HP cost (Annihilate)
        if skill.get("hp_cost_pct", 0) > 0:
            hp_cost = max(1, int(self.player.current_hp * skill["hp_cost_pct"]))
            self.player.current_hp = max(1, self.player.current_hp - hp_cost)
            self._add_log(f"{self.player.name} sacrifices {hp_cost} HP!")

        # Status effect on enemy
        if skill.get("status_effect") and self.enemy.is_alive:
            effect = skill["status_effect"]
            dur = skill.get("status_duration", 3)
            data = skill.get("status_data", None)
            self.enemy.add_status(effect, "debuff", dur, data or {})
            if self._ach_manager:
                if effect == "frozen":
                    self._ach_manager.inc("frozen_inflicted")
                elif effect == "bleed":
                    self._ach_manager.inc("bleed_applied")
            self._add_log(f"{self.enemy.name} is now afflicted with {effect}!")

        # Extra status (Envenom: bleed, Meteor: stun)
        if skill.get("extra_status") and self.enemy.is_alive:
            extra = skill["extra_status"]
            if random.random() < skill.get("extra_chance", 1.0):
                dur = skill.get("extra_duration", 3)
                self.enemy.add_status(extra, "debuff", dur, {})
                if self._ach_manager and extra == "bleed":
                    self._ach_manager.inc("bleed_applied")
                self._add_log(f"{self.enemy.name} is also afflicted with {extra}!")

        # Restore SP (Mana Siphon)
        if skill.get("restore_sp", 0) > 0:
            restored = min(skill["restore_sp"], self.player.max_sp - self.player.sp)
            self.player.sp += restored
            self._add_log(f"{self.player.name} restores {restored} SP!")

        # Permanent stat gain (Aegis Strike)
        if skill.get("perm_stat") and self.enemy.is_alive:
            for stat, value in skill["perm_stat"].items():
                if stat == "def":
                    self.player._base_def += value
            self._add_log(f"{self.player.name} gains +{skill['perm_stat'].get('def', 0)} permanent DEF!")

        # Death Mark — mark target for next attack
        if skill.get("special") == "death_mark" and self.enemy.is_alive:
            self.player._death_marked = True
            self._add_log(f"{self.enemy.name} is marked for death! Next attack is guaranteed crit.")

        # Conflagration — target takes +50% burn damage
        if skill.get("special") == "conflagration" and self.enemy.is_alive:
            self.enemy._conflagration_active = True
            self._add_log(f"{self.enemy.name} will take +50% damage from Burn!")

        if not self.player.is_alive:
            self.state = TurnState.DEFEAT
            self._add_log(f"{self.player.name} has fallen... Defeat.")
            return

        # Track damage taken for Retaliation
        self.player._damage_taken_last_turn = 0

        if not self.enemy.is_alive:
            self._mark_victory_progress()
            if self._ach_manager:
                self._ach_manager.inc("kills")
            self._award_xp()
            self.state = TurnState.VICTORY
            self._add_log(f"{self.enemy.name} defeated! Victory!")
            self._sfx("boss_defeated" if self.is_boss else "victory")
            self._award_gold()
            self._drop_loot()
            return

        self._advance_to_enemy_turn()

    def _award_gold(self):
        """Roll a random gold drop based on enemy type."""
        g_min = getattr(self.enemy, 'gold_min', 20)
        g_max = getattr(self.enemy, 'gold_max', 40)
        amount = random.randint(g_min, g_max)
        self.player.gold += amount
        self._gold_dropped = amount
        if self._ach_manager:
            self._ach_manager.inc("gold_earned", amount)
        self._sfx("loot_drop")
        self._add_log(f"Dropped {amount} gold!")

    def _drop_loot(self):
        """Generate a random loot drop and add it to the player's inventory or consumables."""
        item = LootGenerator.generate(floor=self.floor)
        # Boss guarantees Rare+ drop
        if self.is_boss:
            from item import Rarity
            while getattr(item, "rarity", None) == Rarity.COMMON:
                item = LootGenerator.generate(floor=self.floor)
        if isinstance(item, Consumable):
            merge_into_stack(self.player.consumables, item)
        else:
            self.player.inventory.append(item)
        if self._quest_manager:
            self._quest_manager.record_item_found(item)
        if self._ach_manager:
            self._ach_manager.inc("items_found")
            if getattr(item, "rarity", None) and item.rarity.name == "LEGENDARY":
                self._ach_manager.inc("legendaries_found")
        self._sfx("loot_drop")
        self._add_log(f"Dropped: {item}!")

    def _mark_victory_progress(self):
        if self._quest_manager:
            self._quest_manager.record_kill(self.enemy.name, is_boss=self.is_boss)
        if self._bestiary_manager:
            self._bestiary_manager.record_kill(self.enemy.name)

    def _award_xp(self):
        """Grant XP for defeating the enemy and track level-ups."""
        xp = getattr(self.enemy, "xp_reward", 0)
        self._xp_gained = xp
        self._level_ups = self.player.add_xp(xp)
        if xp > 0:
            self._add_log(f"Gained {xp} XP!")

    def _check_hit(self, attacker, target) -> bool:
        """Roll for hit. Returns True if attack lands."""
        hit_chance = max(0.05, min(0.95, attacker.accuracy - target.evasion))
        return random.random() < hit_chance

    def _sfx(self, name: str):
        """Play a sound effect if a SoundManager is attached."""
        if self._snd:
            self._snd.play(name)

    def _add_log(self, msg: str):
        """Append a message to the battle log."""
        self._log.append(msg)

    def _apply_blessings(self):
        """Apply run blessings from the dungeon to the player."""
        blessings = getattr(self.player, 'run_blessings', {})
        if blessings:
            if blessings.get("might"):
                self.player.add_status("blessing_might", "buff", 999, {})
            if blessings.get("fortitude"):
                self.player.add_status("blessing_fortitude", "buff", 999, {})
            if blessings.get("vitality"):
                self.player.add_status("regen", "buff", 999, {})

    def _advance_to_menu(self):
        """Transition to MENU_SELECT — process player status effects first."""
        self.player.tick_cooldowns()
        # Refresh available skills (new skills may unlock from level up)
        self._available_skills = SkillRegistry.get_available_skills(self.player)
        result = self.player.tick_status_effects()
        result["target"] = "player"
        self._last_status_tick = result

        for msg in result["messages"]:
            if msg[0] == "burn":
                self._add_log(f"Burn deals {msg[1]} damage to {self.player.name}!")
            elif msg[0] == "poison":
                self._add_log(f"Poison (stack {msg[2]}) deals {msg[1]} damage to {self.player.name}!")
            elif msg[0] == "bleed":
                self._add_log(f"Bleed (stack {msg[2]}) deals {msg[1]} damage to {self.player.name}!")
            elif msg[0] == "regen":
                self._add_log(f"Regen heals {self.player.name} for {msg[1]} HP!")
                if self._ach_manager:
                    self._ach_manager.inc("regen_healed", msg[1])

        if not self.player.is_alive:
            self.state = TurnState.DEFEAT
            self._add_log(f"{self.player.name} has fallen to status effects...")
            return

        if result["stunned"]:
            self._add_log(f"{self.player.name} is stunned! Turn skipped.")
            self._enemy_timer = 0
            self._enemy_turn_count += 1
            self.state = TurnState.ENEMY_TURN
            self._sfx("enemy_turn")
            self._add_log("--- Enemy's turn ---")
            self._last_hit_info = {"target": "player", "damage": 0, "is_crit": False, "status_stun": True}
            return

        self._player_confused = result["confused"]
        if self._player_confused:
            self._add_log(f"{self.player.name} is confused...")

        self.state = TurnState.MENU_SELECT
        self._add_log("--- Your turn: Choose an action ---")

    def _advance_to_enemy_turn(self):
        """Transition to ENEMY_TURN — process enemy status effects first."""
        self._enemy_timer = 0
        self._sfx("enemy_turn")

        result = self.enemy.tick_status_effects()
        result["target"] = "enemy"
        self._last_status_tick = result

        for msg in result["messages"]:
            if msg[0] == "burn":
                self._add_log(f"Burn deals {msg[1]} damage to {self.enemy.name}!")
            elif msg[0] == "poison":
                self._add_log(f"Poison (stack {msg[2]}) deals {msg[1]} damage to {self.enemy.name}!")
            elif msg[0] == "bleed":
                self._add_log(f"Bleed (stack {msg[2]}) deals {msg[1]} damage to {self.enemy.name}!")
            elif msg[0] == "regen":
                self._add_log(f"Regen heals {self.enemy.name} for {msg[1]} HP!")

        if not self.enemy.is_alive:
            self._mark_victory_progress()
            if self._ach_manager:
                self._ach_manager.inc("kills")
            self._award_xp()
            self.state = TurnState.VICTORY
            self._add_log(f"{self.enemy.name} defeated by status effects! Victory!")
            self._sfx("boss_defeated" if self.is_boss else "victory")
            self._award_gold()
            self._drop_loot()
            return

        if result["stunned"]:
            self._add_log(f"{self.enemy.name} is stunned! Turn skipped.")
            self._advance_to_menu()
            return

        self.state = TurnState.ENEMY_TURN
        self._add_log("--- Enemy's turn ---")

    def _execute_attack(self):
        """Execute a basic strike attack — supports crits, focused buff, and confused self-hit."""
        # Confused: 50% chance to hit self
        if getattr(self, '_player_confused', False) and random.random() < 0.5:
            self._player_confused = False
            damage = max(1, int(self.player.atk * 0.6))
            actual = self.player.take_damage(damage)
            self._last_hit_info = {"target": "player", "damage": actual, "is_crit": False, "confused_self": True}
            self._add_log(f"{self.player.name} is confused and attacks themselves! ({actual} damage)")
            self._sfx("player_hit")
            if not self.player.is_alive:
                self.state = TurnState.DEFEAT
                self._add_log(f"{self.player.name} has fallen... Defeat.")
            else:
                self._advance_to_enemy_turn()
            return
        self._player_confused = False

        if not self._check_hit(self.player, self.enemy):
            self._last_hit_info = {"target": "enemy", "damage": 0, "is_crit": False, "missed": True}
            self._add_log(f"{self.player.name}'s attack missed!")
            self._sfx("miss")
            self._advance_to_enemy_turn()
            return

        total_atk = self.player.atk
        total_def = self.enemy.defn

        focused_bonus = self.player.consume_focused()

        is_crit = random.random() < self.player.crit_chance
        crit_mult = 1.8 if is_crit else 1.0

        damage = max(1, int(total_atk * crit_mult - total_def) + focused_bonus)
        actual = self.enemy.take_damage(damage)
        self._last_hit_info = {"target": "enemy", "damage": actual, "is_crit": is_crit}
        self._sfx("attack")
        if is_crit:
            self._sfx("crit")
            if self._ach_manager:
                self._ach_manager.inc("crits")

        crit_tag = "CRITICAL! " if is_crit else ""
        focus_tag = f"Astral Focus bonus: +{focused_bonus}! " if focused_bonus > 0 else ""
        self._add_log(f"{self.player.name} uses Basic Strike! {crit_tag}{focus_tag}Deals {actual} damage! (ATK:{total_atk} vs DEF:{total_def})")
        self._shake_source = "player"

        if not self.enemy.is_alive:
            self._mark_victory_progress()
            if self._ach_manager:
                self._ach_manager.inc("kills")
            self._award_xp()
            self.state = TurnState.VICTORY
            self._add_log(f"{self.enemy.name} defeated! Victory!")
            self._sfx("boss_defeated" if self.is_boss else "victory")
            self._award_gold()
            self._drop_loot()
        else:
            self._advance_to_enemy_turn()

    def _enemy_attack(self):
        """Enemy attacks with signature moves per enemy type."""
        self._enemy_turn_count += 1

        # Boss Phase 2 trigger
        if self.is_boss and not self._boss_phase2_triggered:
            if self.enemy.current_hp <= self.enemy.max_hp * 0.5:
                self._boss_phase2_triggered = True
                self.enemy._base_atk = int(self.enemy._base_atk * 1.5)
                self._add_log("The Abyssal Warden roars and enters Phase 2!")
                self._sfx("boss_roar")

        # Confused enemy: 50% chance to hit self
        enemy_confused = self.enemy.has_status("confused")
        if enemy_confused and random.random() < 0.5:
            damage = max(1, int(self.enemy.atk * 0.6))
            actual = self.enemy.take_damage(damage)
            self._last_hit_info = {"target": "enemy", "damage": actual, "is_crit": False, "confused_self": True}
            self._add_log(f"{self.enemy.name} is confused and attacks itself! ({actual} damage)")
            self._sfx("player_hit")
            self._shake_source = "enemy"
            if self._ach_manager:
                self._ach_manager.unlock("confuse_self_hit")
            if not self.enemy.is_alive:
                self._mark_victory_progress()
                if self._ach_manager:
                    self._ach_manager.inc("kills")
                self._award_xp()
                self.state = TurnState.VICTORY
                self._add_log(f"{self.enemy.name} defeated itself in confusion! Victory!")
                self._sfx("boss_defeated" if self.is_boss else "victory")
                self._award_gold()
                self._drop_loot()
                return
            self._advance_to_menu()
            return

        ename = self.enemy.name

        # ── Slime: Split (every 4 turns) ──
        if ename == "Slime" and self._enemy_turn_count % 4 == 0:
            heal = min(15, self.enemy.max_hp - self.enemy.current_hp)
            self.enemy.current_hp += heal
            self.player.add_status("poison", "debuff", 3, {})
            self._add_log(f"Slime splits! Heals {heal} HP and poisons you!")
            self._sfx("buff")
            self._advance_to_menu()
            return

        # ── Wisp: Life Drain (every 3 turns) ──
        if ename == "Wisp" and self._enemy_turn_count % 3 == 0:
            if not self._check_hit(self.enemy, self.player):
                self._last_hit_info = {"target": "player", "damage": 0, "is_crit": False, "missed": True}
                self._add_log(f"{ename}'s Life Drain missed!")
                self._sfx("miss")
                self._advance_to_menu()
                return
            total_atk = self.enemy.atk
            total_def = self.player.defn
            damage = max(1, int(total_atk * 1.2 - total_def))
            actual = self.player.take_damage(damage)
            heal = int(actual * 0.5)
            heal = min(heal, self.enemy.max_hp - self.enemy.current_hp)
            self.enemy.current_hp += heal
            self._last_hit_info = {"target": "player", "damage": actual, "is_crit": False}
            self._sfx("player_hit")
            self._shake_source = "enemy"
            self._add_log(f"{ename} uses Life Drain! Deals {actual} damage and heals {heal} HP!")
            if not self.player.is_alive:
                self.state = TurnState.DEFEAT
                self._add_log(f"{self.player.name} has fallen... Defeat.")
            else:
                self._advance_to_menu()
            return

        # ── Determine hit and special moves ──
        # Stalker Backstab: ignores evasion
        is_stalker = ename == "Shadow Stalker"
        is_backstab = is_stalker and random.random() < 0.3
        if is_backstab:
            # Backstab ignores evasion
            pass  # handled below via check_hit override

        # Normal hit check (Stalker Backstab always hits)
        if not is_backstab and not self._check_hit(self.enemy, self.player):
            self._last_hit_info = {"target": "player", "damage": 0, "is_crit": False, "missed": True}
            self._add_log(f"{ename}'s attack missed!")
            self._sfx("miss")
            self._advance_to_menu()
            return

        total_atk = self.enemy.atk
        total_def = self.player.defn

        # Special move flags
        is_smash = ename == "Vanguard Brute" and self._enemy_turn_count % 3 == 0
        is_wrath = self.is_boss and self._enemy_turn_count % 3 == 0
        is_crush = ename == "Golem" and self._enemy_turn_count % 3 == 0
        is_fire = ename == "Dragon" and random.random() < 0.3
        is_hex = ename == "Cultist" and random.random() < 0.4

        # Damage multiplier
        mult = 1.0
        skill_name = ""
        if is_wrath:
            mult = 2.0
            skill_name = "Warden's Wrath! "
        elif is_crush:
            mult = 2.0
            skill_name = "Crush! "
        elif is_smash:
            mult = 1.5
            skill_name = "Brute Smash! "
        elif is_fire:
            mult = 1.3
            skill_name = "Fire Breath! "
        elif is_hex:
            mult = 1.0
            skill_name = "Dark Hex! "
        elif is_backstab:
            mult = 1.5
            skill_name = "Backstab! "

        effective_def = total_def // 2 if is_crush else total_def
        damage = max(1, int(total_atk * mult - effective_def))
        actual = self.player.take_damage(damage)
        self._last_hit_info = {"target": "player", "damage": actual, "is_crit": False}
        self._sfx("player_hit")
        self._shake_source = "enemy"
        self._add_log(f"{ename} uses {skill_name}Deals {actual} damage! (ATK:{total_atk} vs DEF:{total_def})")

        # Track damage taken for Retaliation skill
        self.player._damage_taken_last_turn += actual

        # Status application for special moves
        if self.player.is_alive:
            if is_fire:
                self.player.add_status("burn", "debuff", 3, {"potency": 6})
                self._add_log(f"{ename}'s Fire Breath burns you! (Burn 3 turns)")
            elif is_hex:
                self.player.add_status("confused", "debuff", 2, {})
                self._add_log(f"{ename}'s Dark Hex confuses you! (Confused 2 turns)")
            elif is_backstab:
                self.player.add_status("bleed", "debuff", 4, {})
                self._add_log(f"{ename}'s Backstab causes bleeding! (Bleed 4 turns)")
                if self._ach_manager:
                    self._ach_manager.inc("bleed_applied")
            elif is_smash and random.random() < 0.25:
                self.player.add_status("stun", "debuff", 1, {})
                self._add_log(f"{ename}'s Smash stuns you! (Stun)")

        if not self.player.is_alive:
            self.state = TurnState.DEFEAT
            self._add_log(f"{self.player.name} has fallen... Defeat.")
        else:
            self._advance_to_menu()

    def update(self, dt_ms: int):
        """Call every frame — handles enemy turn delay."""
        if self.state == TurnState.ENEMY_TURN:
            self._enemy_timer += dt_ms
            if self._enemy_timer >= self.ENEMY_DELAY_MS:
                self._enemy_attack()

    def get_recent_logs(self, count: int = 5) -> list:
        return self._log[-count:]

    def reset(self):
        """Reset both characters to full HP and restart combat."""
        self.player.current_hp = self.player.max_hp
        self.enemy.current_hp = self.enemy.max_hp
        self.player.sp = self.player.max_sp
        self.player.skill_cooldowns.clear()
        self.player.status_effects.clear()
        self._log.clear()
        self._enemy_timer = 0
        self.selected_index = 0
        self.sub_selected_index = 0
        self._gold_dropped = 0
        self._xp_gained = 0
        self._level_ups.clear()
        self.victory_phase = "rewards"
        self._last_hit_info = None
        self._last_status_tick = None
        self._shake_source = None
        self._enemy_turn_count = 0
        self._boss_phase2_triggered = False
        # Re-apply blessings before first turn
        self._apply_blessings()
        self._advance_to_menu()
