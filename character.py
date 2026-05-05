"""
Character module - base stats, SP system, status effects, crit system, equipment, and damage.
"""

import random
from item import ItemSlot, GEAR_SETS


class Character:
    """Base class representing any combatant in the battle."""

    def __init__(self, name: str, max_hp: int, atk: int, defn: int = 0):
        self.name = name
        self.max_hp = max_hp
        self.current_hp = max_hp
        self._base_atk = atk
        self._base_def = defn
        self.equipment = {"weapon": None, "armor": None}
        self.inventory: list = []
        self.consumables: list = []
        self.skill_cooldowns: dict[str, int] = {}
        self.gold: int = 0

        # SP system
        self.sp: int = 50
        self.max_sp: int = 50

        # Level / XP system
        self.level: int = 1
        self.xp: int = 0
        self.xp_to_next: int = 50
        self._max_level: int = 99

        # Status effects list of dicts: {name, type, turns_remaining, data}
        self.status_effects: list = []

    # ── Properties ─────────────────────────────────────────────────

    @property
    def base_atk(self) -> int:
        return self._base_atk

    @property
    def base_def(self) -> int:
        return self._base_def

    @property
    def atk(self) -> int:
        """Total ATK = base + weapon bonus + set bonuses."""
        weapon = self.equipment.get("weapon")
        bonus = weapon.stat_modifier.get("atk", 0) if weapon else 0
        for set_data in self.get_active_sets().values():
            bonus += set_data["bonus"].get("atk", 0)
        return self._base_atk + bonus

    @property
    def defn(self) -> int:
        """Total DEF = base + armor bonus + set bonuses."""
        armor = self.equipment.get("armor")
        bonus = armor.stat_modifier.get("def", 0) if armor else 0
        for set_data in self.get_active_sets().values():
            bonus += set_data["bonus"].get("def", 0)
        return self._base_def + bonus

    def get_active_sets(self) -> dict:
        """Return dict of set_name -> set_data for completed sets."""
        equipped_names = set()
        for item in self.equipment.values():
            if item:
                equipped_names.add(item.name)
        active = {}
        for set_name, set_data in GEAR_SETS.items():
            required = set(set_data["pieces"])
            if required.issubset(equipped_names):
                active[set_name] = set_data
        return active

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def crit_chance(self) -> float:
        """Fragile Focus: crit chance increases as HP decreases."""
        base = 0.05
        hp_pct = self.current_hp / self.max_hp if self.max_hp > 0 else 1.0
        bonus = (1.0 - hp_pct) * 0.30
        return base + bonus

    # ── Equipment ──────────────────────────────────────────────────

    def equip(self, item) -> None:
        slot_key = "weapon" if item.slot == ItemSlot.WEAPON else "armor"
        old_item = self.equipment[slot_key]
        self.equipment[slot_key] = item
        return old_item

    def unequip_slot(self, slot_key: str):
        old_item = self.equipment.get(slot_key)
        if old_item:
            self.equipment[slot_key] = None
            return old_item
        return None

    # ── Status effects ─────────────────────────────────────────────

    def has_status(self, name: str) -> bool:
        return any(e["name"] == name for e in self.status_effects)

    def add_status(self, name: str, type_: str, duration: int):
        """Add or refresh a status effect. Replaces existing effect of same name."""
        self.status_effects = [e for e in self.status_effects if e["name"] != name]
        self.status_effects.append({
            "name": name,
            "type": type_,
            "turns_remaining": duration,
        })

    def consume_focused(self) -> int:
        """If focused, remove it and return bonus damage based on missing HP."""
        for e in self.status_effects:
            if e["name"] == "focused":
                self.status_effects.remove(e)
                missing = self.max_hp - self.current_hp
                return int(missing * 0.5)
        return 0

    def tick_status_effects(self):
        """Decrement all status effect durations. Remove expired ones."""
        for e in self.status_effects[:]:
            e["turns_remaining"] -= 1
            if e["turns_remaining"] <= 0:
                self.status_effects.remove(e)

    def tick_cooldowns(self):
        """Decrement all skill cooldowns by 1 turn. Remove expired ones."""
        for skill in list(self.skill_cooldowns.keys()):
            self.skill_cooldowns[skill] -= 1
            if self.skill_cooldowns[skill] <= 0:
                del self.skill_cooldowns[skill]

    # ── XP / Leveling ──────────────────────────────────────────────

    def _calc_xp_to_next(self) -> int:
        return 50 + (self.level * 25)

    def add_xp(self, amount: int) -> list[dict]:
        """
        Add XP and process any level-ups.
        Returns a list of level-up info dicts for UI notifications.
        Each dict: {'level': int, 'hp_gain': int, 'atk_gain': int, 'def_gain': int}
        """
        level_ups = []
        if self.level >= self._max_level:
            return level_ups
        self.xp += amount
        while self.xp >= self.xp_to_next and self.level < self._max_level:
            self.xp -= self.xp_to_next
            self.level += 1
            self.max_hp += 10
            self.current_hp = self.max_hp
            self._base_atk += 2
            self._base_def += 1
            self.xp_to_next = self._calc_xp_to_next()
            level_ups.append({
                "level": self.level,
                "hp_gain": 10,
                "atk_gain": 2,
                "def_gain": 1,
            })
        # Cap XP at threshold (carry-over already handled above)
        if self.level >= self._max_level:
            self.xp = 0
            self.xp_to_next = 0
        return level_ups

    # ── Damage ─────────────────────────────────────────────────────

    def take_damage(self, raw_damage: int) -> int:
        """Apply damage. Vulnerable targets take 1.5x. Returns actual damage dealt."""
        if self.has_status("vulnerable"):
            raw_damage = int(raw_damage * 1.5)
        actual = max(0, raw_damage)
        old_hp = self.current_hp
        self.current_hp = max(0, self.current_hp - actual)
        return old_hp - self.current_hp


class Enemy(Character):
    """Simple enemy - identical stats to Character but semantically distinct."""

    def __init__(self, name: str, max_hp: int, atk: int, defn: int = 0, xp_reward: int = 0, gold_min: int = 20, gold_max: int = 40):
        super().__init__(name, max_hp, atk, defn)
        self.xp_reward = xp_reward
        self.gold_min = gold_min
        self.gold_max = gold_max