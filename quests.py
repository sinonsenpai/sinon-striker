"""
Simple quest board system for hub progression.
"""

from __future__ import annotations

import random

from dungeon import ENEMY_POOL
from item import Rarity, LootGenerator


QUEST_TYPES = ("hunt", "collect", "reach", "boss")


class QuestManager:
    """Tracks active quests and handles rewards."""

    def __init__(self):
        self.active_quests: list[dict] = []
        self.completed_quests: int = 0
        self._next_id: int = 1
        while len(self.active_quests) < 3:
            self.active_quests.append(self._generate_quest())

    def _generate_quest(self) -> dict:
        qtype = random.choice(QUEST_TYPES)
        quest = {"id": self._next_id, "type": qtype, "progress": 0, "completed": False, "claimed": False}
        self._next_id += 1

        if qtype == "hunt":
            key, data = random.choice(list(ENEMY_POOL.items()))
            count = random.randint(3, 8)
            quest.update({
                "enemy_key": key,
                "enemy_name": data["name"],
                "target": count,
                "reward_kind": "gold",
                "reward_value": 40 + count * 15,
                "description": f"Defeat {count} {data['name']}(s).",
            })
        elif qtype == "collect":
            rarity = random.choice([Rarity.COMMON, Rarity.RARE, Rarity.EPIC])
            count = random.randint(2, 5)
            quest.update({
                "rarity": rarity.name,
                "target": count,
                "reward_kind": "item",
                "reward_value": 1,
                "description": f"Find {count} {rarity.name.lower()} or better items.",
            })
        elif qtype == "reach":
            floor = random.randint(2, 10)
            quest.update({
                "target": floor,
                "reward_kind": "xp",
                "reward_value": 50 + floor * 20,
                "description": f"Reach floor {floor}.",
            })
        else:
            quest.update({
                "target": 1,
                "reward_kind": "legendary_item",
                "reward_value": 1,
                "description": "Defeat a boss.",
            })
        return quest

    def _check_complete(self, quest: dict):
        if quest["type"] in ("hunt", "collect"):
            quest["completed"] = quest["progress"] >= quest["target"]
        elif quest["type"] == "reach":
            quest["completed"] = quest["progress"] >= quest["target"]
        elif quest["type"] == "boss":
            quest["completed"] = quest["progress"] >= 1

    def record_kill(self, enemy_key: str, is_boss: bool = False):
        for quest in self.active_quests:
            if quest["completed"]:
                continue
            if quest["type"] == "hunt" and (quest.get("enemy_key") == enemy_key or quest.get("enemy_name") == enemy_key):
                quest["progress"] += 1
                self._check_complete(quest)
            elif quest["type"] == "boss" and is_boss:
                quest["progress"] = 1
                self._check_complete(quest)

    def record_item_found(self, item):
        if item is None:
            return
        for quest in self.active_quests:
            if quest["type"] != "collect" or quest["completed"]:
                continue
            needed = Rarity[quest["rarity"]]
            if item.rarity.value >= needed.value:
                quest["progress"] += 1
                self._check_complete(quest)

    def record_floor(self, floor: int):
        for quest in self.active_quests:
            if quest["type"] != "reach" or quest["completed"]:
                continue
            if floor >= quest["target"]:
                quest["progress"] = floor
                self._check_complete(quest)

    def claim_quest(self, index: int, player) -> dict | None:
        if index < 0 or index >= len(self.active_quests):
            return None
        quest = self.active_quests[index]
        if not quest["completed"] or quest["claimed"]:
            return None

        reward = {"kind": quest["reward_kind"], "value": quest["reward_value"], "description": quest["description"]}
        if quest["reward_kind"] == "gold":
            player.gold += quest["reward_value"]
        elif quest["reward_kind"] == "xp":
            player.add_xp(quest["reward_value"])
        elif quest["reward_kind"] == "item":
            item = LootGenerator.generate(floor=max(1, player.level))
            if getattr(item, "rarity", None) and item.rarity.value < Rarity.RARE.value:
                item = LootGenerator.generate(floor=max(4, player.level))
            if hasattr(item, "quantity"):
                player.consumables.append(item)
            else:
                player.inventory.append(item)
            reward["item"] = item
        else:
            item = LootGenerator.generate(floor=max(6, player.level))
            while getattr(item, "rarity", None) != Rarity.LEGENDARY:
                item = LootGenerator.generate(floor=max(6, player.level))
            if hasattr(item, "quantity"):
                player.consumables.append(item)
            else:
                player.inventory.append(item)
            reward["item"] = item

        quest["claimed"] = True
        self.completed_quests += 1
        self.active_quests.pop(index)
        while len(self.active_quests) < 3:
            self.active_quests.append(self._generate_quest())
        return reward

    def to_dict(self) -> dict:
        return {
            "active_quests": self.active_quests,
            "completed_quests": self.completed_quests,
            "next_id": self._next_id,
        }

    def load_from_dict(self, data: dict | None):
        if not data:
            return
        self.active_quests = list(data.get("active_quests", []))
        self.completed_quests = data.get("completed_quests", 0)
        self._next_id = data.get("next_id", self._next_id)
        while len(self.active_quests) < 3:
            self.active_quests.append(self._generate_quest())
