"""
Hub Screen — Haven's Rest town between title and battles.
"""

import math
import random
import pygame
from enum import Enum, auto
from item import Rarity, ItemSlot
from sprites import get_hub_sinon
import achievements


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
    RETURN_PROMPT = auto()
    TOAST = auto()
    ACHIEVEMENTS = auto()


# ── Location data ──────────────────────────────────────────────────────
LOCATIONS = [
    {"name": "Dungeon Gate", "icon": "sword",   "desc": "Descend into danger",   "key": "dungeon"},
    {"name": "Smithy",       "icon": "hammer",  "desc": "Equip & manage gear",   "key": "smithy"},
    {"name": "Apothecary",   "icon": "potion",  "desc": "Buy consumables",       "key": "apothecary"},
    {"name": "Rest",         "icon": "moon",    "desc": "Restore HP & SP",       "key": "rest"},
]

CARD_W, CARD_H = 175, 135
CARD_GAP = 22
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


# ── Hub Screen ─────────────────────────────────────────────────────────
class HubScreen:
    """Renders and manages the Haven's Rest hub town."""

    def __init__(self, screen: pygame.Surface, player, ach_manager=None):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.player = player
        self._ach_manager = ach_manager

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
        self._sell_toast_timer = 0
        self._sell_toast_text = ""

        # ── Shop state ──
        self._shop_cursor = 0
        self._shop_confirming = False
        self._shop_toast_timer = 0
        self._shop_toast_text = ""

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
        elif key == "apothecary":
            self._enter_shop()
        elif key == "rest":
            self._do_rest()

    def open_achievements(self):
        if self.sub_state == HubSubState.MAIN:
            self._enter_achievements()

    def cancel(self):
        """ESC pressed. Behaviour depends on sub-state."""
        if self.sub_state == HubSubState.MAIN:
            self.sub_state = HubSubState.RETURN_PROMPT
        elif self.sub_state in (HubSubState.APOTHECARY, HubSubState.SMITHY_INVENTORY, HubSubState.ACHIEVEMENTS):
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
        p = self.player
        if p.inventory:
            self._inv_cursor = (self._inv_cursor - 1) % len(p.inventory)
            if self._inv_cursor < self._inv_scroll_offset:
                self._inv_scroll_offset = self._inv_cursor

    def smithy_move_down(self):
        if self.sub_state != HubSubState.SMITHY_INVENTORY:
            return
        self._sell_confirming = False
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
        if self._ach_manager:
            self._ach_manager.unlock("merchant")

        if self._inv_cursor >= len(p.inventory):
            self._inv_cursor = max(0, len(p.inventory) - 1)
        if self._inv_scroll_offset > self._inv_cursor:
            self._inv_scroll_offset = max(0, self._inv_cursor - 1)

    def smithy_sort(self):
        """Sort sell list by rarity then stat value."""
        from item import Weapon, Rarity
        RANK = {Rarity.LEGENDARY: 3, Rarity.EPIC: 2, Rarity.RARE: 1, Rarity.COMMON: 0}
        self.player.inventory.sort(
            key=lambda it: (RANK.get(it.rarity, 0), it.atk if isinstance(it, Weapon) else it.defense),
            reverse=True,
        )
        self._inv_cursor = 0
        self._inv_scroll_offset = 0

    def _sell_price(self, item) -> int:
        """Calculate sell price based on rarity and stats."""
        from item import Weapon, Armor
        base = {Rarity.COMMON: 10, Rarity.RARE: 25, Rarity.EPIC: 60, Rarity.LEGENDARY: 150}
        b = base.get(item.rarity, 10)
        stat_bonus = item.atk if isinstance(item, Weapon) else item.defense
        return int(b * (1 + stat_bonus / 10))

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
        elif self.sub_state == HubSubState.ACHIEVEMENTS:
            self._draw_achievements()

        # ── Fade overlay ──
        if self.fade_alpha > 1:
            fade = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fade.fill((0, 0, 0, min(255, int(self.fade_alpha))))
            self.screen.blit(fade, (0, 0))

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

            # Name
            name_surf = self.font_card_name.render(loc["name"], True, WHITE if selected else DIM_WHITE)
            nx = cx + (CARD_W - name_surf.get_width()) // 2
            ny = iy + 30 + 8
            self.screen.blit(name_surf, (nx, ny))

            # Description
            desc_surf = self.font_card_desc.render(loc["desc"], True, (130, 130, 150))
            dx = cx + (CARD_W - desc_surf.get_width()) // 2
            dy = ny + name_surf.get_height() + 4
            self.screen.blit(desc_surf, (dx, dy))

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
    #  Smithy inventory overlay                                          #
    # ------------------------------------------------------------------ #

    def _enter_smithy(self):
        self._inv_cursor = 0
        self._inv_scroll_offset = 0
        self._sell_confirming = False
        self.sub_state = HubSubState.SMITHY_INVENTORY

    def _draw_smithy_inventory(self):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 560, 400
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        m = 18

        # Panel
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 2, border_radius=8)

        # Title + gold
        title = self.font_inv_title.render("Smithy - Sell Your Gear", True, NEON_CYAN)
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

        eq_label = self.font_inv_section.render("EQUIPPED", True, DIM_WHITE)
        self.screen.blit(eq_label, (px + m, eq_y))

        eq_ry = eq_y + 22
        row_w = panel_w - 2 * m
        if weapon:
            w_text = f"W: {weapon.name}  +{weapon.atk} ATK"
            w_surf = self.font_card_desc.render(w_text, True, RARITY_COLOR.get(weapon.rarity, WHITE))
            self.screen.blit(w_surf, (px + m + 4, eq_ry))
            eq_ry += 16
        if armor:
            a_text = f"A: {armor.name}  +{armor.defense} DEF"
            a_surf = self.font_card_desc.render(a_text, True, RARITY_COLOR.get(armor.rarity, WHITE))
            self.screen.blit(a_surf, (px + m + 4, eq_ry))
            eq_ry += 16
        if not weapon and not armor:
            no_eq = self.font_card_desc.render("(empty)", True, (80, 80, 100))
            self.screen.blit(no_eq, (px + m + 4, eq_ry))
            eq_ry += 16

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
        bag_label = self.font_inv_section.render("BAG - Select to Sell", True, GOLD)
        self.screen.blit(bag_label, (px + m, eq_ry))
        eq_ry += 24

        bag_zone_top = eq_ry
        bag_zone_bottom = py + panel_h - m - 30
        bag_zone_h = bag_zone_bottom - bag_zone_top
        pygame.draw.rect(self.screen, (*NEON_CYAN_DIM[:3], 80),
                         (px + m - 4, bag_zone_top - 2, row_w + 8, bag_zone_h + 4), 1, border_radius=4)

        clip_rect = pygame.Rect(px + m, bag_zone_top, row_w, bag_zone_h)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        inv = p.inventory
        item_h = 38
        item_pad = 4
        max_visible = max(1, bag_zone_h // (item_h + item_pad))

        # Clamp scroll
        if self._inv_scroll_offset > self._inv_cursor:
            self._inv_scroll_offset = self._inv_cursor
        elif self._inv_cursor >= self._inv_scroll_offset + max_visible:
            self._inv_scroll_offset = self._inv_cursor - max_visible + 1

        if not inv:
            empty = self.font_inv_item.render("  No items to sell.", True, (80, 80, 100))
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
        elif self._sell_confirming:
            item = inv[self._inv_cursor] if inv else None
            if item:
                price = self._sell_price(item)
                confirm = self.font_small.render(f"Sell {item.name} for {price}g?  Press ENTER to confirm", True, GOLD)
                self.screen.blit(confirm, (px + (panel_w - confirm.get_width()) // 2, hint_y))
        else:
            hints = "W/S: Navigate   ENTER: Sell   F: Sort   ESC: Back"
            hint_surf = self.font_inv_hint.render(hints, True, (100, 100, 130))
            self.screen.blit(hint_surf, (px + (panel_w - hint_surf.get_width()) // 2, hint_y))

    def _draw_sell_item_row(self, x, y, w, h, item, selected):
        from item import Weapon
        rarity_c = RARITY_COLOR.get(item.rarity, WHITE)
        accent_c = RARITY_ACCENT.get(item.rarity, (60, 60, 75))
        price = self._sell_price(item)
        is_weapon = isinstance(item, Weapon)
        stat_val = f"+{item.atk} ATK" if is_weapon else f"+{item.defense} DEF"

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
        price_text = f"[{price}g]"
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
        self.screen.blit(s, (cx - 15, cy))

    def _start_fade(self, target: float, duration_sec: float):
        self._fade_target = target
        self._fade_speed = 255.0 / (duration_sec * 1000.0) if duration_sec > 0 else 0

    @staticmethod
    def _ease_out(t: float) -> float:
        return 1.0 - (1.0 - t) ** 3
