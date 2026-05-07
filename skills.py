"""
Skill Registry — class-based skill trees with level-gated unlocks.
"""

from enum import Enum


class SkillTree(Enum):
    VANGUARD = "Vanguard"
    BERSERKER = "Berserker"
    PYROMANCY = "Pyromancy"
    ARCANIST = "Arcanist"
    ASSASSIN = "Assassin"
    TRICKSTER = "Trickster"
    SURVIVAL = "Survival"


class PlayerClass(Enum):
    WARRIOR = "Warrior"
    MAGE = "Mage"
    ROGUE = "Rogue"


CLASS_TREES = {
    PlayerClass.WARRIOR: [SkillTree.VANGUARD, SkillTree.BERSERKER],
    PlayerClass.MAGE: [SkillTree.PYROMANCY, SkillTree.ARCANIST],
    PlayerClass.ROGUE: [SkillTree.ASSASSIN, SkillTree.TRICKSTER],
}

CLASS_BASE_STATS = {
    PlayerClass.WARRIOR: {"max_hp": 120, "atk": 18, "defn": 8, "max_sp": 50, "crit": 0.05, "eva": 0.05},
    PlayerClass.MAGE:    {"max_hp": 90,  "atk": 12, "defn": 4, "max_sp": 75, "crit": 0.05, "eva": 0.05},
    PlayerClass.ROGUE:   {"max_hp": 100, "atk": 15, "defn": 5, "max_sp": 55, "crit": 0.10, "eva": 0.10},
}


ALL_SKILLS = [
    # ── Survival (Neutral — all classes) ──────────────────────────
    {
        "name": "Mend",
        "tree": SkillTree.SURVIVAL,
        "tier": 1,
        "unlock_level": 1,
        "cost": 12,
        "damage_mult": 0,
        "desc": "Heal self 25% max HP",
        "heal_pct": 0.25,
    },
    {
        "name": "Iron Will",
        "tree": SkillTree.SURVIVAL,
        "tier": 2,
        "unlock_level": 5,
        "cost": 15,
        "damage_mult": 0,
        "desc": "+30% DEF for 3 turns",
        "buff": "iron_will",
        "buff_duration": 3,
    },
    {
        "name": "Adrenaline",
        "tree": SkillTree.SURVIVAL,
        "tier": 3,
        "unlock_level": 10,
        "cost": 20,
        "damage_mult": 0,
        "desc": "+25% ATK for 3 turns, self Vulnerable 1 turn",
        "buff": "adrenaline",
        "buff_duration": 3,
        "self_effect": "vulnerable",
        "self_effect_duration": 1,
    },
    {
        "name": "Last Stand",
        "tree": SkillTree.SURVIVAL,
        "tier": 4,
        "unlock_level": 15,
        "cost": 25,
        "damage_mult": 0,
        "desc": "Damage = missing HP × 0.6, cannot drop below 1 HP",
        "special": "last_stand",
    },

    # ── Vanguard (Warrior tank) ────────────────────────────────────
    {
        "name": "Shield Bash",
        "tree": SkillTree.VANGUARD,
        "tier": 1,
        "unlock_level": 1,
        "cost": 15,
        "damage_mult": 1.4,
        "desc": "1.4x ATK  |  Stun 1 turn",
        "status_effect": "stun",
        "status_duration": 1,
    },
    {
        "name": "Fortify",
        "tree": SkillTree.VANGUARD,
        "tier": 2,
        "unlock_level": 5,
        "cost": 18,
        "damage_mult": 0,
        "desc": "+50% DEF for 2 turns",
        "buff": "fortify",
        "buff_duration": 2,
    },
    {
        "name": "Retaliation",
        "tree": SkillTree.VANGUARD,
        "tier": 3,
        "unlock_level": 10,
        "cost": 22,
        "damage_mult": 1.0,
        "desc": "1.0x ATK + bonus = dmg taken last turn × 0.5",
        "special": "retaliation",
    },
    {
        "name": "Aegis Strike",
        "tree": SkillTree.VANGUARD,
        "tier": 4,
        "unlock_level": 15,
        "cost": 30,
        "damage_mult": 2.0,
        "desc": "2.0x ATK, gain DEF+10 permanently",
        "perm_stat": {"def": 10},
    },

    # ── Berserker (Warrior damage) ─────────────────────────────────
    {
        "name": "Blood Rage",
        "tree": SkillTree.BERSERKER,
        "tier": 1,
        "unlock_level": 1,
        "cost": 10,
        "damage_mult": 1.5,
        "desc": "1.5x ATK, self Bleed 2 turns",
        "self_effect_data": {"bleed": {"duration": 2}},
    },
    {
        "name": "Reckless Swing",
        "tree": SkillTree.BERSERKER,
        "tier": 2,
        "unlock_level": 5,
        "cost": 18,
        "damage_mult": 2.2,
        "desc": "2.2x ATK, self Vulnerable 2 turns",
        "self_effect": "vulnerable",
        "self_effect_duration": 2,
    },
    {
        "name": "Death Wish",
        "tree": SkillTree.BERSERKER,
        "tier": 3,
        "unlock_level": 10,
        "cost": 20,
        "damage_mult": 1.8,
        "desc": "1.8x-2.5x ATK (scales with missing HP)",
        "special": "death_wish",
    },
    {
        "name": "Annihilate",
        "tree": SkillTree.BERSERKER,
        "tier": 4,
        "unlock_level": 15,
        "cost": 35,
        "damage_mult": 3.0,
        "desc": "3.0x ATK, costs 15% current HP",
        "hp_cost_pct": 0.15,
    },

    # ── Pyromancy (Mage fire/DOT) ──────────────────────────────────
    {
        "name": "Fireball",
        "tree": SkillTree.PYROMANCY,
        "tier": 1,
        "unlock_level": 1,
        "cost": 15,
        "damage_mult": 1.5,
        "desc": "1.5x ATK  |  Burn 3 turns (8 dmg)",
        "status_effect": "burn",
        "status_duration": 3,
        "status_data": {"potency": 8},
    },
    {
        "name": "Inferno",
        "tree": SkillTree.PYROMANCY,
        "tier": 2,
        "unlock_level": 5,
        "cost": 22,
        "damage_mult": 1.0,
        "desc": "1.0x ATK  |  Burn 5 turns (10 dmg)",
        "status_effect": "burn",
        "status_duration": 5,
        "status_data": {"potency": 10},
    },
    {
        "name": "Conflagration",
        "tree": SkillTree.PYROMANCY,
        "tier": 3,
        "unlock_level": 10,
        "cost": 28,
        "damage_mult": 2.0,
        "desc": "2.0x ATK, target +50% burn dmg 3 turns",
        "status_effect": "burn",
        "status_duration": 3,
        "status_data": {"potency": 8},
        "special": "conflagration",
    },
    {
        "name": "Meteor",
        "tree": SkillTree.PYROMANCY,
        "tier": 4,
        "unlock_level": 15,
        "cost": 35,
        "damage_mult": 2.5,
        "desc": "2.5x ATK, Burn 4 turns (12 dmg), 30% Stun",
        "status_effect": "burn",
        "status_duration": 4,
        "status_data": {"potency": 12},
        "extra_status": "stun",
        "extra_chance": 0.30,
    },

    # ── Arcanist (Mage control) ────────────────────────────────────
    {
        "name": "Frost Bolt",
        "tree": SkillTree.ARCANIST,
        "tier": 1,
        "unlock_level": 1,
        "cost": 14,
        "damage_mult": 1.3,
        "desc": "1.3x ATK  |  Frozen 1 turn",
        "status_effect": "frozen",
        "status_duration": 1,
    },
    {
        "name": "Hex",
        "tree": SkillTree.ARCANIST,
        "tier": 2,
        "unlock_level": 5,
        "cost": 18,
        "damage_mult": 0.8,
        "desc": "0.8x ATK  |  Confused 3 turns",
        "status_effect": "confused",
        "status_duration": 3,
    },
    {
        "name": "Mana Siphon",
        "tree": SkillTree.ARCANIST,
        "tier": 3,
        "unlock_level": 10,
        "cost": 20,
        "damage_mult": 1.0,
        "desc": "1.0x ATK, restore 10 SP on hit",
        "restore_sp": 10,
    },
    {
        "name": "Time Warp",
        "tree": SkillTree.ARCANIST,
        "tier": 4,
        "unlock_level": 15,
        "cost": 30,
        "damage_mult": 1.8,
        "desc": "1.8x ATK  |  Stun 2 turns",
        "status_effect": "stun",
        "status_duration": 2,
    },

    # ── Assassin (Rogue burst) ─────────────────────────────────────
    {
        "name": "Backstab",
        "tree": SkillTree.ASSASSIN,
        "tier": 1,
        "unlock_level": 1,
        "cost": 15,
        "damage_mult": 1.8,
        "desc": "1.8x ATK, ignores 50% DEF",
        "ignore_def_pct": 0.5,
    },
    {
        "name": "Expose Weakness",
        "tree": SkillTree.ASSASSIN,
        "tier": 2,
        "unlock_level": 5,
        "cost": 18,
        "damage_mult": 1.0,
        "desc": "1.0x ATK  |  Target Vulnerable 3 turns",
        "status_effect": "vulnerable",
        "status_duration": 3,
    },
    {
        "name": "Execute",
        "tree": SkillTree.ASSASSIN,
        "tier": 3,
        "unlock_level": 10,
        "cost": 25,
        "damage_mult": 1.2,
        "desc": "2.5x ATK if target <40% HP, else 1.2x",
        "special": "execute",
    },
    {
        "name": "Death Mark",
        "tree": SkillTree.ASSASSIN,
        "tier": 4,
        "unlock_level": 15,
        "cost": 30,
        "damage_mult": 1.5,
        "desc": "1.5x ATK, mark target — next attack is auto-crit",
        "special": "death_mark",
    },

    # ── Trickster (Rogue poison/evasion) ───────────────────────────
    {
        "name": "Poison Dart",
        "tree": SkillTree.TRICKSTER,
        "tier": 1,
        "unlock_level": 1,
        "cost": 12,
        "damage_mult": 1.2,
        "desc": "1.2x ATK  |  Poison 3 turns (stacks)",
        "status_effect": "poison",
        "status_duration": 3,
    },
    {
        "name": "Smoke Bomb",
        "tree": SkillTree.TRICKSTER,
        "tier": 2,
        "unlock_level": 5,
        "cost": 16,
        "damage_mult": 0.5,
        "desc": "0.5x ATK  |  +25% evasion for 3 turns",
        "buff": "smoke_screen",
        "buff_duration": 3,
    },
    {
        "name": "Envenom",
        "tree": SkillTree.TRICKSTER,
        "tier": 3,
        "unlock_level": 10,
        "cost": 22,
        "damage_mult": 1.5,
        "desc": "1.5x ATK, Poison 4 turns (stacks), Bleed 2 turns",
        "status_effect": "poison",
        "status_duration": 4,
        "extra_status": "bleed",
        "extra_duration": 2,
    },
    {
        "name": "Thousand Cuts",
        "tree": SkillTree.TRICKSTER,
        "tier": 4,
        "unlock_level": 15,
        "cost": 28,
        "damage_mult": 0.5,
        "desc": "0.5x ATK × 4 hits, each hit Poison stack",
        "hits": 4,
        "status_effect": "poison",
        "status_duration": 3,
    },
]


class SkillRegistry:
    """Central registry for all skills with class/tree/level gating."""

    @staticmethod
    def get_available_skills(player) -> list:
        """Return skill defs available to this player based on class, tree, and level."""
        available = []
        for skill in ALL_SKILLS:
            tree = skill["tree"]
            if tree != SkillTree.SURVIVAL:
                # Class-specific: must match player's chosen tree
                if not hasattr(player, 'chosen_tree') or player.chosen_tree is None:
                    continue
                if tree != player.chosen_tree:
                    continue
            # Level gate
            if player.level < skill.get("unlock_level", 1):
                continue
            available.append(skill)
        return available

    @staticmethod
    def get_skill_by_name(name: str) -> dict | None:
        for skill in ALL_SKILLS:
            if skill["name"] == name:
                return skill
        return None

    @staticmethod
    def get_trees_for_class(player_class: PlayerClass) -> list:
        return CLASS_TREES.get(player_class, [])

    @staticmethod
    def get_base_stats(player_class: PlayerClass) -> dict:
        return dict(CLASS_BASE_STATS.get(player_class, CLASS_BASE_STATS[PlayerClass.WARRIOR]))
