"""
Achievement System — track and display player accomplishments.
"""

import json
import os
import pygame


ACHIEVEMENT_FILE = "achievements.json"


ACHIEVEMENT_DEFS = [
    # Combat
    {"id": "first_blood", "name": "First Blood", "desc": "Defeat your first enemy.", "icon": "🗡️", "counter": "kills", "threshold": 1},
    {"id": "slayer", "name": "Slayer", "desc": "Defeat 10 enemies.", "icon": "⚔️", "counter": "kills", "threshold": 10},
    {"id": "massacre", "name": "Massacre", "desc": "Defeat 50 enemies.", "icon": "💀", "counter": "kills", "threshold": 50},
    {"id": "crit_master", "name": "Crit Master", "desc": "Land 10 critical hits.", "icon": "⭐", "counter": "crits", "threshold": 10},
    {"id": "skill_surge", "name": "Skill Surge", "desc": "Use skills 5 times.", "icon": "✨", "counter": "skills_used", "threshold": 5},
    # Dungeon
    {"id": "delver", "name": "Delver", "desc": "Complete a dungeon run.", "icon": "🏰", "counter": "dungeons_completed", "threshold": 1},
    {"id": "deep_trek", "name": "Deep Trek", "desc": "Reach dungeon floor 5.", "icon": "⛰️", "counter": "deepest_floor", "threshold": 5},
    {"id": "abyss_walker", "name": "Abyss Walker", "desc": "Reach dungeon floor 10.", "icon": "🌑", "counter": "deepest_floor", "threshold": 10},
    # Collection
    {"id": "collector", "name": "Collector", "desc": "Find 25 items.", "icon": "🎒", "counter": "items_found", "threshold": 25},
    {"id": "legendary_find", "name": "Legendary Find", "desc": "Find a Legendary item.", "icon": "👑", "counter": "legendaries_found", "threshold": 1},
    {"id": "gold_hoarder", "name": "Gold Hoarder", "desc": "Earn 1,000 gold total.", "icon": "💰", "counter": "gold_earned", "threshold": 1000},
    {"id": "miser", "name": "Miser", "desc": "Earn 5,000 gold total.", "icon": "💎", "counter": "gold_earned", "threshold": 5000},
    # Leveling
    {"id": "novice", "name": "Novice", "desc": "Reach level 5.", "icon": "📖", "counter": "level_reached", "threshold": 5},
    {"id": "warrior", "name": "Warrior", "desc": "Reach level 10.", "icon": "🛡️", "counter": "level_reached", "threshold": 10},
    {"id": "legend", "name": "Legend", "desc": "Reach level 25.", "icon": "🏆", "counter": "level_reached", "threshold": 25},
    # One-shots
    {"id": "set_bonus", "name": "Set Bonus", "desc": "Equip a complete gear set.", "icon": "🎯"},
    {"id": "deaths_door", "name": "Death's Door", "desc": "Fall in battle.", "icon": "💔", "counter": "deaths", "threshold": 1},
    {"id": "apothecary", "name": "Apothecary", "desc": "Buy an item from the Apothecary.", "icon": "🧪"},
    {"id": "merchant", "name": "Merchant", "desc": "Sell an item at the Smithy.", "icon": "🔨"},
    # Phase 1 new
    {"id": "confuse_self_hit", "name": "Confusion Reigns", "desc": "Cause an enemy to hit itself via Confused.", "icon": "🌀"},
    {"id": "frozen_solid", "name": "Frozen Solid", "desc": "Inflict Frozen on 10 enemies.", "icon": "❄️", "counter": "frozen_inflicted", "threshold": 10},
    {"id": "bloodletter", "name": "Bloodletter", "desc": "Apply Bleed 20 times.", "icon": "🩸", "counter": "bleed_applied", "threshold": 20},
    {"id": "survivalist", "name": "Survivalist", "desc": "Heal 500 HP total via Regen.", "icon": "💚", "counter": "regen_healed", "threshold": 500},
    # Phase 2 — Skill Tree / Class
    {"id": "class_warrior", "name": "Class Master: Warrior", "desc": "Reach level 20 as Warrior.", "icon": "🛡️", "counter": "level_warrior", "threshold": 20},
    {"id": "class_mage", "name": "Class Master: Mage", "desc": "Reach level 20 as Mage.", "icon": "🔮", "counter": "level_mage", "threshold": 20},
    {"id": "class_rogue", "name": "Class Master: Rogue", "desc": "Reach level 20 as Rogue.", "icon": "🗡️", "counter": "level_rogue", "threshold": 20},
    {"id": "scholar", "name": "Scholar", "desc": "Unlock all 8 skills for your class.", "icon": "📚"},
    {"id": "jack_of_trades", "name": "Jack of All Trades", "desc": "Use 10 different skills in a single dungeon run.", "icon": "🎭"},
    {"id": "untouchable", "name": "Untouchable", "desc": "Win 5 fights without taking damage.", "icon": "💨", "counter": "flawless_victories", "threshold": 5},
]


class AchievementManager:
    """Tracks achievement progress and unlocks."""

    def __init__(self):
        self.unlocked: set[str] = set()
        self.counters: dict[str, int] = {}
        self._toast_queue: list[str] = []
        self._ach_by_id = {a["id"]: a for a in ACHIEVEMENT_DEFS}

    def inc(self, counter: str, amount: int = 1):
        """Increment a counter and check for threshold unlocks."""
        self.counters[counter] = self.counters.get(counter, 0) + amount
        self._check_counter_unlocks(counter)

    def set(self, counter: str, value: int):
        """Set a counter to a value and check for threshold unlocks."""
        old = self.counters.get(counter, 0)
        if value > old:
            self.counters[counter] = value
            self._check_counter_unlocks(counter)

    def _check_counter_unlocks(self, counter: str):
        """Check all achievements that use this counter."""
        for ach in ACHIEVEMENT_DEFS:
            if ach.get("counter") == counter:
                threshold = ach.get("threshold", 0)
                if self.counters.get(counter, 0) >= threshold:
                    self.unlock(ach["id"])

    def unlock(self, ach_id: str):
        """Unlock a one-shot achievement."""
        if ach_id not in self._ach_by_id:
            return
        if ach_id not in self.unlocked:
            self.unlocked.add(ach_id)
            self._toast_queue.append(ach_id)

    def pop_toast(self) -> dict | None:
        """Return the next newly-unlocked achievement dict, or None."""
        while self._toast_queue:
            ach_id = self._toast_queue.pop(0)
            ach = self._ach_by_id.get(ach_id)
            if ach:
                return ach
        return None

    def peek_toast(self) -> dict | None:
        """Return the next toast without removing it."""
        if self._toast_queue:
            ach_id = self._toast_queue[0]
            return self._ach_by_id.get(ach_id)
        return None

    def save(self):
        """Save achievements to JSON."""
        data = {
            "unlocked": list(self.unlocked),
            "counters": self.counters,
        }
        try:
            with open(ACHIEVEMENT_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self):
        """Load achievements from JSON."""
        if not os.path.exists(ACHIEVEMENT_FILE):
            return
        try:
            with open(ACHIEVEMENT_FILE) as f:
                data = json.load(f)
            self.unlocked = set(data.get("unlocked", []))
            self.counters = data.get("counters", {})
        except Exception:
            pass

    def reset(self):
        """Clear all achievements for a new game."""
        self.unlocked.clear()
        self.counters.clear()
        self._toast_queue.clear()


class AchievementToast:
    """Renders a slide-in/fade-out achievement toast at top-center."""

    SLIDE_IN_MS = 350
    HOLD_MS = 2500
    FADE_OUT_MS = 500

    def __init__(self, screen_w: int):
        self._ach = None
        self._timer = 0.0
        self._phase = "idle"  # idle, slide, hold, fade
        self._screen_w = screen_w
        self._font_title = pygame.font.SysFont("arial", 22, bold=True)
        self._font_desc = pygame.font.SysFont("arial", 14, bold=False)

    def show(self, ach: dict):
        """Display a new achievement toast."""
        self._ach = ach
        self._timer = 0.0
        self._phase = "slide"

    def is_idle(self) -> bool:
        return self._phase == "idle"

    def update(self, dt_ms: int) -> bool:
        """Update animation. Returns True if toast finished and should advance queue."""
        if self._phase == "idle":
            return False

        self._timer += dt_ms

        if self._phase == "slide" and self._timer >= self.SLIDE_IN_MS:
            self._phase = "hold"
            self._timer = 0.0
        elif self._phase == "hold" and self._timer >= self.HOLD_MS:
            self._phase = "fade"
            self._timer = 0.0
        elif self._phase == "fade" and self._timer >= self.FADE_OUT_MS:
            self._phase = "idle"
            self._ach = None
            return True
        return False

    def draw(self, screen: pygame.Surface):
        """Draw the toast if active."""
        if self._phase == "idle" or self._ach is None:
            return

        # Calculate alpha and y-offset
        if self._phase == "slide":
            t = min(1.0, self._timer / self.SLIDE_IN_MS)
            eased = 1.0 - (1.0 - t) ** 3
            alpha = int(255 * eased)
            y_offset = int(-50 * (1.0 - eased))
        elif self._phase == "hold":
            alpha = 255
            y_offset = 0
        else:  # fade
            t = min(1.0, self._timer / self.FADE_OUT_MS)
            alpha = int(255 * (1.0 - t))
            y_offset = int(15 * t)

        pad = 14
        header_pad = 6
        icon = self._ach.get("icon", "🏆")
        name = self._ach.get("name", "Achievement")
        desc = self._ach.get("desc", "")

        icon_surf = self._font_title.render(icon, True, (255, 215, 0))
        name_surf = self._font_title.render(name, True, (255, 215, 0))
        desc_surf = self._font_desc.render(desc, True, (230, 230, 245))
        header_font = pygame.font.SysFont("arial", 12, bold=True)
        header_surf = header_font.render("ACHIEVEMENT UNLOCKED", True, (160, 160, 180))

        # Layout sizing
        header_h = header_surf.get_height() + 4
        text_block_w = max(name_surf.get_width(), desc_surf.get_width())
        content_w = icon_surf.get_width() + 10 + text_block_w
        content_h = max(icon_surf.get_height(), name_surf.get_height() + desc_surf.get_height() + 2)
        panel_w = max(content_w + pad * 2, header_surf.get_width() + pad * 2)
        panel_h = header_h + content_h + pad * 2 + 4

        px = (self._screen_w - panel_w) // 2
        py = 18 + y_offset

        # Panel background
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((20, 15, 40, min(240, alpha)))
        screen.blit(panel, (px, py))

        # Gold border
        border_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (255, 215, 0, min(220, alpha)), (0, 0, panel_w, panel_h), width=2, border_radius=8)
        screen.blit(border_surf, (px, py))

        # Header text
        header_surf.set_alpha(min(alpha, 200))
        screen.blit(header_surf, (px + (panel_w - header_surf.get_width()) // 2, py + header_pad))

        # Icon and name/desc
        base_y = py + header_h + header_pad + 4
        icon_x = px + pad
        screen.blit(icon_surf, (icon_x, base_y))

        text_x = icon_x + icon_surf.get_width() + 10
        screen.blit(name_surf, (text_x, base_y))
        screen.blit(desc_surf, (text_x, base_y + name_surf.get_height() + 2))
