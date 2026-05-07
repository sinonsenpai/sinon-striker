"""
Save Manager — handles player progress persistence via JSON.
"""

import json
import os
import tempfile

from item import Weapon, Armor, Consumable, Rarity, merge_into_stack
from skills import PlayerClass, SkillTree

SAVE_FILE = "save_data.json"
SETTINGS_FILE = "settings.json"


def save_game(player, snd=None, ach_manager=None, current_floor: int = 1, resume_context: dict | None = None):
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
        "current_hp": player.current_hp,
        "max_sp": player.max_sp,
        "sp": player.sp,
        "base_crit": player._base_crit,
        "base_eva": player._eva,
        "status_effects": player.status_effects,
        "skill_cooldowns": player.skill_cooldowns,
        "death_marked": getattr(player, "_death_marked", False),
        "damage_taken_last_turn": getattr(player, "_damage_taken_last_turn", 0),
        "conflagration_active": getattr(player, "_conflagration_active", False),
        "current_floor": current_floor,
        "player_class": player.player_class.value if player.player_class else None,
        "chosen_tree": player.chosen_tree.value if player.chosen_tree else None,
        "equipment": {
            "weapon": serialize_item(player.equipment.get("weapon")),
            "armor": serialize_item(player.equipment.get("armor")),
        },
        "inventory": [serialize_item(item) for item in player.inventory],
        "consumables": [serialize_consumable(c) for c in player.consumables],
        "resume_context": resume_context or {"mode": "hub"},
    }
    directory = os.path.dirname(os.path.abspath(SAVE_FILE)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="save_data.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, SAVE_FILE)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_game(player):
    """Load saved progress into the player object. Returns (loaded, current_floor, resume_context)."""
    if not os.path.exists(SAVE_FILE):
        return False, 1, {"mode": "hub"}
    try:
        with open(SAVE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        broken_name = f"{SAVE_FILE}.corrupt"
        try:
            if os.path.exists(broken_name):
                os.remove(broken_name)
            os.replace(SAVE_FILE, broken_name)
        except OSError:
            pass
        return False, 1, {"mode": "hub"}

    player.gold = data.get("gold", 0)
    player.level = data.get("level", 1)
    player.xp = data.get("xp", 0)
    player.xp_to_next = data.get("xp_to_next", 50)
    player._base_atk = data.get("base_atk", 15)
    player._base_def = data.get("base_def", 5)
    player.max_hp = data.get("max_hp", 100)
    player.current_hp = data.get("current_hp", player.max_hp)
    player.max_sp = data.get("max_sp", getattr(player, "max_sp", 50))
    player.sp = min(data.get("sp", player.max_sp), player.max_sp)
    player._base_crit = data.get("base_crit", getattr(player, "_base_crit", 0.05))
    player._eva = data.get("base_eva", getattr(player, "_eva", 0.05))
    player.status_effects = data.get("status_effects", [])
    player.skill_cooldowns = data.get("skill_cooldowns", {})
    player._death_marked = data.get("death_marked", False)
    player._damage_taken_last_turn = data.get("damage_taken_last_turn", 0)
    player._conflagration_active = data.get("conflagration_active", False)

    # Class / Tree (backward compatible: default to Warrior + Berserker)
    pc_name = data.get("player_class")
    needs_default_class_stats = False
    if pc_name:
        try:
            player.player_class = PlayerClass(pc_name)
        except ValueError:
            player.player_class = PlayerClass.WARRIOR
            needs_default_class_stats = True
    else:
        player.player_class = PlayerClass.WARRIOR
        needs_default_class_stats = True

    if needs_default_class_stats:
        player.apply_class_stats(PlayerClass.WARRIOR)

    tree_name = data.get("chosen_tree")
    if tree_name:
        try:
            player.chosen_tree = SkillTree(tree_name)
        except ValueError:
            player.chosen_tree = SkillTree.BERSERKER
    else:
        player.chosen_tree = SkillTree.BERSERKER

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

    return True, data.get("current_floor", 1), data.get("resume_context", {"mode": "hub"})


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


def save_settings(sfx_volume: float, music_volume: float, muted: bool = False):
    """Write audio settings to JSON."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "sfx_volume": sfx_volume,
                "music_volume": music_volume,
                "muted": muted,
            }, f)
    except Exception:
        pass


def load_settings() -> dict:
    """Return saved audio settings, or defaults if none exist."""
    if not os.path.exists(SETTINGS_FILE):
        return {"sfx_volume": 0.3, "music_volume": 0.25, "muted": False}
    with open(SETTINGS_FILE) as f:
        return json.load(f)
