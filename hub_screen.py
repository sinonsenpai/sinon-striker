"""
Hub Screen — Haven's Rest town between title and battles.
"""

import math
import random
import pygame
from enum import Enum, auto
from item import Rarity, ItemSlot, Weapon, Armor, Ring, Amulet, LootGenerator, Consumable, merge_into_stack, RARITY_PREFIX
from sprites import get_hub_sinon
import achievements
from skills import SkillRegistry


# ── Palette ────────────────────────────────────────────────────────────
BG_COLOR = (18, 14, 30)
NEON_CYAN = (0, 240, 255)
NEON_CYAN_DIM = (0, 100, 120)
GOLD = (255, 215, 0)
GOLD_DIM = (120, 100, 30)
WHITE = (230, 230, 245)
DIM_WHITE = (160, 160, 180)
RED = (220, 50, 60)
GREEN = (50, 210, 100)
PANEL_BG = (20, 15, 40)

RARITY_COLOR = {
    Rarity.COMMON:    (185, 185, 195),
    Rarity.RARE:     (60, 140, 255),
    Rarity.EPIC:     (180, 60, 255),
    Rarity.LEGENDARY: (255, 200, 40),
}
RARITY_ACCENT = {
    Rarity.COMMON:    (120, 120, 130),
    Rarity.RARE:     (30, 80, 220),
    Rarity.EPIC:     (120, 30, 180),
    Rarity.LEGENDARY: (220, 170, 0),
}
SLOT_LABEL = {ItemSlot.WEAPON: "Weapon", ItemSlot.ARMOR: "Armor"}


# ── Enums ──────────────────────────────────────────────────────────────
class HubSubState(Enum):
    MAIN = auto()
    SMITHY_INVENTORY = auto()
    APOTHECARY = auto()
    MERCHANT = auto()
    GUILD_HALL = auto()
    RETURN_PROMPT = auto()
    TOAST = auto()
    ACHIEVEMENTS = auto()


# ── Location data ──────────────────────────────────────────────────────
LOCATIONS = [
    {"name": "Dungeon Gate", "icon": "sword",   "desc": "Descend into danger",   "key": "dungeon"},
    {"name": "Smithy",       "icon": "hammer",  "desc": "Gear, upgrades, sell",   "key": "smithy"},
    {"name": "Guild Hall",   "icon": "book",    "desc": "Bestiary and quests",   "key": "guild"},
    {"name": "Apothecary",   "icon": "potion",  "desc": "Buy consumables",       "key": "apothecary"},
    {"name": "Merchant",     "icon": "chest",   "desc": "Buy weapons and armor", "key": "merchant"},
    {"name": "Rest",         "icon": "moon",    "desc": "Restore HP and SP",     "key": "rest"},
]

CARD_W, CARD_H = 126, 132
CARD_GAP = 4
CARD_LIFT = 4

# ── Shop data ───────────────────────────────────────────────────────────
SHOP_ITEMS = [
    {"name": "Small Potion",  "cost": 50,  "hp_restore": 30, "desc": "Restores 30 HP"},
    {"name": "Large Potion",  "cost": 120, "hp_restore": 75, "desc": "Restores 75 HP"},
    {"name": "Antidote",      "cost": 40,  "hp_restore": 0,  "desc": "Cure poison (WIP)"},
]


# ── Dust particle ──────────────────────────────────────────────────────
class GoldenDust:
    """A tiny mote drifting upward like dust in warm light."""
    def __init__(self, w: int, h: int):
        self.x = random.uniform(0, w)
        self.y = random.uniform(h * 0.4, h)
        self.size = random.uniform(0.6, 2.0)
        self.speed = random.uniform(0.15, 0.55)
        self.wobble_amp = random.uniform(0.2, 0.9)
        self.wobble_rate = random.uniform(0.015, 0.04)
        self.phase = random.uniform(0, math.pi * 2)
        self.max_alpha = random.randint(60, 160)

    def update(self, dt_ms: int, w: int):
        self.y -= self.speed * dt_ms / 16.0
        self.x += math.sin(self.phase) * self.wobble_amp * dt_ms / 16.0
        self.phase += self.wobble_rate * dt_ms / 16.0
        if self.y < -10:
            self.y = random.uniform(w * 0.3, w * 0.7)
            self.x = random.uniform(0, w * 0.8)

    def alpha(self, time_ms: float) -> int:
        wave = 0.5 + 0.5 * math.sin(time_ms * 0.003 + self.x * 0.01)
        return max(0, min(255, int(self.max_alpha * wave)))


def _wrap_text(font, text: str, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


# ── Hub Screen ─────────────────────────────────────────────────────────
class HubScreen:
    """Renders and manages the Haven's Rest hub town."""

    def __init__(self, screen: pygame.Surface, player, ach_manager=None, sound_manager=None, bestiary_manager=None, quest_manager=None, ng_plus_unlocked: bool = False):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.player = player
        self._ach_manager = ach_manager
        self._snd = sound_manager
        self._bestiary = bestiary_manager
        self._quests = quest_manager
        self._ng_plus_unlocked = ng_plus_unlocked

        # ── Dust particles ──
        self._dust = [GoldenDust(self.w, self.h) for _ in range(40)]
        self._elapsed_ms = 0.0

        # ── Fonts ──
        self.font_banner = pygame.font.SysFont("arial", 36, bold=True)
        self.font_icon = pygame.font.SysFont("arial", 30, bold=True)
        self.font_card_name = pygame.font.SysFont("arial", 18, bold=True)
        self.font_card_desc = pygame.font.SysFont("arial", 14, bold=False)
        self.font_prompt = pygame.font.SysFont("arial", 26, bold=True)
        self.font_toast = pygame.font.SysFont("arial", 24, bold=True)
        self.font_small = pygame.font.SysFont("arial", 15, bold=False)
        self.font_hint = pygame.font.SysFont("arial", 14, bold=False)

        # Inventory fonts (for smithy)
        self.font_inv_title = pygame.font.SysFont("arial", 30, bold=True)
        self.font_inv_section = pygame.font.SysFont("arial", 18, bold=True)
        self.font_inv_item = pygame.font.SysFont("arial", 16, bold=False)
        self.font_inv_stat = pygame.font.SysFont("arial", 16, bold=True)
        self.font_inv_hint = pygame.font.SysFont("arial", 14, bold=False)

        # ── Selection ──
        self.selected_index = 0

        # ── Sub-state ──
        self.sub_state = HubSubState.MAIN

        # ── Card animation ──
        self._card_slide = 0.0    # 0..1 entrance slide progress
        self._card_slide_in = True

        # ── Toast ──
        self._toast_timer = 0.0
        self._toast_text = ""

        # ── Smithy inventory cursors ──
        self._inv_cursor = 0
        self._inv_section = "bag"       # "equipped" or "bag"
        self._inv_equip_cursor = 0      # 0=weapon, 1=armor
        self._inv_scroll_offset = 0
        self._sell_confirming = False
        self._upgrade_confirming = False
        self._smithy_mode = "sell"      # "sell" or "upgrade"
        self._sell_toast_timer = 0
        self._sell_toast_text = ""
        self._upgrade_toast_timer = 0
        self._upgrade_toast_text = ""

        # ── Shop state ──
        self._shop_cursor = 0
        self._shop_confirming = False
        self._shop_toast_timer = 0
        self._shop_toast_text = ""

        # ── Merchant state ──
        self._merchant_stock: list = []
        self._merchant_cursor = 0
        self._merchant_confirming = False
        self._merchant_toast_timer = 0
        self._merchant_toast_text = ""

        # ── Guild hall state ──
        self._guild_tab = 0  # 0=bestiary, 1=quests, 2=respec
        self._bestiary_cursor = 0
        self._bestiary_scroll_offset = 0
        self._quest_cursor = 0
        self._quest_scroll_offset = 0
        self._respec_tree_index = 0
        self._respec_confirming = False

        # ── Achievement viewer state ──
        self._ach_cursor = 0
        self._ach_scroll_offset = 0

        # ── Fade ──
        self.fade_alpha = 0.0           # 0..255
        self._fade_target = 0.0
        self._fade_speed = 0.0          # units per ms

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def move_left(self):
        if self.sub_state != HubSubState.MAIN:
            return
        self.selected_index = (self.selected_index - 1) % len(LOCATIONS)

    def move_right(self):
        if self.sub_state != HubSubState.MAIN:
            return
        self.selected_index = (self.selected_index + 1) % len(LOCATIONS)

    def confirm(self):
        """Confirm the selected location. May change sub-state or signal actions."""
        if self.sub_state == HubSubState.RETURN_PROMPT:
            return  # handled via confirm_y / confirm_n

        if self.sub_state != HubSubState.MAIN:
            return

        loc = LOCATIONS[self.selected_index]
        key = loc["key"]

        if key == "dungeon":
            self._start_fade(255, 0.52)
            return "battle"
        elif key == "smithy":
            self._enter_smithy()
        elif key == "guild":
            self._enter_guild_hall()
        elif key == "apothecary":
            self._enter_shop()
        elif key == "merchant":
            self._enter_merchant()
        elif key == "rest":
            self._do_rest()

    def open_achievements(self):
        if self.sub_state == HubSubState.MAIN:
            self._enter_achievements()

    def cancel(self):
        """ESC pressed. Behaviour depends on sub-state."""
        if self.sub_state == HubSubState.MAIN:
            self.sub_state = HubSubState.RETURN_PROMPT
        elif self.sub_state in (HubSubState.APOTHECARY, HubSubState.SMITHY_INVENTORY, HubSubState.MERCHANT, HubSubState.ACHIEVEMENTS, HubSubState.GUILD_HALL):
            self.sub_state = HubSubState.MAIN
        elif self.sub_state == HubSubState.RETURN_PROMPT:
            self.sub_state = HubSubState.MAIN
        elif self.sub_state == HubSubState.TOAST:
            self.sub_state = HubSubState.MAIN
            self._toast_timer = 0

    def confirm_return(self):
        """Y pressed in return prompt."""
        if self.sub_state == HubSubState.RETURN_PROMPT:
            return "title"

    def decline_return(self):
        """N pressed in return prompt."""
        if self.sub_state == HubSubState.RETURN_PROMPT:
            self.sub_state = HubSubState.MAIN

    # ── Smithy inventory controls ────────────────────────────────────

    def smithy_move_up(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        self._sell_confirming = False
        self._upgrade_confirming = False
        p = self.player
        if p.inventory:
            self._inv_cursor = (self._inv_cursor - 1) % len(p.inventory)
            if self._inv_cursor < self._inv_scroll_offset:
                self._inv_scroll_offset = self._inv_cursor

    def smithy_move_down(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        self._sell_confirming = False
        self._upgrade_confirming = False
        p = self.player
        if p.inventory:
            self._inv_cursor = (self._inv_cursor + 1) % len(p.inventory)
            # scroll to keep cursor visible
            max_visible = 6  # approximate; refined in draw
            if self._inv_cursor >= self._inv_scroll_offset + max_visible:
                self._inv_scroll_offset = self._inv_cursor - max_visible + 1

    def smithy_sell(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        if self._smithy_mode != "sell":
            return
        p = self.player
        if not p.inventory:
            return
        item = p.inventory[self._inv_cursor]

        if not self._sell_confirming:
            self._sell_confirming = True
            return

        price = self._sell_price(item)
        p.gold += price
        p.inventory.pop(self._inv_cursor)
        self._sell_toast_text = f"Sold {item.name} for {price}g!"
        self._sell_toast_timer = 1500
        self._sell_confirming = False
        self._sfx("shop_sell")
        if self._ach_manager:
            self._ach_manager.unlock("merchant")

        if self._inv_cursor >= len(p.inventory):
            self._inv_cursor = max(0, len(p.inventory) - 1)
        if self._inv_scroll_offset > self._inv_cursor:
            self._inv_scroll_offset = max(0, self._inv_cursor - 1)

    def smithy_upgrade(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        if self._smithy_mode != "upgrade":
            return
        p = self.player
        if not p.inventory:
            return
        item = p.inventory[self._inv_cursor]
        if getattr(item, "quantity", 1) > 1:
            # Consumables are not upgradable
            self._upgrade_toast_text = "Consumables can't be upgraded."
            self._upgrade_toast_timer = 1500
            return
        if item.slot not in (ItemSlot.WEAPON, ItemSlot.ARMOR, ItemSlot.RING, ItemSlot.AMULET):
            self._upgrade_toast_text = "That item can't be upgraded."
            self._upgrade_toast_timer = 1500
            return

        price = self._upgrade_price(item)
        if not self._upgrade_confirming:
            if p.gold < price:
                self._sfx("error")
                self._upgrade_toast_text = "Not enough gold!"
                self._upgrade_toast_timer = 1500
                return
            self._upgrade_confirming = True
            return

        self._upgrade_confirming = False
        if p.gold < price:
            self._sfx("error")
            self._upgrade_toast_text = "Not enough gold!"
            self._upgrade_toast_timer = 1500
            return

        upgraded = self._upgrade_item(item)
        if upgraded is None:
            self._upgrade_toast_text = "That item is already at its limit."
            self._upgrade_toast_timer = 1500
            return

        p.gold -= price
        p.inventory[self._inv_cursor] = upgraded
        self._upgrade_toast_text = f"Upgraded {item.name}!"
        self._upgrade_toast_timer = 1500
        self._sfx("shop_buy")
        if self._ach_manager:
            self._ach_manager.inc("items_upgraded")
            self._ach_manager.unlock("artificer")

    def smithy_sort(self):
        """Sort sell list by rarity then stat value."""
        RANK = {Rarity.LEGENDARY: 3, Rarity.EPIC: 2, Rarity.RARE: 1, Rarity.COMMON: 0}
        def _power(it):
            if isinstance(it, Weapon):
                return it.atk
            if isinstance(it, Armor):
                return it.defense
            total = 0
            for stat, value in getattr(it, "stat_modifier", {}).items():
                total += int(value * 100) if stat in ("acc", "eva", "crit") else int(value)
            return total
        self.player.inventory.sort(
            key=lambda it: (RANK.get(it.rarity, 0), _power(it)),
            reverse=True,
        )
        self._inv_cursor = 0
        self._inv_scroll_offset = 0

    def _sell_price(self, item) -> int:
        """Calculate sell price based on rarity and stats."""
        base = {Rarity.COMMON: 10, Rarity.RARE: 25, Rarity.EPIC: 60, Rarity.LEGENDARY: 150}
        b = base.get(item.rarity, 10)
        if isinstance(item, Weapon):
            stat_bonus = item.atk
        elif isinstance(item, Armor):
            stat_bonus = item.defense
        else:
            stat_bonus = 0
            for stat, value in getattr(item, "stat_modifier", {}).items():
                stat_bonus += int(value * 100) if stat in ("acc", "eva", "crit") else int(value)
        return int(b * (1 + stat_bonus / 10))

    def smithy_toggle_mode(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        self._smithy_mode = "upgrade" if self._smithy_mode == "sell" else "sell"
        self._sell_confirming = False
        self._upgrade_confirming = False

    def _upgrade_price(self, item) -> int:
        if item.rarity == Rarity.LEGENDARY:
            return 0
        stat = item.atk if isinstance(item, Weapon) else getattr(item, "defense", 0)
        if item.rarity == Rarity.COMMON:
            return 100 + stat * 50
        if item.rarity == Rarity.RARE:
            return 300 + stat * 100
        return 700 + stat * 150

    def _upgrade_item(self, item):
        if item.rarity == Rarity.LEGENDARY:
            return None

        if item.rarity == Rarity.COMMON:
            next_rarity = Rarity.RARE
        elif item.rarity == Rarity.RARE:
            next_rarity = Rarity.EPIC
        else:
            next_rarity = Rarity.LEGENDARY
        base_name = item.name
        for prefix in sorted(RARITY_PREFIX.values(), key=len, reverse=True):
            if prefix and base_name.startswith(prefix):
                base_name = base_name[len(prefix):]
                break
        new_name = RARITY_PREFIX[next_rarity] + base_name

        if isinstance(item, Weapon):
            new_atk = max(item.atk + 2, int(item.atk * 1.5))
            return Weapon(new_name, next_rarity, new_atk, set_name=getattr(item, "set_name", None), acc=item.stat_modifier.get("acc", 0))
        if isinstance(item, Armor):
            new_def = max(item.defense + 1, int(item.defense * 1.5))
            return Armor(new_name, next_rarity, new_def, set_name=getattr(item, "set_name", None), eva=item.stat_modifier.get("eva", 0))
        if isinstance(item, Ring):
            acc = item.stat_modifier.get("acc", 0) + (0.02 if item.rarity == Rarity.COMMON else 0.03)
            crit = item.stat_modifier.get("crit", 0) + (0.02 if item.rarity == Rarity.COMMON else 0.03)
            return Ring(new_name, next_rarity, acc=acc, crit=crit, set_name=getattr(item, "set_name", None))
        if isinstance(item, Amulet):
            sp = item.stat_modifier.get("sp", 0) + (4 if item.rarity == Rarity.COMMON else 6)
            eva = item.stat_modifier.get("eva", 0) + (0.01 if item.rarity == Rarity.COMMON else 0.02)
            return Amulet(new_name, next_rarity, sp=sp, eva=eva, set_name=getattr(item, "set_name", None))
        return None

    # ── Properties ──────────────────────────────────────────────────

    @property
    def fade_done(self) -> bool:
        return self.fade_alpha >= 255 and self._fade_target == 255

    @property
    def wants_title(self) -> bool:
        """After Y confirmation, main.py reads this."""
        return False  # set by confirm_return in main.py flow

    # ── Animation control ───────────────────────────────────────────

    def start_fade_in(self):
        self.fade_alpha = 255.0
        self._start_fade(0, 0.45)
        self._card_slide = 0.0
        self._card_slide_in = True

    # ── Update / Draw ──────────────────────────────────────────────

    def update(self, dt_ms: int):
        self._elapsed_ms += dt_ms

        # Dust
        for d in self._dust:
            d.update(dt_ms, self.w)

        # Card slide
        if self._card_slide_in and self._card_slide < 1.0:
            self._card_slide = min(1.0, self._card_slide + dt_ms / 300.0)

        # Fade
        if self.fade_alpha != self._fade_target:
            step = self._fade_speed * dt_ms
            if self._fade_target > self.fade_alpha:
                self.fade_alpha = min(self._fade_target, self.fade_alpha + step)
            else:
                self.fade_alpha = max(self._fade_target, self.fade_alpha - step)

        # Toast timer
        if self.sub_state == HubSubState.TOAST:
            self._toast_timer += dt_ms
            if self._toast_timer > 1600:
                self.sub_state = HubSubState.MAIN
                self._toast_timer = 0

        # Shop toast timer
        if self._shop_toast_timer > 0:
            self._shop_toast_timer -= dt_ms
            if self._shop_toast_timer < 0:
                self._shop_toast_timer = 0

        # Sell toast timer
        if self._sell_toast_timer > 0:
            self._sell_toast_timer -= dt_ms
            if self._sell_toast_timer < 0:
                self._sell_toast_timer = 0

        if self._upgrade_toast_timer > 0:
            self._upgrade_toast_timer -= dt_ms
            if self._upgrade_toast_timer < 0:
                self._upgrade_toast_timer = 0

        # Merchant toast timer
        if self._merchant_toast_timer > 0:
            self._merchant_toast_timer -= dt_ms
            if self._merchant_toast_timer < 0:
                self._merchant_toast_timer = 0

    def draw(self, dt_ms: int):
        self.screen.fill(BG_COLOR)

        # ── Warm gradient at bottom ──
        y0 = int(self.h * 0.55)
        for y in range(y0, self.h):
            t = (y - y0) / max(1, self.h - y0)
            r = int(BG_COLOR[0] + (35 - BG_COLOR[0]) * t)
            g = int(BG_COLOR[1] + (20 - BG_COLOR[1]) * t)
            b = int(BG_COLOR[2] + (10 - BG_COLOR[2]) * t)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.w, y))

        # ── Golden dust ──
        for d in self._dust:
            a = d.alpha(self._elapsed_ms)
            if a < 15:
                continue
            color = (GOLD[0], GOLD[1], GOLD[2])
            bright = int(a / 255.0 * 180 + 40)
            c = tuple(min(255, ch * bright // 200) for ch in color)
            pygame.draw.circle(self.screen, c, (int(d.x), int(d.y)), max(1, int(d.size)))

        # ── Banner ──
        banner_y = int(self.h * 0.06)
        banner = self.font_banner.render("Haven's Rest", True, GOLD)
        bwidth = banner.get_width()
        bx = (self.w - bwidth) // 2
        self.screen.blit(banner, (bx, banner_y))

        # Decorative underline
        line_y = banner_y + banner.get_height() + 6
        left_x = bx - 20
        right_x = bx + bwidth + 20
        pygame.draw.line(self.screen, GOLD, (left_x, line_y), (left_x + 40, line_y), 1)
        pygame.draw.line(self.screen, GOLD, (right_x - 40, line_y), (right_x, line_y), 1)
        pygame.draw.circle(self.screen, GOLD_DIM, ((left_x + right_x) // 2, line_y), 3)

        # ── Level badge (top-right, left of gold) ──
        lv_text = f"Lv.{self.player.level}"
        lv_surf = self.font_card_name.render(lv_text, True, NEON_CYAN)
        lv_pad = 8
        lv_panel_w = lv_surf.get_width() + 16
        lv_panel_h = lv_surf.get_height() + 10
        lv_px = self.w - lv_panel_w - lv_pad
        lv_py = banner_y - 4
        lv_bg = pygame.Surface((lv_panel_w, lv_panel_h), pygame.SRCALPHA)
        lv_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 160))
        self.screen.blit(lv_bg, (lv_px, lv_py))
        pygame.draw.rect(self.screen, NEON_CYAN_DIM, (lv_px, lv_py, lv_panel_w, lv_panel_h), 1, border_radius=5)
        self.screen.blit(lv_surf, (lv_px + 8, lv_py + 5))

        # ── Gold display (top-right) ──
        gold_text = f"\u25cf Gold: {self.player.gold}"
        gold_surf = self.font_card_name.render(gold_text, True, GOLD)
        gold_pad = 16
        gold_panel_w = gold_surf.get_width() + 20
        gold_panel_h = gold_surf.get_height() + 10
        gold_px = lv_px - gold_panel_w - gold_pad
        gold_py = banner_y - 4
        gold_bg = pygame.Surface((gold_panel_w, gold_panel_h), pygame.SRCALPHA)
        gold_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 160))
        self.screen.blit(gold_bg, (gold_px, gold_py))
        pygame.draw.rect(self.screen, GOLD_DIM, (gold_px, gold_py, gold_panel_w, gold_panel_h), 1, border_radius=5)
        self.screen.blit(gold_surf, (gold_px + 10, gold_py + 5))

        # ── Location cards ──
        self._draw_cards()

        # ── Sinon sprite (bottom-center 'you are here' indicator) ──
        if self.sub_state == HubSubState.MAIN:
            if not hasattr(self, '_hub_sinon'):
                self._hub_sinon = get_hub_sinon()
            sw, sh = self._hub_sinon.get_size()
            sx = (self.w - sw) // 2
            sy = self.h - sh - 30
            # Shadow
            shadow = pygame.Surface((sw - 6, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 70), (0, 0, sw - 6, 6))
            self.screen.blit(shadow, (sx + 3, self.h - 26))
            self.screen.blit(self._hub_sinon, (sx, sy))

        # ── Hint ──
        if self.sub_state == HubSubState.MAIN:
            hint = self.font_hint.render("[LEFT/RIGHT] Navigate   [ENTER] Select   [A] Achievements   [ESC] Leave", True, (90, 90, 115))
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, self.h - 28))

        # ── Sub-state overlays ──
        if self.sub_state == HubSubState.APOTHECARY:
            self._draw_apothecary()
        elif self.sub_state == HubSubState.SMITHY_INVENTORY:
            self._draw_smithy_inventory()
        elif self.sub_state == HubSubState.RETURN_PROMPT:
            self._draw_return_prompt()
        elif self.sub_state == HubSubState.TOAST:
            self._draw_toast()
        elif self.sub_state == HubSubState.MERCHANT:
            self._draw_merchant()
        elif self.sub_state == HubSubState.GUILD_HALL:
            self._draw_guild_hall()
        elif self.sub_state == HubSubState.ACHIEVEMENTS:
            self._draw_achievements()

        # ── Fade overlay ──
        if self.fade_alpha > 1:
            fade = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fade.fill((0, 0, 0, min(255, int(self.fade_alpha))))
            self.screen.blit(fade, (0, 0))

    # ------------------------------------------------------------------ #
    #  Text fitting helper                                               #
    # ------------------------------------------------------------------ #

    def _fit_text(self, text: str, base_size: int, max_width: int, color, bold: bool = False, min_size: int = 12):
        """Render text, scaling font down until it fits max_width. Returns (surface, font_size_used)."""
        size = base_size
        while size >= min_size:
            font = pygame.font.SysFont("arial", size, bold=bold)
            surf = font.render(text, True, color)
            if surf.get_width() <= max_width:
                return surf, size
            size -= 1
        font = pygame.font.SysFont("arial", min_size, bold=bold)
        return font.render(text, True, color), min_size

    # ------------------------------------------------------------------ #
    #  Card drawing                                                      #
    # ------------------------------------------------------------------ #

    def _draw_cards(self):
        n = len(LOCATIONS)
        total_w = n * CARD_W + (n - 1) * CARD_GAP
        start_x = (self.w - total_w) // 2
        base_y = int(self.h * 0.38)

        # Slide-in: cards begin below screen
        slide_off = int((1.0 - self._ease_out(self._card_slide)) * (self.h + 100))
        card_y = base_y + slide_off

        for i, loc in enumerate(LOCATIONS):
            cx = start_x + i * (CARD_W + CARD_GAP)
            cy = card_y
            selected = i == self.selected_index

            # Lift selected card
            if selected and self._card_slide >= 0.95:
                cy -= CARD_LIFT

            # Card background
            card_surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            card_surf.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 180))
            self.screen.blit(card_surf, (cx, cy))

            # Border
            border_color = NEON_CYAN if selected else NEON_CYAN_DIM
            border_alpha = 200 if selected else 100
            border_surf = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
            pygame.draw.rect(border_surf, (*border_color, border_alpha),
                             (0, 0, CARD_W, CARD_H), width=2, border_radius=6)
            self.screen.blit(border_surf, (cx, cy))

            # Selection pulse
            if selected:
                pulse = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.005)
                sel_overlay = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
                sel_overlay.fill((*NEON_CYAN, int(25 * pulse)))
                self.screen.blit(sel_overlay, (cx, cy))

            # Icon (procedural, no font dependency)
            icon = loc["icon"]
            ix = cx + CARD_W // 2
            iy = cy + 18
            self._draw_card_icon(icon, ix, iy, GOLD if selected else DIM_WHITE)

            # Name — dynamically scale if too wide
            name_max_w = CARD_W - 16
            name_surf, _ = self._fit_text(loc["name"], 18, name_max_w, WHITE if selected else DIM_WHITE, bold=True, min_size=14)
            nx = cx + (CARD_W - name_surf.get_width()) // 2
            ny = iy + 52
            self.screen.blit(name_surf, (nx, ny))

            # Description — wrap onto up to 2 centered lines so cards don't collide
            desc_font = pygame.font.SysFont("arial", 11, bold=False)
            desc_lines = _wrap_text(desc_font, loc["desc"], CARD_W - 18)
            if len(desc_lines) > 2:
                first = " ".join(desc_lines[:2])
                second = " ".join(desc_lines[2:])
                desc_lines = [first, second]
            desc_lines = desc_lines[:2]
            desc_y = ny + name_surf.get_height() + 3
            for line in desc_lines:
                desc_surf = desc_font.render(line, True, (150, 150, 170))
                dx = cx + (CARD_W - desc_surf.get_width()) // 2
                self.screen.blit(desc_surf, (dx, desc_y))
                desc_y += desc_surf.get_height() + 1

            # Selection indicator
            if selected:
                tri_color = NEON_CYAN
                tri_h = 6
                tri_y = cy + CARD_H - 2
                tri_cx = cx + CARD_W // 2
                pts = [(tri_cx - 6, tri_y), (tri_cx + 6, tri_y), (tri_cx, tri_y + tri_h)]
                pygame.draw.polygon(self.screen, tri_color, pts)

    # ------------------------------------------------------------------ #
    #  Apothecary shop                                                   #
    # ------------------------------------------------------------------ #

    def _enter_shop(self):
        self._shop_cursor = 0
        self._shop_confirming = False
        self.sub_state = HubSubState.APOTHECARY

    def shop_move_up(self):
        if self.sub_state != HubSubState.APOTHECARY:
            return
        self._shop_confirming = False
        self._shop_cursor = (self._shop_cursor - 1) % len(SHOP_ITEMS)

    def shop_move_down(self):
        if self.sub_state != HubSubState.APOTHECARY:
            return
        self._shop_confirming = False
        self._shop_cursor = (self._shop_cursor + 1) % len(SHOP_ITEMS)

    def shop_buy(self):
        if self.sub_state != HubSubState.APOTHECARY:
            return
        item = SHOP_ITEMS[self._shop_cursor]

        if not self._shop_confirming:
            if self.player.gold < item["cost"]:
                self._sfx("error")
                self._shop_toast_text = "Not enough gold!"
                self._shop_toast_timer = 1500
                return
            self._shop_confirming = True
            return

        # Second press — confirm purchase
        self._shop_confirming = False
        if self.player.gold >= item["cost"]:
            self.player.gold -= item["cost"]
            from item import Consumable, Rarity, merge_into_stack
            potion = Consumable(item["name"], Rarity.COMMON, item["hp_restore"])
            merge_into_stack(self.player.consumables, potion)
            self._shop_toast_text = f"Purchased {item['name']}!"
            self._shop_toast_timer = 1500
            self._sfx("shop_buy")
            if self._ach_manager:
                self._ach_manager.unlock("apothecary")

    def _draw_apothecary(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 440, 300
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        m = 16

        # Panel background
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 2, border_radius=8)

        # Header
        title = self.font_prompt.render("Apothecary", True, GOLD)
        self.screen.blit(title, (px + m, py + 10))
        gold_text = f"\u25cf Gold: {self.player.gold}"
        gold_surf = self.font_card_name.render(gold_text, True, GOLD)
        self.screen.blit(gold_surf, (px + panel_w - gold_surf.get_width() - m, py + 12))

        # Separator
        sep_y = py + 10 + title.get_height() + 6
        pygame.draw.line(self.screen, NEON_CYAN_DIM, (px + m, sep_y), (px + panel_w - m, sep_y), 1)

        # Item rows
        row_y = sep_y + 12
        item_h = 58
        item_gap = 6
        row_w = panel_w - 2 * m

        for i, item in enumerate(SHOP_ITEMS):
            iy = row_y + i * (item_h + item_gap)
            selected = i == self._shop_cursor

            # Row background
            if selected:
                pulse = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.007)
                hl_color = GOLD if self._shop_confirming else NEON_CYAN
                row_bg = pygame.Surface((row_w, item_h), pygame.SRCALPHA)
                row_bg.fill((*hl_color, int(30 * pulse)))
                self.screen.blit(row_bg, (px + m, iy))
                pygame.draw.rect(self.screen, hl_color, (px + m, iy, row_w, item_h), 1, border_radius=5)
            else:
                row_bg = pygame.Surface((row_w, item_h), pygame.SRCALPHA)
                row_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 80))
                self.screen.blit(row_bg, (px + m, iy))

            # Item name
            if selected:
                name_color = GOLD if self._shop_confirming else NEON_CYAN
                name_text = f"> {item['name']}"
            else:
                name_text = item["name"]
                name_color = WHITE

            name_surf = self.font_inv_item.render(name_text, True, name_color)
            self.screen.blit(name_surf, (px + m + 10, iy + 6))

            # Description
            desc_surf = self.font_card_desc.render(item["desc"], True, DIM_WHITE)
            self.screen.blit(desc_surf, (px + m + 10, iy + 28))

            # Cost
            can_afford = self.player.gold >= item["cost"]
            cost_color = GOLD if can_afford else RED
            cost_text = f"Cost: {item['cost']}g"
            cost_surf = self.font_card_name.render(cost_text, True, cost_color)
            self.screen.blit(cost_surf, (px + panel_w - cost_surf.get_width() - m - 8, iy + 8))

        # Toast, confirm prompt, or hint
        hint_y = py + panel_h - 28
        if self._shop_toast_timer > 0:
            is_good = "Purchased" in self._shop_toast_text
            toast_surf = self.font_small.render(self._shop_toast_text, True, GREEN if is_good else RED)
            self.screen.blit(toast_surf, (px + (panel_w - toast_surf.get_width()) // 2, hint_y))
        elif self._shop_confirming:
            confirm_text = f"Buy {SHOP_ITEMS[self._shop_cursor]['name']} for {SHOP_ITEMS[self._shop_cursor]['cost']}g?  Press ENTER to confirm"
            confirm_surf = self.font_small.render(confirm_text, True, GOLD)
            self.screen.blit(confirm_surf, (px + (panel_w - confirm_surf.get_width()) // 2, hint_y))
        else:
            hint = self.font_hint.render("[W/S] Navigate   [ENTER] Buy   [ESC] Back", True, (100, 100, 130))
            self.screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, hint_y))

    # ------------------------------------------------------------------ #
    #  Gear Merchant                                                     #
    # ------------------------------------------------------------------ #

    def _enter_merchant(self):
        from item import LootGenerator, Consumable
        self._merchant_stock = []
        stock_size = random.randint(4, 6)
        for _ in range(stock_size):
            item = LootGenerator.generate(floor=max(1, self.player.level))
            if not isinstance(item, Consumable):
                self._merchant_stock.append(item)
        self._merchant_cursor = 0
        self._merchant_confirming = False
        self.sub_state = HubSubState.MERCHANT

    def merchant_move_up(self):
        if self.sub_state != HubSubState.MERCHANT:
            return
        self._merchant_confirming = False
        self._merchant_cursor = (self._merchant_cursor - 1) % len(self._merchant_stock)

    def merchant_move_down(self):
        if self.sub_state != HubSubState.MERCHANT:
            return
        self._merchant_confirming = False
        self._merchant_cursor = (self._merchant_cursor + 1) % len(self._merchant_stock)

    def merchant_buy(self):
        if self.sub_state != HubSubState.MERCHANT:
            return
        items = self._merchant_stock
        if not items:
            return
        item = items[self._merchant_cursor]
        price = self._merchant_price(item)

        if not self._merchant_confirming:
            if self.player.gold < price:
                self._sfx("error")
                self._merchant_toast_text = "Not enough gold!"
                self._merchant_toast_timer = 1500
                return
            self._merchant_confirming = True
            return

        # Second press — buy
        self._merchant_confirming = False
        if self.player.gold >= price:
            self.player.gold -= price
            self.player.inventory.append(item)
            self._merchant_stock.pop(self._merchant_cursor)
            self._merchant_toast_text = f"Purchased {item.name}!"
            self._merchant_toast_timer = 1500
            self._sfx("shop_buy")
            if self._merchant_cursor >= len(self._merchant_stock) and self._merchant_stock:
                self._merchant_cursor = len(self._merchant_stock) - 1
            if self._ach_manager:
                self._ach_manager.unlock("spendthrift")

    def _merchant_price(self, item) -> int:
        """Merchant sells at ~2x sell price."""
        base = {Rarity.COMMON: 20, Rarity.RARE: 50, Rarity.EPIC: 120, Rarity.LEGENDARY: 300}
        b = base.get(item.rarity, 20)
        if isinstance(item, Weapon):
            stat_value = item.atk
        elif isinstance(item, Armor):
            stat_value = item.defense
        else:
            stat_value = 0
            for stat, value in getattr(item, "stat_modifier", {}).items():
                stat_value += int(value * 100) if stat in ("acc", "eva", "crit") else int(value)
        return int(b * (1 + stat_value / 8))

    def _draw_merchant(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 500, 380
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        m = 16

        # Panel background
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 2, border_radius=8)

        # Header
        title = self.font_prompt.render("Merchant", True, GOLD)
        self.screen.blit(title, (px + m, py + 10))
        gold_text = f"\u25cf Gold: {self.player.gold}"
        gold_surf = self.font_card_name.render(gold_text, True, GOLD)
        self.screen.blit(gold_surf, (px + panel_w - gold_surf.get_width() - m, py + 12))

        # Separator
        sep_y = py + 10 + title.get_height() + 6
        pygame.draw.line(self.screen, NEON_CYAN_DIM, (px + m, sep_y), (px + panel_w - m, sep_y), 1)

        # Stock list
        row_y = sep_y + 12
        item_h = 54
        item_gap = 6
        row_w = panel_w - 2 * m

        if not self._merchant_stock:
            empty = self.font_inv_item.render("All out of stock — check back later!", True, DIM_WHITE)
            self.screen.blit(empty, (px + m + 10, row_y + 20))
        else:
            for i, item in enumerate(self._merchant_stock):
                iy = row_y + i * (item_h + item_gap)
                selected = i == self._merchant_cursor

                # Row background
                if selected:
                    pulse = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.007)
                    hl_color = GOLD if self._merchant_confirming else NEON_CYAN
                    row_bg = pygame.Surface((row_w, item_h), pygame.SRCALPHA)
                    row_bg.fill((*hl_color, int(30 * pulse)))
                    self.screen.blit(row_bg, (px + m, iy))
                    pygame.draw.rect(self.screen, hl_color, (px + m, iy, row_w, item_h), 1, border_radius=5)
                else:
                    row_bg = pygame.Surface((row_w, item_h), pygame.SRCALPHA)
                    row_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 80))
                    self.screen.blit(row_bg, (px + m, iy))

                # Item name with rarity color
                rarity_c = RARITY_COLOR.get(item.rarity, WHITE)
                name_text = f"> {item.name}" if selected else item.name
                name_color = (GOLD if self._merchant_confirming else NEON_CYAN) if selected else rarity_c
                name_surf = self.font_inv_item.render(name_text, True, name_color)
                self.screen.blit(name_surf, (px + m + 10, iy + 6))

                # Stats
                stat_parts = []
                for stat, value in item.stat_modifier.items():
                    if stat in ("acc", "eva"):
                        stat_parts.append(f"+{int(value * 100)}% {stat.upper()}")
                    else:
                        stat_parts.append(f"+{value} {stat.upper()}")
                stat_text = "  ".join(stat_parts)
                stat_surf = self.font_card_desc.render(stat_text, True, DIM_WHITE)
                self.screen.blit(stat_surf, (px + m + 10, iy + 28))

                # Price
                price = self._merchant_price(item)
                can_afford = self.player.gold >= price
                cost_color = GOLD if can_afford else RED
                cost_text = f"{price}g"
                cost_surf = self.font_card_name.render(cost_text, True, cost_color)
                self.screen.blit(cost_surf, (px + panel_w - cost_surf.get_width() - m - 8, iy + 14))

        # Toast, confirm prompt, or hint
        hint_y = py + panel_h - 28
        if self._merchant_toast_timer > 0:
            is_good = "Purchased" in self._merchant_toast_text
            toast_surf = self.font_small.render(self._merchant_toast_text, True, GREEN if is_good else RED)
            self.screen.blit(toast_surf, (px + (panel_w - toast_surf.get_width()) // 2, hint_y))
        elif self._merchant_confirming and self._merchant_stock:
            item = self._merchant_stock[self._merchant_cursor]
            price = self._merchant_price(item)
            confirm_text = f"Buy {item.name} for {price}g?  Press ENTER to confirm"
            confirm_surf = self.font_small.render(confirm_text, True, GOLD)
            self.screen.blit(confirm_surf, (px + (panel_w - confirm_surf.get_width()) // 2, hint_y))
        else:
            hint = self.font_hint.render("[W/S] Navigate   [ENTER] Buy   [ESC] Back", True, (100, 100, 130))
            self.screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, hint_y))

    # ------------------------------------------------------------------ #
    #  Guild Hall                                                        #
    # ------------------------------------------------------------------ #

    def _enter_guild_hall(self):
        self._guild_tab = 0
        self._bestiary_cursor = 0
        self._bestiary_scroll_offset = 0
        self._quest_cursor = 0
        self._quest_scroll_offset = 0
        self._respec_tree_index = 0
        self._respec_confirming = False
        self.sub_state = HubSubState.GUILD_HALL

    def guild_move_left(self):
        if self.sub_state != HubSubState.GUILD_HALL:
            return
        self._respec_confirming = False
        self._guild_tab = (self._guild_tab - 1) % 3

    def guild_move_right(self):
        if self.sub_state != HubSubState.GUILD_HALL:
            return
        self._respec_confirming = False
        self._guild_tab = (self._guild_tab + 1) % 3

    def guild_move_up(self):
        if self.sub_state != HubSubState.GUILD_HALL:
            return
        if self._guild_tab == 0 and self._bestiary:
            keys = list(self._bestiary.entries.keys())
            if keys:
                self._bestiary_cursor = (self._bestiary_cursor - 1) % len(keys)
        elif self._guild_tab == 1 and self._quests:
            if self._quests.active_quests:
                self._quest_cursor = (self._quest_cursor - 1) % len(self._quests.active_quests)
        elif self._guild_tab == 2:
            trees = SkillRegistry.get_trees_for_class(self.player.player_class)
            if trees:
                self._respec_tree_index = (self._respec_tree_index - 1) % len(trees)

    def guild_move_down(self):
        if self.sub_state != HubSubState.GUILD_HALL:
            return
        if self._guild_tab == 0 and self._bestiary:
            keys = list(self._bestiary.entries.keys())
            if keys:
                self._bestiary_cursor = (self._bestiary_cursor + 1) % len(keys)
        elif self._guild_tab == 1 and self._quests:
            if self._quests.active_quests:
                self._quest_cursor = (self._quest_cursor + 1) % len(self._quests.active_quests)
        elif self._guild_tab == 2:
            trees = SkillRegistry.get_trees_for_class(self.player.player_class)
            if trees:
                self._respec_tree_index = (self._respec_tree_index + 1) % len(trees)

    def guild_confirm(self):
        if self.sub_state != HubSubState.GUILD_HALL:
            return
        if self._guild_tab == 1 and self._quests:
            return self._claim_selected_quest()
        if self._guild_tab == 2:
            return self._confirm_respec()

    def _claim_selected_quest(self):
        if not self._quests or not self._quests.active_quests:
            return
        reward = self._quests.claim_quest(self._quest_cursor, self.player)
        if reward:
            kind = reward["kind"]
            if kind == "gold":
                self._toast_text = f"Quest complete! +{reward['value']} gold."
            elif kind == "xp":
                self._toast_text = f"Quest complete! +{reward['value']} XP."
            else:
                self._toast_text = "Quest complete! Reward claimed."
            self.sub_state = HubSubState.TOAST
            self._toast_timer = 0
            if self._ach_manager:
                self._ach_manager.inc("quests_completed")
                self._ach_manager.unlock("quest_master")

    def _confirm_respec(self):
        trees = SkillRegistry.get_trees_for_class(self.player.player_class)
        if not trees:
            return
        if len(trees) == 1:
            return
        selected_tree = trees[self._respec_tree_index]
        cost = self._respec_cost()
        if not self._respec_confirming:
            self._respec_confirming = True
            return
        self._respec_confirming = False
        if self.player.gold < cost:
            self._sfx("error")
            self._toast_text = "Not enough gold!"
            self._toast_timer = 0
            self.sub_state = HubSubState.TOAST
            return
        if self.player.chosen_tree == selected_tree:
            self._toast_text = "That tree is already equipped."
            self._toast_timer = 0
            self.sub_state = HubSubState.TOAST
            return
        self.player.gold -= cost
        self.player.chosen_tree = selected_tree
        self._toast_text = f"Respecced to {selected_tree.value}!"
        self._toast_timer = 0
        self.sub_state = HubSubState.TOAST

    def _respec_cost(self) -> int:
        return 75 + self.player.level * 25

    # ------------------------------------------------------------------ #
    #  Smithy inventory overlay                                          #
    # ------------------------------------------------------------------ #

    def _enter_smithy(self):
        self._inv_cursor = 0
        self._inv_scroll_offset = 0
        self._sell_confirming = False
        self._upgrade_confirming = False
        self._smithy_mode = "sell"
        self.sub_state = HubSubState.SMITHY_INVENTORY

    def _draw_smithy_inventory(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 600, 430
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        m = 16

        # Panel
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 2, border_radius=8)

        # Title + gold
        mode_label = "Sell Gear" if self._smithy_mode == "sell" else "Upgrade Gear"
        title = self.font_inv_title.render(f"Smithy - {mode_label}", True, NEON_CYAN)
        self.screen.blit(title, (px + m, py + 10))
        gold_text = f"* {self.player.gold}g"
        gold_surf = self.font_card_name.render(gold_text, True, GOLD)
        self.screen.blit(gold_surf, (px + panel_w - gold_surf.get_width() - m, py + 12))

        # Separator
        sep_y = py + 10 + title.get_height() + 6
        pygame.draw.line(self.screen, NEON_CYAN_DIM, (px + m, sep_y), (px + panel_w - m, sep_y), 1)

        # Equipment section (view-only)
        eq_y = sep_y + 10
        p = self.player
        weapon = p.equipment.get("weapon")
        armor = p.equipment.get("armor")
        ring = p.equipment.get("ring")
        amulet = p.equipment.get("amulet")

        eq_label = self.font_inv_section.render("EQUIPPED", True, DIM_WHITE)
        self.screen.blit(eq_label, (px + m, eq_y))

        eq_ry = eq_y + 22
        row_w = panel_w - 2 * m
        eq_col_w = (row_w - 8) // 2
        left_col_x = px + m + 4
        right_col_x = left_col_x + eq_col_w + 8
        left_lines = []
        right_lines = []

        if weapon:
            left_lines.append((f"W: {weapon.name}  +{weapon.atk} ATK", RARITY_COLOR.get(weapon.rarity, WHITE)))
        if armor:
            left_lines.append((f"A: {armor.name}  +{armor.defense} DEF", RARITY_COLOR.get(armor.rarity, WHITE)))
        if ring:
            ring_stats = "  ".join(
                f"+{int(value * 100)}% {stat.upper()}" if stat in ("acc", "eva", "crit")
                else f"+{value} {stat.upper()}"
                for stat, value in ring.stat_modifier.items()
            )
            right_lines.append((f"R: {ring.name}  {ring_stats}".strip(), RARITY_COLOR.get(ring.rarity, WHITE)))
        if amulet:
            amulet_stats = "  ".join(
                f"+{int(value * 100)}% {stat.upper()}" if stat in ("acc", "eva", "crit")
                else f"+{value} {stat.upper()}"
                for stat, value in amulet.stat_modifier.items()
            )
            right_lines.append((f"M: {amulet.name}  {amulet_stats}".strip(), RARITY_COLOR.get(amulet.rarity, WHITE)))

        if not left_lines:
            left_lines.append(("(empty)", (80, 80, 100)))
        if not right_lines:
            right_lines.append(("No accessories equipped", (80, 80, 100)))

        for idx, (text, color) in enumerate(left_lines[:2]):
            surf = self.font_card_desc.render(text, True, color)
            self.screen.blit(surf, (left_col_x, eq_ry + idx * 18))
        for idx, (text, color) in enumerate(right_lines[:2]):
            surf = self.font_card_desc.render(text, True, color)
            self.screen.blit(surf, (right_col_x, eq_ry + idx * 18))
        eq_ry += 38

        # Set bonuses
        active_sets = p.get_active_sets()
        if active_sets:
            eq_ry += 4
            for set_data in active_sets.values():
                set_text = f"SET: {set_data['description']}"
                set_surf = self.font_card_desc.render(set_text, True, GOLD)
                self.screen.blit(set_surf, (px + m + 4, eq_ry))
                eq_ry += 16

        eq_ry += 4

        # Bag section
        bag_label_text = "BAG - Sell Mode" if self._smithy_mode == "sell" else "BAG - Upgrade Mode"
        bag_label = self.font_inv_section.render(bag_label_text, True, GOLD)
        self.screen.blit(bag_label, (px + m, eq_ry))
        eq_ry += 22

        bag_zone_top = eq_ry
        bag_zone_bottom = py + panel_h - m - 30
        bag_zone_h = bag_zone_bottom - bag_zone_top
        pygame.draw.rect(self.screen, (*NEON_CYAN_DIM[:3], 80),
                         (px + m - 4, bag_zone_top - 2, row_w + 8, bag_zone_h + 4), 1, border_radius=4)

        clip_rect = pygame.Rect(px + m, bag_zone_top, row_w, bag_zone_h)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        inv = p.inventory
        item_h = 36
        item_pad = 4
        max_visible = max(1, bag_zone_h // (item_h + item_pad))

        # Clamp scroll
        if self._inv_scroll_offset > self._inv_cursor:
            self._inv_scroll_offset = self._inv_cursor
        elif self._inv_cursor >= self._inv_scroll_offset + max_visible:
            self._inv_scroll_offset = self._inv_cursor - max_visible + 1

        if not inv:
            empty = self.font_inv_item.render("  No gear in bag.", True, (80, 80, 100))
            self.screen.blit(empty, (px + m + 4, bag_zone_top + 6))
        else:
            scroll = self._inv_scroll_offset
            visible = min(len(inv), scroll + max_visible)
            for i in range(scroll, visible):
                v = i - scroll
                iy = bag_zone_top + 4 + v * (item_h + item_pad)
                if iy + item_h > bag_zone_bottom:
                    break
                item = inv[i]
                sel = i == self._inv_cursor
                self._draw_sell_item_row(px + m, iy, row_w, item_h, item, sel)

            if visible < len(inv):
                remaining = len(inv) - visible
                more_y = bag_zone_top + 4 + (visible - scroll) * (item_h + item_pad)
                if more_y + item_h <= bag_zone_bottom:
                    more = self.font_small.render(f"+{remaining} more...", True, DIM_WHITE)
                    self.screen.blit(more, (px + m + 4, more_y + (item_h - more.get_height()) // 2))

        self.screen.set_clip(old_clip)

        # Toast or hint
        hint_y = py + panel_h - 24
        if self._sell_toast_timer > 0:
            toast = self.font_small.render(self._sell_toast_text, True, GOLD)
            self.screen.blit(toast, (px + (panel_w - toast.get_width()) // 2, hint_y))
        elif self._upgrade_toast_timer > 0:
            toast = self.font_small.render(self._upgrade_toast_text, True, GOLD)
            self.screen.blit(toast, (px + (panel_w - toast.get_width()) // 2, hint_y))
        elif self._sell_confirming:
            item = inv[self._inv_cursor] if inv else None
            if item:
                price = self._sell_price(item)
                confirm = self.font_small.render(f"Sell {item.name} for {price}g?  Press ENTER to confirm", True, GOLD)
                self.screen.blit(confirm, (px + (panel_w - confirm.get_width()) // 2, hint_y))
        elif self._upgrade_confirming:
            item = inv[self._inv_cursor] if inv else None
            if item:
                price = self._upgrade_price(item)
                confirm = self.font_small.render(f"Upgrade {item.name} for {price}g?  Press ENTER to confirm", True, GOLD)
                self.screen.blit(confirm, (px + (panel_w - confirm.get_width()) // 2, hint_y))
        else:
            if self._smithy_mode == "sell":
                hints = "W/S: Navigate   ENTER: Sell   F: Sort   TAB: Switch Mode   ESC: Back"
            else:
                hints = "W/S: Navigate   ENTER: Upgrade   TAB: Switch Mode   ESC: Back"
            hint_surf = self.font_inv_hint.render(hints, True, (100, 100, 130))
            self.screen.blit(hint_surf, (px + (panel_w - hint_surf.get_width()) // 2, hint_y))

    def _draw_sell_item_row(self, x, y, w, h, item, selected):
        rarity_c = RARITY_COLOR.get(item.rarity, WHITE)
        accent_c = RARITY_ACCENT.get(item.rarity, (60, 60, 75))
        if self._smithy_mode == "upgrade":
            price = self._upgrade_price(item)
            price_text = f"[{price}g]"
        else:
            price = self._sell_price(item)
            price_text = f"[{price}g]"
        stat_parts = []
        for stat, value in item.stat_modifier.items():
            if stat in ("acc", "eva", "crit"):
                stat_parts.append(f"+{int(value * 100)}% {stat.upper()}")
            elif stat == "sp":
                stat_parts.append(f"+{value} SP")
            else:
                stat_parts.append(f"+{value} {stat.upper()}")
        stat_val = "  ".join(stat_parts) if stat_parts else "No stats"

        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.008)
            sel_bg = pygame.Surface((w, h), pygame.SRCALPHA)
            sel_bg.fill((*NEON_CYAN, int(30 * pulse)))
            self.screen.blit(sel_bg, (x, y))

        # Rarity bar
        pygame.draw.rect(self.screen, accent_c, (x + 4, y + 6, 3, h - 12), border_radius=1)

        # Item name + stats
        name_text = f"{item.name}  [{stat_val}]"
        if selected:
            name_text = f"> {name_text}"
            name_color = NEON_CYAN
        else:
            name_color = rarity_c
        name_surf = self.font_inv_item.render(name_text, True, name_color)
        self.screen.blit(name_surf, (x + 12, y + (h - name_surf.get_height()) // 2))

        # Sell price
        price_surf = self.font_card_name.render(price_text, True, GOLD)
        self.screen.blit(price_surf, (x + w - price_surf.get_width() - 10, y + (h - price_surf.get_height()) // 2))
    @staticmethod
    def _truncate(text: str, font, max_w: int) -> str:
        if font.size(text)[0] <= max_w:
            return text
        while text and font.size(text + "...")[0] > max_w:
            text = text[:-1]
        return text + "..."

    # ------------------------------------------------------------------ #
    #  Achievement viewer                                                #
    # ------------------------------------------------------------------ #

    def _enter_achievements(self):
        self._ach_cursor = 0
        self._ach_scroll_offset = 0
        self.sub_state = HubSubState.ACHIEVEMENTS

    def achievements_move_up(self):
        if self.sub_state != HubSubState.ACHIEVEMENTS:
            return
        defs = achievements.ACHIEVEMENT_DEFS
        if not defs:
            return
        self._ach_cursor = (self._ach_cursor - 1) % len(defs)
        if self._ach_cursor < self._ach_scroll_offset:
            self._ach_scroll_offset = self._ach_cursor

    def achievements_move_down(self):
        if self.sub_state != HubSubState.ACHIEVEMENTS:
            return
        defs = achievements.ACHIEVEMENT_DEFS
        if not defs:
            return
        self._ach_cursor = (self._ach_cursor + 1) % len(defs)
        max_visible = 5  # approximate; refined in draw
        if self._ach_cursor >= self._ach_scroll_offset + max_visible:
            self._ach_scroll_offset = self._ach_cursor - max_visible + 1

    def _draw_achievements(self):
        defs = achievements.ACHIEVEMENT_DEFS
        if not defs:
            return

        # Dark translucent overlay
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Title
        title = self.font_banner.render("ACHIEVEMENTS", True, GOLD)
        tx = (self.w - title.get_width()) // 2
        ty = 20
        self.screen.blit(title, (tx, ty))

        # Progress counter
        total = len(defs)
        unlocked_count = len(self._ach_manager.unlocked) if self._ach_manager else 0
        progress_text = f"{unlocked_count} / {total} Unlocked"
        progress_surf = self.font_small.render(progress_text, True, DIM_WHITE)
        px = (self.w - progress_surf.get_width()) // 2
        py = ty + title.get_height() + 4
        self.screen.blit(progress_surf, (px, py))

        # List layout
        list_top = py + progress_surf.get_height() + 16
        list_bottom = self.h - 40  # room for hint
        list_h = list_bottom - list_top
        card_h = 82
        card_gap = 8
        card_w = 700
        card_x = (self.w - card_w) // 2

        max_visible = max(1, list_h // (card_h + card_gap))

        # Clamp scroll offset
        max_scroll = max(0, len(defs) - max_visible)
        self._ach_scroll_offset = max(0, min(self._ach_scroll_offset, max_scroll))
        if self._ach_cursor < self._ach_scroll_offset:
            self._ach_scroll_offset = self._ach_cursor
        if self._ach_cursor >= self._ach_scroll_offset + max_visible:
            self._ach_scroll_offset = self._ach_cursor - max_visible + 1
        self._ach_scroll_offset = max(0, min(self._ach_scroll_offset, max_scroll))

        # Hint
        hint = self.font_hint.render("[W/S] Scroll   [ENTER/ESC] Close", True, (100, 100, 130))
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, list_bottom + 12))

        # Clip list area
        clip_rect = pygame.Rect(card_x, list_top, card_w, list_h)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        for i, ach in enumerate(defs):
            cy = list_top + i * (card_h + card_gap) - self._ach_scroll_offset * (card_h + card_gap)
            if cy + card_h < list_top or cy > list_bottom:
                continue

            is_unlocked = self._ach_manager and ach["id"] in self._ach_manager.unlocked
            is_selected = i == self._ach_cursor

            # Card background
            card_bg = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            bg_alpha = 200 if is_selected else 160
            card_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], bg_alpha))
            self.screen.blit(card_bg, (card_x, cy))

            # Border
            border_color = NEON_CYAN if is_selected else NEON_CYAN_DIM
            pygame.draw.rect(self.screen, border_color, (card_x, cy, card_w, card_h), 1, border_radius=6)

            # Selection pulse
            if is_selected:
                pulse = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.005)
                sel_overlay = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                sel_overlay.fill((*NEON_CYAN, int(20 * pulse)))
                self.screen.blit(sel_overlay, (card_x, cy))

            # Icon (emoji)
            icon_color = GOLD if is_unlocked else (100, 100, 110)
            icon_surf = self.font_icon.render(ach.get("icon", "🏆"), True, icon_color)
            ix = card_x + 20
            iy = cy + (card_h - icon_surf.get_height()) // 2
            self.screen.blit(icon_surf, (ix, iy))

            # Name
            name_color = GOLD if is_unlocked else WHITE
            name_surf = self.font_card_name.render(ach["name"], True, name_color)
            nx = card_x + 70
            ny = cy + 14
            self.screen.blit(name_surf, (nx, ny))

            # Description
            desc_surf = self.font_card_desc.render(ach["desc"], True, DIM_WHITE)
            self.screen.blit(desc_surf, (nx, ny + name_surf.get_height() + 4))

            # Progress bar or UNLOCKED badge
            if is_unlocked:
                badge_text = "UNLOCKED"
                badge_surf = self.font_small.render(badge_text, True, GOLD)
                bx = card_x + card_w - badge_surf.get_width() - 18
                by = cy + card_h - badge_surf.get_height() - 14
                self.screen.blit(badge_surf, (bx, by))
            else:
                counter = ach.get("counter")
                threshold = ach.get("threshold")
                if counter and threshold:
                    current = self._ach_manager.counters.get(counter, 0) if self._ach_manager else 0
                    progress = min(1.0, current / threshold) if threshold > 0 else 0.0

                    bar_w = 140
                    bar_h = 8
                    bar_x = card_x + card_w - bar_w - 18
                    bar_y = cy + card_h - 28

                    # Bar bg
                    pygame.draw.rect(self.screen, (30, 30, 45), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
                    # Bar fill
                    fill_w = int(bar_w * progress)
                    if fill_w > 0:
                        pygame.draw.rect(self.screen, NEON_CYAN, (bar_x, bar_y, fill_w, bar_h), border_radius=4)

                    # Text
                    prog_text = f"{current} / {threshold}"
                    prog_surf = self.font_small.render(prog_text, True, DIM_WHITE)
                    self.screen.blit(prog_surf, (bar_x + bar_w - prog_surf.get_width(), bar_y - prog_surf.get_height() - 2))

        self.screen.set_clip(old_clip)

    def _draw_guild_hall(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 740, 450
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        m = 16

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 228))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 2, border_radius=8)

        title = self.font_banner.render("GUILD HALL", True, GOLD)
        self.screen.blit(title, (px + m, py + 10))
        gold_text = f"Gold: {self.player.gold}"
        gold_surf = self.font_card_name.render(gold_text, True, GOLD)
        self.screen.blit(gold_surf, (px + panel_w - gold_surf.get_width() - m, py + 16))

        # Tabs
        tabs = ["Bestiary", "Quests", "Respec"]
        tab_y = py + 60
        tab_w = 112
        tab_gap = 10
        total_tabs_w = len(tabs) * tab_w + (len(tabs) - 1) * tab_gap
        tab_x = px + (panel_w - total_tabs_w) // 2
        for i, label in enumerate(tabs):
            rx = tab_x + i * (tab_w + tab_gap)
            selected = i == self._guild_tab
            tab_bg = pygame.Surface((tab_w, 34), pygame.SRCALPHA)
            tab_bg.fill((*NEON_CYAN, 65 if selected else 25))
            self.screen.blit(tab_bg, (rx, tab_y))
            pygame.draw.rect(self.screen, NEON_CYAN if selected else NEON_CYAN_DIM, (rx, tab_y, tab_w, 34), 2, border_radius=5)
            label_surf = self.font_small.render(label, True, GOLD if selected else DIM_WHITE)
            self.screen.blit(label_surf, (rx + (tab_w - label_surf.get_width()) // 2, tab_y + 8))

        content_top = tab_y + 50
        content_h = panel_h - (content_top - py) - 48
        content_w = panel_w - 2 * m
        left_w = int(content_w * 0.49)
        right_w = content_w - left_w - 14
        left_x = px + m
        right_x = left_x + left_w + 14

        # Panels
        pygame.draw.rect(self.screen, (30, 30, 45), (left_x, content_top, left_w, content_h), 1, border_radius=6)
        pygame.draw.rect(self.screen, (30, 30, 45), (right_x, content_top, right_w, content_h), 1, border_radius=6)

        if self._guild_tab == 0:
            self._draw_bestiary_tab(left_x, content_top, left_w, content_h, right_x, right_w)
        elif self._guild_tab == 1:
            self._draw_quests_tab(left_x, content_top, left_w, content_h, right_x, right_w)
        else:
            self._draw_respec_tab(left_x, content_top, left_w, content_h, right_x, right_w)

        hint = self.font_hint.render("[A/D] Tabs   [W/S] Move   [ENTER] Select   [ESC] Back", True, (100, 100, 130))
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, py + panel_h - 24))

    def _draw_bestiary_tab(self, left_x, top_y, left_w, content_h, right_x, right_w):
        if not self._bestiary:
            empty = self.font_card_name.render("Bestiary data unavailable.", True, DIM_WHITE)
            self.screen.blit(empty, (left_x + 12, top_y + 12))
            return

        entries = list(self._bestiary.entries.values())
        if not entries:
            return

        visible = 4
        if self._bestiary_cursor < self._bestiary_scroll_offset:
            self._bestiary_scroll_offset = self._bestiary_cursor
        elif self._bestiary_cursor >= self._bestiary_scroll_offset + visible:
            self._bestiary_scroll_offset = self._bestiary_cursor - visible + 1
        self._bestiary_scroll_offset = max(0, min(self._bestiary_scroll_offset, max(0, len(entries) - visible)))

        title = self.font_inv_section.render(f"Encounters: {self._bestiary.encountered_count()}/{len(entries)}", True, GOLD)
        self.screen.blit(title, (left_x + 12, top_y + 10))
        if self._bestiary.is_complete():
            complete = self.font_small.render("Bestiary complete!", True, GOLD)
            self.screen.blit(complete, (left_x + 12 + title.get_width() + 10, top_y + 12))

        row_y = top_y + 40
        row_h = 42
        for idx in range(self._bestiary_scroll_offset, min(len(entries), self._bestiary_scroll_offset + visible)):
            entry = entries[idx]
            y = row_y + (idx - self._bestiary_scroll_offset) * row_h
            selected = idx == self._bestiary_cursor
            if selected:
                pygame.draw.rect(self.screen, (*NEON_CYAN, 40), (left_x + 8, y, left_w - 16, row_h - 2), border_radius=4)
            name_color = GOLD if entry["encountered"] else DIM_WHITE
            name_surf = self.font_card_name.render(entry["name"], True, name_color)
            self.screen.blit(name_surf, (left_x + 12, y + 6))
            meta = f"Kills: {entry['kills']}"
            if entry["first_floor"] is not None:
                meta += f"  |  First floor: {entry['first_floor']}"
            meta_surf = self.font_small.render(meta, True, DIM_WHITE)
            self.screen.blit(meta_surf, (left_x + 12, y + 22))

        entry = entries[self._bestiary_cursor]
        detail_title = self.font_inv_section.render("Details", True, GOLD)
        self.screen.blit(detail_title, (right_x + 12, top_y + 10))
        lines = [
            f"Name: {entry['name']}",
            f"Encountered: {'Yes' if entry['encountered'] else 'No'}",
            f"Kills: {entry['kills']}",
            f"First floor: {entry['first_floor'] if entry['first_floor'] is not None else '-'}",
            f"HP: {entry['hp']}",
            f"ATK: {entry['atk']}",
            f"DEF: {entry['defn']}",
            f"EVA: {int(entry['eva'] * 100)}%",
            f"XP reward: {entry['xp_reward']}",
        ]
        dy = top_y + 42
        for line in lines:
            surf = self.font_small.render(line, True, WHITE)
            self.screen.blit(surf, (right_x + 12, dy))
            dy += 22

    def _draw_quests_tab(self, left_x, top_y, left_w, content_h, right_x, right_w):
        if not self._quests:
            empty = self.font_card_name.render("Quest board unavailable.", True, DIM_WHITE)
            self.screen.blit(empty, (left_x + 12, top_y + 12))
            return

        quests = self._quests.active_quests
        title = self.font_inv_section.render(f"Completed: {self._quests.completed_quests}", True, GOLD)
        self.screen.blit(title, (left_x + 12, top_y + 10))

        visible = 3
        if quests:
            if self._quest_cursor < self._quest_scroll_offset:
                self._quest_scroll_offset = self._quest_cursor
            elif self._quest_cursor >= self._quest_scroll_offset + visible:
                self._quest_scroll_offset = self._quest_cursor - visible + 1
            self._quest_scroll_offset = max(0, min(self._quest_scroll_offset, max(0, len(quests) - visible)))

            row_y = top_y + 38
            row_h = 88
            for idx in range(self._quest_scroll_offset, min(len(quests), self._quest_scroll_offset + visible)):
                quest = quests[idx]
                y = row_y + (idx - self._quest_scroll_offset) * row_h
                selected = idx == self._quest_cursor
                if selected:
                    pygame.draw.rect(self.screen, (*NEON_CYAN, 40), (left_x + 8, y, left_w - 16, row_h - 4), border_radius=4)
                label = quest["description"]
                q_surf = self.font_card_name.render(label, True, GOLD if quest["completed"] else WHITE)
                self.screen.blit(q_surf, (left_x + 12, y + 8))
                prog = f"{quest['progress']} / {quest['target']}"
                prog_surf = self.font_small.render(prog, True, DIM_WHITE)
                self.screen.blit(prog_surf, (left_x + 12, y + 34))
                reward = f"Reward: {quest['reward_kind'].replace('_', ' ').title()}"
                reward_surf = self.font_small.render(reward, True, DIM_WHITE)
                self.screen.blit(reward_surf, (left_x + 12, y + 54))
                if quest["completed"]:
                    badge = self.font_small.render("READY TO CLAIM", True, GOLD)
                    self.screen.blit(badge, (left_x + left_w - badge.get_width() - 16, y + 58))
        else:
            empty = self.font_card_name.render("No active quests.", True, DIM_WHITE)
            self.screen.blit(empty, (left_x + 12, top_y + 60))

        quest = quests[self._quest_cursor] if quests else None
        detail_title = self.font_inv_section.render("Quest Details", True, GOLD)
        self.screen.blit(detail_title, (right_x + 12, top_y + 10))
        if quest:
            lines = [
                f"Type: {quest['type'].title()}",
                f"Target: {quest['target']}",
                f"Progress: {quest['progress']} / {quest['target']}",
                f"Reward: {quest['reward_kind'].replace('_', ' ').title()}",
            ]
            if quest["type"] == "hunt":
                lines.append(f"Enemy: {quest.get('enemy_name', 'Unknown')}")
            if quest["type"] == "collect":
                lines.append(f"Minimum rarity: {quest.get('rarity', 'COMMON')}")
            if quest["type"] == "reach":
                lines.append("Clear the floor to complete.")
            if quest["completed"]:
                lines.append("Press ENTER to claim.")
            dy = top_y + 42
            for line in lines:
                surf = self.font_small.render(line, True, WHITE)
                self.screen.blit(surf, (right_x + 12, dy))
                dy += 22
        else:
            empty = self.font_small.render("No quests available.", True, DIM_WHITE)
            self.screen.blit(empty, (right_x + 12, top_y + 48))

    def _draw_respec_tab(self, left_x, top_y, left_w, content_h, right_x, right_w):
        trees = SkillRegistry.get_trees_for_class(self.player.player_class)
        title = self.font_inv_section.render(f"Class: {self.player.player_class.value}", True, GOLD)
        self.screen.blit(title, (left_x + 12, top_y + 10))
        current_tree = self.player.chosen_tree.value if self.player.chosen_tree else "None"
        current = self.font_small.render(f"Current tree: {current_tree}", True, DIM_WHITE)
        self.screen.blit(current, (left_x + 12, top_y + 34))
        cost = self._respec_cost()

        if trees:
            row_y = top_y + 70
            for i, tree in enumerate(trees):
                y = row_y + i * 54
                selected = i == self._respec_tree_index
                if selected:
                    pygame.draw.rect(self.screen, (*NEON_CYAN, 40), (left_x + 8, y, left_w - 16, 46), border_radius=4)
                color = GOLD if tree == self.player.chosen_tree else WHITE
                tree_surf = self.font_card_name.render(tree.value, True, color)
                self.screen.blit(tree_surf, (left_x + 12, y + 6))
                if tree == self.player.chosen_tree:
                    badge = self.font_small.render("EQUIPPED", True, GOLD)
                    self.screen.blit(badge, (left_x + left_w - badge.get_width() - 16, y + 10))

        detail_title = self.font_inv_section.render("Respec", True, GOLD)
        self.screen.blit(detail_title, (right_x + 12, top_y + 10))
        lines = [
            f"Cost: {cost} gold",
            "Switch to the selected tree.",
            "Press ENTER twice to pay the respec cost.",
        ]
        dy = top_y + 44
        for line in lines:
            surf = self.font_small.render(line, True, WHITE)
            self.screen.blit(surf, (right_x + 12, dy))
            dy += 26

        if self._guild_tab == 2 and trees:
            selected_tree = trees[self._respec_tree_index]
            sel = self.font_card_name.render(f"Selected: {selected_tree.value}", True, NEON_CYAN)
            self.screen.blit(sel, (right_x + 12, dy + 8))
            if self._respec_confirming:
                confirm = self.font_small.render("Press ENTER again to spend the gold.", True, GOLD)
                self.screen.blit(confirm, (right_x + 12, dy + 36))

    # ------------------------------------------------------------------ #
    #  Return prompt                                                     #
    # ------------------------------------------------------------------ #

    def _draw_return_prompt(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 360, 120
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 220))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN_DIM, (px, py, panel_w, panel_h), 1, border_radius=6)

        text = self.font_prompt.render("Return to title?", True, WHITE)
        self.screen.blit(text, ((self.w - text.get_width()) // 2, py + 22))

        yn = self.font_small.render("[Y] Yes   [N] No", True, DIM_WHITE)
        self.screen.blit(yn, ((self.w - yn.get_width()) // 2, py + 62))

    # ------------------------------------------------------------------ #
    #  Toast                                                             #
    # ------------------------------------------------------------------ #

    def _draw_toast(self):
        y = int(self.h * 0.82)
        alpha = min(255, self._toast_timer * 0.8)
        if self._toast_timer > 1200:
            fade = max(0, 255 - (self._toast_timer - 1200) * 0.8)
            alpha = min(alpha, int(fade))

        surf = self.font_toast.render(self._toast_text, True, GREEN)
        alpha_surf = pygame.Surface((surf.get_width() + 30, surf.get_height() + 12), pygame.SRCALPHA)
        alpha_surf.fill((15, 15, 35, min(200, alpha)))
        alpha_surf.blit(surf, (15, 6))
        alpha_surf.set_alpha(min(255, alpha))
        self.screen.blit(alpha_surf, ((self.w - alpha_surf.get_width()) // 2, y - alpha_surf.get_height() // 2))

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                  #
    # ------------------------------------------------------------------ #

    def _do_rest(self):
        restored = False
        if self.player.current_hp < self.player.max_hp:
            self.player.current_hp = self.player.max_hp
            restored = True
        if self.player.sp < self.player.max_sp:
            self.player.sp = self.player.max_sp
            restored = True
        if restored:
            self._toast_text = "HP and SP fully restored!"
        else:
            self._toast_text = "HP and SP already full."
        self.sub_state = HubSubState.TOAST
        self._toast_timer = 0

    def _draw_card_icon(self, icon_type: str, cx: int, cy: int, color):
        """Draw a small procedural icon centered at (cx, cy)."""
        s = pygame.Surface((30, 30), pygame.SRCALPHA)
        if icon_type == "sword":
            # Blade
            pygame.draw.line(s, color, (15, 2), (15, 20), 2)
            # Crossguard
            pygame.draw.line(s, color, (7, 18), (23, 18), 3)
            # Handle
            pygame.draw.line(s, color, (15, 18), (15, 28), 2)
            # Tip
            pygame.draw.polygon(s, color, [(15, 0), (12, 5), (18, 5)])
        elif icon_type == "hammer":
            # Head
            pygame.draw.rect(s, color, (5, 6, 20, 8), border_radius=2)
            # Handle
            pygame.draw.line(s, color, (15, 14), (15, 28), 3)
        elif icon_type == "potion":
            # Neck
            pygame.draw.rect(s, color, (12, 2, 6, 8), border_radius=1)
            # Body
            pygame.draw.ellipse(s, color, (4, 10, 22, 18), width=2)
            # Liquid line
            pygame.draw.arc(s, color, (6, 12, 18, 14), 0.2, 2.9, 2)
        elif icon_type == "moon":
            # Simple bed / rest icon
            pygame.draw.rect(s, color, (4, 16, 22, 8), border_radius=2)
            pygame.draw.rect(s, color, (6, 10, 8, 8), border_radius=2)
        elif icon_type == "book":
            # Open book: two facing pages with center spine
            pygame.draw.rect(s, color, (2, 3, 12, 22), border_radius=1, width=2)
            pygame.draw.rect(s, color, (16, 3, 12, 22), border_radius=1, width=2)
            pygame.draw.line(s, color, (15, 3), (15, 25), 2)
        elif icon_type == "chest":
            # Chest box
            pygame.draw.rect(s, color, (4, 10, 22, 14), border_radius=2, width=2)
            # Lid line
            pygame.draw.line(s, color, (4, 14), (26, 14), 2)
            # Lock
            pygame.draw.rect(s, color, (13, 12, 4, 6), border_radius=1)
            # Sparkle
            pygame.draw.line(s, color, (20, 6), (20, 10), 2)
            pygame.draw.line(s, color, (18, 8), (22, 8), 2)
        self.screen.blit(s, (cx - 15, cy))

    def _sfx(self, name: str):
        if self._snd:
            self._snd.play(name)

    def _start_fade(self, target: float, duration_sec: float):
        self._fade_target = target
        self._fade_speed = 255.0 / (duration_sec * 1000.0) if duration_sec > 0 else 0

    @staticmethod
    def _ease_out(t: float) -> float:
        return 1.0 - (1.0 - t) ** 3
