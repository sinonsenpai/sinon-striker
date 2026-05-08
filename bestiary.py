"""
Bestiary tracking for enemies encountered during a save.
"""

from __future__ import annotations

from dungeon import ENEMY_POOL


class BestiaryManager:
    """Tracks enemy encounters and kills."""

    def __init__(self):
        self.entries: dict[str, dict] = {}
        for key, data in ENEMY_POOL.items():
            self.entries[key] = {
                "key": key,
                "name": data["name"],
                "encountered": False,
                "kills": 0,
                "first_floor": None,
                "hp": data["hp"],
                "atk": data["atk"],
                "defn": data["defn"],
                "eva": data.get("eva", 0.0),
                "xp_reward": data.get("xp_reward", 0),
                "gold_min": data.get("gold_min", 0),
                "gold_max": data.get("gold_max", 0),
            }

    def encounter(self, enemy_key: str, floor: int | None = None):
        if enemy_key not in self.entries:
            return
        entry = self.entries[enemy_key]
        entry["encountered"] = True
        if entry["first_floor"] is None and floor is not None:
            entry["first_floor"] = floor

    def record_kill(self, enemy_key: str):
        if enemy_key in self.entries:
            self.entries[enemy_key]["kills"] += 1
            return
        for entry in self.entries.values():
            if entry["name"] == enemy_key:
                entry["kills"] += 1
                return

    def is_complete(self) -> bool:
        return all(entry["encountered"] for entry in self.entries.values())

    def encountered_count(self) -> int:
        return sum(1 for entry in self.entries.values() if entry["encountered"])

    def to_dict(self) -> dict:
        return {"entries": self.entries}

    def load_from_dict(self, data: dict | None):
        if not data:
            return
        entries = data.get("entries", {})
        for key, payload in entries.items():
            if key in self.entries:
                self.entries[key].update(payload)
