"""
Save Manager — handles player progress persistence via JSON.
"""

import json
import os

from item import Weapon, Armor, Consumable, Rarity, merge_into_stack

SAVE_FILE = "save_data.json"
SETTINGS_FILE = "settings.json"


def save_game(player, snd=None, ach_manager=None):
    """Save all player progress to JSON."""
    if ach_manager is not None:
        ach_manager.save()
    data = {
        "gold": player.gold,
        "level": player.level,
        "xp": player.xp,
        "xp_to_next": player.xp_to_next,
        "base_atk": player._base_atk,
        "base_def": player._base_def,
        "max_hp": player.max_hp,
        "equipment": {
            "weapon": serialize_item(player.equipment.get("weapon")),
            "armor": serialize_item(player.equipment.get("armor")),
        },
        "inventory": [serialize_item(item) for item in player.inventory],
        "consumables": [serialize_consumable(c) for c in player.consumables],
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_game(player):
    """Load saved progress into the player object. Returns True if save existed."""
    if not os.path.exists(SAVE_FILE):
        return False
    with open(SAVE_FILE) as f:
        data = json.load(f)

    player.gold = data.get("gold", 0)
    player.level = data.get("level", 1)
    player.xp = data.get("xp", 0)
    player.xp_to_next = data.get("xp_to_next", 50)
    player._base_atk = data.get("base_atk", 15)
    player._base_def = data.get("base_def", 5)
    player.max_hp = data.get("max_hp", 100)
    player.current_hp = player.max_hp

    # Equipment
    for slot in ("weapon", "armor"):
        item_data = data.get("equipment", {}).get(slot)
        player.equipment[slot] = deserialize_item(item_data) if item_data else None

    # Inventory
    player.inventory = [deserialize_item(i) for i in data.get("inventory", []) if i]

    # Consumables
    player.consumables = []
    for c in data.get("consumables", []):
        item = deserialize_consumable(c)
        if item:
            merge_into_stack(player.consumables, item)

    return True


def serialize_item(item):
    if item is None:
        return None
    return {
        "type": "weapon" if isinstance(item, Weapon) else "armor",
        "name": item.name,
        "rarity": item.rarity.name,
        "atk": getattr(item, "atk", 0),
        "defense": getattr(item, "defense", 0),
        "set_name": getattr(item, "set_name", None),
    }


def deserialize_item(data):
    if data is None:
        return None
    rarity = Rarity[data["rarity"]]
    if data["type"] == "weapon":
        item = Weapon(data["name"], rarity, data["atk"])
    else:
        item = Armor(data["name"], rarity, data["defense"])
    if data.get("set_name"):
        item.set_name = data["set_name"]
    return item


def serialize_consumable(c):
    return {
        "name": c.name,
        "rarity": c.rarity.name,
        "hp_restore": c.hp_restore,
        "quantity": c.quantity,
    }


def deserialize_consumable(data):
    rarity = Rarity[data["rarity"]]
    item = Consumable(data["name"], rarity, data["hp_restore"])
    item.quantity = data.get("quantity", 1)
    return item


def save_settings(sfx_volume: float, music_volume: float):
    """Write audio settings to JSON."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "sfx_volume": sfx_volume,
                "music_volume": music_volume,
            }, f)
    except Exception:
        pass


def load_settings() -> dict:
    """Return saved audio settings, or defaults if none exist."""
    if not os.path.exists(SETTINGS_FILE):
        return {"sfx_volume": 0.3, "music_volume": 0.25}
    with open(SETTINGS_FILE) as f:
        return json.load(f)
