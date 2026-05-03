"""
Item module - base item class, Weapon/Armor/Consumable subclasses, and LootGenerator.
"""

import random
from typing import Union
from enum import Enum, auto


class Rarity(Enum):
    COMMON = auto()
    RARE = auto()
    EPIC = auto()
    LEGENDARY = auto()


class ItemSlot(Enum):
    WEAPON = auto()
    ARMOR = auto()


RARITY_WEIGHTS = {
    Rarity.COMMON: 70,
    Rarity.RARE: 20,
    Rarity.EPIC: 9,
    Rarity.LEGENDARY: 1,
}

RARITY_STAT_MULTIPLIER = {
    Rarity.COMMON: 1,
    Rarity.RARE: 2,
    Rarity.EPIC: 4,
    Rarity.LEGENDARY: 8,
}

RARITY_PREFIX = {
    Rarity.COMMON: "",
    Rarity.RARE: "Fine ",
    Rarity.EPIC: "Grand ",
    Rarity.LEGENDARY: "Star-",
}

WEAPON_NAMES = [
    "Blade",
    "Sword",
    "Axe",
    "Mace",
    "Dagger",
    "Claymore",
    "Scimitar",
    "Flail",
]

ARMOR_NAMES = [
    "Chainmail",
    "Plate",
    "Leather",
    "Brigandine",
    "Scale",
    "Robe",
    "Hauberk",
    "Lamellar",
]

WEAPON_BASE_ATK = 3
ARMOR_BASE_DEF = 2
POTION_BASE_HP = 15


class Item:
    """Base class for all equippable items."""

    def __init__(self, name: str, rarity: Rarity, slot: ItemSlot, stat_modifier: dict):
        self.name = name
        self.rarity = rarity
        self.slot = slot
        self.stat_modifier = stat_modifier

    def __str__(self) -> str:
        stat_parts = []
        for stat, value in self.stat_modifier.items():
            stat_label = stat.upper()
            stat_parts.append(f"+{value} {stat_label}")
        stats_str = " ".join(stat_parts)
        return f"[{self.rarity.name}] {self.name} ({stats_str})"


class Weapon(Item):
    """A weapon item that provides ATK bonus."""

    def __init__(self, name: str, rarity: Rarity, atk: int):
        stat_modifier = {"atk": atk}
        super().__init__(name, rarity, ItemSlot.WEAPON, stat_modifier)
        self.atk = atk


class Armor(Item):
    """An armor item that provides DEF bonus."""

    def __init__(self, name: str, rarity: Rarity, defense: int):
        stat_modifier = {"def": defense}
        super().__init__(name, rarity, ItemSlot.ARMOR, stat_modifier)
        self.defense = defense


class Consumable:
    """A consumable item usable once in battle (not equippable)."""

    def __init__(self, name: str, rarity: Rarity, hp_restore: int = 0):
        self.name = name
        self.rarity = rarity
        self.hp_restore = hp_restore
        self.quantity = 1

    def __str__(self) -> str:
        qty = f" x{self.quantity}" if self.quantity > 1 else ""
        return f"[{self.rarity.name}] {self.name}{qty} (+{self.hp_restore} HP)"


def merge_into_stack(consumables: list, new_item: 'Consumable'):
    """Add a consumable to the list, merging into existing stacks by name."""
    for c in consumables:
        if c.name == new_item.name:
            c.quantity += 1
            return
    consumables.append(new_item)


def pop_from_stack(consumables: list, index: int):
    """Remove one from a consumable stack. Returns the item if stack empty, else None."""
    item = consumables[index]
    if item.quantity <= 1:
        return consumables.pop(index)
    item.quantity -= 1
    return None


class LootGenerator:
    """Generates random loot items based on a rarity table."""

    @staticmethod
    def _roll_rarity() -> Rarity:
        """Roll for item rarity using weighted probabilities."""
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        return random.choices(rarities, weights=weights, k=1)[0]

    @staticmethod
    def generate() -> Union[Item, Consumable]:
        """Generate a random Weapon, Armor, or Consumable with rarity-scaled stats."""
        rarity = LootGenerator._roll_rarity()
        multiplier = RARITY_STAT_MULTIPLIER[rarity]

        # 60% weapon, 28% armor, 12% consumable
        roll = random.random()
        if roll < 0.60:
            name = RARITY_PREFIX[rarity] + random.choice(WEAPON_NAMES)
            atk = WEAPON_BASE_ATK * multiplier
            return Weapon(name, rarity, atk)
        elif roll < 0.88:
            name = RARITY_PREFIX[rarity] + random.choice(ARMOR_NAMES)
            defense = ARMOR_BASE_DEF * multiplier
            return Armor(name, rarity, defense)
        else:
            hp_restore = POTION_BASE_HP * multiplier
            name = RARITY_PREFIX[rarity] + "Potion"
            return Consumable(name, rarity, hp_restore)