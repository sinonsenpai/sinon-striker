"""
Dungeon module — room types, generation, and dungeon run state.
"""

import random
from enum import Enum, auto


class RoomType(Enum):
    COMBAT = auto()
    ELITE = auto()
    LOOT = auto()
    REST = auto()
    SHOP = auto()
    EXIT = auto()
    BOSS = auto()
    SHRINE = auto()
    TRAP = auto()


ROOM_ICONS = {
    RoomType.COMBAT: "combat",
    RoomType.ELITE: "elite",
    RoomType.LOOT: "loot",
    RoomType.REST: "rest",
    RoomType.SHOP: "shop",
    RoomType.EXIT: "exit",
    RoomType.BOSS: "boss",
    RoomType.SHRINE: "shrine",
    RoomType.TRAP: "trap",
}

ROOM_COLORS = {
    RoomType.COMBAT: (220, 50, 60),
    RoomType.ELITE: (180, 60, 255),
    RoomType.LOOT: (255, 215, 0),
    RoomType.REST: (50, 210, 100),
    RoomType.SHOP: (0, 240, 255),
    RoomType.EXIT: (255, 215, 0),
    RoomType.BOSS: (255, 60, 60),
    RoomType.SHRINE: (255, 200, 100),
    RoomType.TRAP: (200, 50, 50),
}

ROOM_LABELS = {
    RoomType.COMBAT: "Combat",
    RoomType.ELITE: "Elite",
    RoomType.LOOT: "Loot",
    RoomType.REST: "Rest",
    RoomType.SHOP: "Shop",
    RoomType.EXIT: "Exit",
    RoomType.BOSS: "Boss",
    RoomType.SHRINE: "Shrine",
    RoomType.TRAP: "Trap",
}

FLAVOR = {
    RoomType.COMBAT: [
        "A den of slimes blocks the path.",
        "Shadows move in the corridor ahead.",
        "The stench of danger fills the air.",
    ],
    RoomType.ELITE: [
        "A powerful presence lurks within...",
        "The air crackles with danger.",
        "Heavy footsteps echo from the darkness.",
    ],
    RoomType.LOOT: [
        "A treasure chamber gleams ahead.",
        "Something shiny catches your eye.",
        "You spot a dusty chest in the corner.",
    ],
    RoomType.REST: [
        "A warm glow emanates from the doorway.",
        "The air feels calm here.",
        "A sanctuary hidden within the depths.",
    ],
    RoomType.SHOP: [
        "A traveling merchant has set up camp.",
        "You hear coins clinking.",
        "A lantern flickers over wares for sale.",
    ],
    RoomType.EXIT: [
        "The exit is near. Escape with your spoils!",
        "A way out shimmers in the distance.",
        "Daylight peeks through a crack ahead.",
    ],
    RoomType.BOSS: [
        "A menacing presence looms ahead...",
        "The ground shakes with mighty footsteps.",
        "An aura of pure dread emanates from beyond.",
    ],
    RoomType.SHRINE: [
        "An ancient shrine hums with power.",
        "A divine light bathes the chamber.",
        "Offerings left by those before you catch your eye.",
    ],
    RoomType.TRAP: [
        "The floor tiles look suspicious...",
        "You hear a faint click beneath your feet.",
        "Tripwire glints in the torchlight.",
    ],
}

# ── Biome definitions ────────────────────────────────────────────────

BIOMES = {
    "depths": {
        "name": "The Depths",
        "floors": (1, 4),
        "bg_tint": (30, 20, 10),
        "particle_color": (255, 140, 40),
        "particle_count": 25,
    },
    "catacombs": {
        "name": "The Catacombs",
        "floors": (5, 9),
        "bg_tint": (10, 15, 30),
        "particle_color": (60, 120, 220),
        "particle_count": 30,
    },
    "abyss": {
        "name": "The Abyss",
        "floors": (10, 999),
        "bg_tint": (5, 3, 15),
        "particle_color": (120, 40, 180),
        "particle_count": 40,
    },
}


def get_biome(floor: int) -> dict:
    """Return the biome dict for a given floor."""
    for biome in BIOMES.values():
        lo, hi = biome["floors"]
        if lo <= floor <= hi:
            return biome
    return BIOMES["abyss"]

BRANCH_POINTS = {2, 4}

ENEMY_POOL = {
    "slime": {"name": "Slime", "hp": 50, "atk": 8, "defn": 3, "eva": 0.02, "gold_min": 10, "gold_max": 20, "xp_reward": 15},
    "dragon": {"name": "Dragon", "hp": 80, "atk": 14, "defn": 6, "eva": 0.05, "gold_min": 20, "gold_max": 40, "xp_reward": 30},
    "wisp": {"name": "Wisp", "hp": 40, "atk": 10, "defn": 2, "eva": 0.07, "gold_min": 12, "gold_max": 22, "xp_reward": 18},
    "cultist": {"name": "Cultist", "hp": 70, "atk": 12, "defn": 4, "eva": 0.05, "gold_min": 18, "gold_max": 35, "xp_reward": 35},
    "brute": {"name": "Vanguard Brute", "hp": 120, "atk": 18, "defn": 8, "eva": 0.03, "gold_min": 25, "gold_max": 50, "xp_reward": 50},
    "golem": {"name": "Golem", "hp": 150, "atk": 16, "defn": 14, "eva": 0.01, "gold_min": 30, "gold_max": 60, "xp_reward": 55},
    "stalker": {"name": "Shadow Stalker", "hp": 60, "atk": 15, "defn": 3, "eva": 0.12, "gold_min": 28, "gold_max": 55, "xp_reward": 45},
    "abyssal_warden": {"name": "Abyssal Warden", "hp": 250, "atk": 25, "defn": 12, "eva": 0.08, "gold_min": 80, "gold_max": 150, "xp_reward": 100},
}


def scale_enemy(base: dict, floor: int) -> dict:
    """Scale enemy stats by floor. Bosses scale slightly less per floor."""
    if floor <= 1:
        return dict(base)
    mult = 1.0 + (floor - 1) * 0.15  # +15% stats per floor
    is_boss = base.get("name") == "Abyssal Warden"
    if is_boss:
        mult = 1.0 + (floor - 1) * 0.10  # Boss scales slower but starts higher
    scaled = dict(base)
    scaled["hp"] = max(1, int(base["hp"] * mult))
    scaled["atk"] = max(1, int(base["atk"] * mult))
    scaled["defn"] = max(1, int(base["defn"] * mult))
    scaled["eva"] = min(0.30, base["eva"] * mult)
    scaled["gold_min"] = int(base["gold_min"] * mult)
    scaled["gold_max"] = int(base["gold_max"] * mult)
    scaled["xp_reward"] = int(base["xp_reward"] * mult)
    return scaled


def generate_dungeon(floor: int) -> list:
    """Generate a dungeon run of 4-6 rooms."""
    rooms = []

    # First room: always combat (warmup)
    enemy = _pick_enemy(floor)
    rooms.append({
        "type": RoomType.COMBAT,
        "enemy": enemy,
        "cleared": False,
        "floor": floor,
        "flavor": random.choice(FLAVOR[RoomType.COMBAT]),
    })

    # Middle rooms: random mix
    mid_count = random.randint(2, 4)
    for _ in range(mid_count):
        rooms.append(_generate_room(floor))

    # Boss floor: replace the last mid room with a boss room (right before EXIT)
    if floor % 5 == 0 and mid_count >= 1:
        rooms[-1] = {
            "type": RoomType.BOSS,
            "enemy": "abyssal_warden",
            "cleared": False,
            "floor": floor,
            "flavor": random.choice(FLAVOR[RoomType.BOSS]),
        }

    # Final room: exit
    rooms.append({
        "type": RoomType.EXIT,
        "enemy": None,
        "cleared": False,
        "floor": floor,
        "flavor": random.choice(FLAVOR[RoomType.EXIT]),
    })

    return rooms


def _generate_room(floor: int) -> dict:
    """Generate a random room weighted by type with flavor text."""
    roll = random.random()
    if roll < 0.45:
        rtype = RoomType.COMBAT
        enemy = _pick_enemy(floor)
    elif roll < 0.55:
        rtype = RoomType.LOOT
        enemy = None
    elif roll < 0.65:
        rtype = RoomType.SHRINE
        enemy = None
    elif roll < 0.80:
        rtype = RoomType.REST
        enemy = None
    elif roll < 0.90:
        rtype = RoomType.SHOP
        enemy = None
    elif roll < 0.98:
        rtype = RoomType.ELITE
        elite_pool = ["brute"] if floor < 3 else ["brute", "golem", "stalker"]
        enemy = random.choice(elite_pool)
    else:
        rtype = RoomType.TRAP
        enemy = None
    return {
        "type": rtype,
        "enemy": enemy,
        "cleared": False,
        "floor": floor,
        "flavor": random.choice(FLAVOR[rtype]),
    }


def _pick_enemy(floor: int) -> str:
    """Pick a random enemy appropriate for the floor."""
    pool = ["slime", "dragon"]
    if floor >= 2:
        pool.append("brute")
        pool.append("cultist")
    if floor >= 3:
        pool.append("wisp")
    if floor >= 4:
        pool.append("golem")
    if floor >= 6:
        pool.append("stalker")
    return random.choice(pool)


class DungeonRun:
    """Tracks the state of a single dungeon run."""

    def __init__(self, player, floor: int = 1, ng_plus: bool = False):
        self.player = player
        self.floor = floor
        self.biome = get_biome(floor)
        self.rooms = generate_dungeon(floor)
        self.room_index = 0          # rooms completed (also index into rooms)
        self.total_rooms = len(self.rooms)
        self.enemies_defeated = 0
        self.total_gold = 0
        self.elapsed_ms = 0
        self.ng_plus = ng_plus

        # Room transition state
        self.room_transition = 0.0   # timer for "room cleared" overlay
        self.room_cleared = False

        # Branching state
        self.branching = False
        self.branch_choices = []     # two room dicts when at a branch point

        # Blessings from shrines (apply for the run)
        self.blessings: dict = {}

    @property
    def current(self) -> dict:
        if 0 <= self.room_index < len(self.rooms):
            return self.rooms[self.room_index]
        return None

    @property
    def done(self) -> bool:
        return self.room_index >= len(self.rooms)

    def advance(self):
        """Move to next room (only after current is cleared)."""
        self.room_index += 1

    def mark_cleared(self):
        """Mark current room cleared and start transition overlay."""
        if self.current:
            self.current["cleared"] = True
        self.room_cleared = True
        self.room_transition = 1500  # 1.5s overlay

    def update(self, dt_ms: int):
        self.elapsed_ms += dt_ms
        if self.room_transition > 0:
            self.room_transition -= dt_ms
            if self.room_transition <= 0:
                self.room_cleared = False
                # Check if we're at a branch point
                if self.room_index in BRANCH_POINTS and not self.branching:
                    self._setup_branch()
                return True  # signal overlay finished
        return False

    def _setup_branch(self):
        """Generate two room choices for the player."""
        self.branching = True
        self.branch_choices = [_generate_room(self.floor), _generate_room(self.floor)]

    def resolve_branch(self, selection: int):
        """Set the chosen room and discard the other, then advance."""
        if not self.branching or selection < 0 or selection >= len(self.branch_choices):
            return
        chosen = self.branch_choices[selection]
        # Insert chosen room at next position
        self.rooms.insert(self.room_index + 1, chosen)
        self.total_rooms = len(self.rooms)
        self.branching = False
        self.branch_choices = []
        self.advance()

    def skip_room(self):
        """Skip the current room (used in branching)."""
        if self.current:
            self.current["cleared"] = True
        self.room_index += 1
