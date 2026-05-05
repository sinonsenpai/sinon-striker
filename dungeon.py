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


ROOM_ICONS = {
    RoomType.COMBAT: "combat",
    RoomType.ELITE: "elite",
    RoomType.LOOT: "loot",
    RoomType.REST: "rest",
    RoomType.SHOP: "shop",
    RoomType.EXIT: "exit",
    RoomType.BOSS: "boss",
}

ROOM_COLORS = {
    RoomType.COMBAT: (220, 50, 60),
    RoomType.ELITE: (180, 60, 255),
    RoomType.LOOT: (255, 215, 0),
    RoomType.REST: (50, 210, 100),
    RoomType.SHOP: (0, 240, 255),
    RoomType.EXIT: (255, 215, 0),
    RoomType.BOSS: (255, 60, 60),
}

ROOM_LABELS = {
    RoomType.COMBAT: "Combat",
    RoomType.ELITE: "Elite",
    RoomType.LOOT: "Loot",
    RoomType.REST: "Rest",
    RoomType.SHOP: "Shop",
    RoomType.EXIT: "Exit",
    RoomType.BOSS: "Boss",
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
}

BRANCH_POINTS = {2, 4}

ENEMY_POOL = {
    "slime": {"name": "Slime", "hp": 50, "atk": 8, "defn": 3, "gold_min": 10, "gold_max": 20, "xp_reward": 15},
    "dragon": {"name": "Dragon", "hp": 80, "atk": 14, "defn": 6, "gold_min": 20, "gold_max": 40, "xp_reward": 30},
    "brute": {"name": "Vanguard Brute", "hp": 120, "atk": 18, "defn": 8, "gold_min": 25, "gold_max": 50, "xp_reward": 50},
    "abyssal_warden": {"name": "Abyssal Warden", "hp": 250, "atk": 25, "defn": 12, "gold_min": 80, "gold_max": 150, "xp_reward": 100},
}


def generate_dungeon(floor: int) -> list:
    """Generate a dungeon run of 4-6 rooms."""
    rooms = []

    # First room: always combat (warmup)
    enemy = "dragon" if floor >= 2 else "slime"
    rooms.append({
        "type": RoomType.COMBAT,
        "enemy": enemy,
        "cleared": False,
        "flavor": random.choice(FLAVOR[RoomType.COMBAT]),
    })

    # Middle rooms: random mix
    mid_count = random.randint(2, 4)
    for _ in range(mid_count):
        rooms.append(_generate_room(floor))

    # Boss floor: replace the last mid room with a boss room
    if floor % 5 == 0 and mid_count >= 1:
        rooms[-2] = {
            "type": RoomType.BOSS,
            "enemy": "abyssal_warden",
            "cleared": False,
            "flavor": random.choice(FLAVOR[RoomType.BOSS]),
        }

    # Final room: exit
    rooms.append({
        "type": RoomType.EXIT,
        "enemy": None,
        "cleared": False,
        "flavor": random.choice(FLAVOR[RoomType.EXIT]),
    })

    return rooms


def _generate_room(floor: int) -> dict:
    """Generate a random room weighted by type with flavor text."""
    roll = random.random()
    if roll < 0.45:
        rtype = RoomType.COMBAT
        enemy = _pick_enemy(floor)
    elif roll < 0.65:
        rtype = RoomType.LOOT
        enemy = None
    elif roll < 0.80:
        rtype = RoomType.REST
        enemy = None
    elif roll < 0.90:
        rtype = RoomType.SHOP
        enemy = None
    else:
        rtype = RoomType.ELITE
        enemy = "brute" if floor >= 1 else "dragon"
    return {
        "type": rtype,
        "enemy": enemy,
        "cleared": False,
        "flavor": random.choice(FLAVOR[rtype]),
    }


def _pick_enemy(floor: int) -> str:
    """Pick a random enemy appropriate for the floor."""
    if floor >= 2:
        return random.choice(["dragon", "brute"])
    else:
        return random.choice(["slime", "dragon"])


class DungeonRun:
    """Tracks the state of a single dungeon run."""

    def __init__(self, player, floor: int = 1):
        self.player = player
        self.floor = floor
        self.rooms = generate_dungeon(floor)
        self.room_index = 0          # rooms completed (also index into rooms)
        self.total_rooms = len(self.rooms)
        self.enemies_defeated = 0
        self.total_gold = 0

        # Room transition state
        self.room_transition = 0.0   # timer for "room cleared" overlay
        self.room_cleared = False

        # Branching state
        self.branching = False
        self.branch_choices = []     # two room dicts when at a branch point

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
