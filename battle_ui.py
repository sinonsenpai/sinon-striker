"""
Battle UI module - zoned layout with anime glass aesthetic.
Top 70%: Stage (character HUDs, sprites, VS, turn state)
Bottom 30%: Command Tray (left=menu, right=combat log)
All positions use percentage-based layout.
"""

import math
import random
import pygame
from character import Character, Enemy
from combat_manager import CombatManager, TurnState, MenuAction, MENU_OPTIONS, SKILL_DEFS
from item import Rarity, ItemSlot, Consumable
from sprites import get_sinon_sprite, get_enemy_sprite, SpriteAnim


# ── Color palette (anime glass, unchanged) ──
BG_COLOR = (18, 14, 30)
WHITE = (230, 230, 245)
DIM_WHITE = (160, 160, 180)
RED = (220, 50, 60)
GREEN = (50, 210, 100)
YELLOW = (240, 220, 60)
GOLD = (255, 215, 0)
DARK_GRAY = (60, 60, 75)
NEON_CYAN = (0, 240, 255)
NEON_CYAN_DIM = (0, 100, 120)
HP_BAR_BG = (80, 20, 20)
PANEL_BG = (20, 15, 40)
PANEL_BG_ALPHA = 190
PANEL_BORDER = (0, 240, 255)
PANEL_BORDER_ALPHA = 200
ACCENT_GOLD = (255, 215, 0)
ACCENT_GOLD_DIM = (120, 100, 30)
TRAY_BG_ALPHA = 210

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

SHAKE_MAX_INTENSITY = 8
SHAKE_DURATION_MS = 200
INV_SLIDE_MS = 200

INV_PANEL_W = 560
INV_PANEL_H = 460
INV_MARGIN = 20
INV_STAT_ZONE_H = 100
INV_ITEM_H = 50
INV_ITEM_PAD = 10
INV_EQ_SLOT_H = 40

MENU_PAD = 8


def _truncate_text(font, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    while text and font.size(text + "...")[0] > max_width:
        text = text[:-1]
    return text + "..."


# ── Visual FX classes ──────────────────────────────────────────────────

class FloatingText:
    def __init__(self, text, x, y, color, size=24):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.font = pygame.font.SysFont("arial", size, bold=(size >= 30))
        self.lifetime = 800
        self.timer = 0
        self.velocity = -1.5

    def update(self, dt_ms):
        self.timer += dt_ms
        self.y += self.velocity * (dt_ms / 16)
        return self.timer < self.lifetime

    def draw(self, screen):
        alpha = max(0, 255 - int(255 * (self.timer / self.lifetime)))
        surf = self.font.render(self.text, True, self.color)
        surf.set_alpha(alpha)
        screen.blit(surf, (self.x - surf.get_width() // 2, self.y))


class Spark:
    def __init__(self, x, y, color, size):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(1.5, 4.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.lifetime = 400
        self.timer = 0

    def update(self, dt_ms):
        self.timer += dt_ms
        self.x += self.vx * (dt_ms / 16)
        self.y += self.vy * (dt_ms / 16)
        return self.timer < self.lifetime

    def draw(self, screen):
        alpha = max(0, 255 - int(255 * (self.timer / self.lifetime)))
        spark_surf = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        spark_surf.fill((*self.color, alpha))
        screen.blit(spark_surf, (int(self.x), int(self.y)))


class ScreenFlash:
    def __init__(self):
        self.timer = 0
        self.duration = 80
        self.active = False
        self.color = WHITE
        self.max_alpha = 80

    def trigger(self, color=WHITE, duration=80, max_alpha=80):
        self.timer = duration
        self.duration = duration
        self.active = True
        self.color = color
        self.max_alpha = max_alpha

    def update(self, dt_ms):
        if not self.active:
            return
        self.timer -= dt_ms
        if self.timer <= 0:
            self.active = False

    def draw(self, screen):
        if not self.active:
            return
        alpha = int(self.max_alpha * (self.timer / self.duration))
        flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        flash.fill((*self.color, alpha))
        screen.blit(flash, (0, 0))


class CriticalPopup:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.lifetime = 500
        self.timer = 0
        self.scale = 1.5

    def update(self, dt_ms):
        self.timer += dt_ms
        t = min(1.0, self.timer / self.lifetime)
        self.scale = 1.5 - 0.5 * t
        return self.timer < self.lifetime

    def draw(self, screen, font):
        alpha = max(0, 255 - int(255 * (self.timer / self.lifetime)))
        surf = font.render("CRITICAL!", True, GOLD)
        w = int(surf.get_width() * self.scale)
        h = int(surf.get_height() * self.scale)
        if w > 0 and h > 0:
            scaled = pygame.transform.scale(surf, (w, h))
            scaled.set_alpha(alpha)
            screen.blit(scaled, (self.x - w // 2, self.y - h // 2))


class BattleUI:
    """Renders the battle screen with zoned layout."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.font_xl = pygame.font.SysFont("arial", 34, bold=True)
        self.font_large = pygame.font.SysFont("arial", 26, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 20, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16, bold=False)
        self.font_stat = pygame.font.SysFont("arial", 18, bold=True)
        self.font_hud = pygame.font.SysFont("arial", 15, bold=False)
        self.font_victory = pygame.font.SysFont("arial", 42, bold=True)
        self.font_victory_sub = pygame.font.SysFont("arial", 18, bold=False)
        self.font_card_desc = pygame.font.SysFont("arial", 14, bold=False)
        self.offscreen = pygame.Surface((self.w, self.h))

        self.shake_intensity = 0.0
        self.shake_timer = 0
        self._prev_log_count = 0
        self._pulse_timer = 0.0
        self._inv_slide_progress = 0.0
        self._inv_slide_direction = 0
        self._inv_visible = False
        self._log_scroll_offset = 0

        # Sprite animations
        self._player_anim = SpriteAnim()
        self._enemy_anim = SpriteAnim()
        self._prev_player_hp = 0
        self._prev_enemy_hp = 0

        # Level-up overlay animation
        self._lvl_up_scale = 0.0

        # Visual FX
        self._floating_texts = []
        self._sparks = []
        self._critical_popups = []
        self._screen_flash = ScreenFlash()

    # ── Layout helpers (percentage-based) ──

    def _stage_bottom(self):
        return int(self.h * 0.68)

    def _tray_top(self):
        return self._stage_bottom()

    def _tray_height(self):
        return self.h - self._tray_top()

    # ── Glass panel ──

    def _draw_glass_panel(self, x, y, w, h, border_color=PANEL_BORDER,
                          border_alpha=PANEL_BORDER_ALPHA, border_width=2,
                          corner_radius=6):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], PANEL_BG_ALPHA))
        self.screen.blit(panel, (x, y))
        border_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (*border_color, border_alpha),
                         (0, 0, w, h), width=border_width, border_radius=corner_radius)
        self.screen.blit(border_surf, (x, y))

    def _draw_accent_line(self, x1, y1, x2, y2, color=NEON_CYAN, width=1):
        pygame.draw.line(self.screen, color, (x1, y1), (x2, y2), width)

    # ── Shake & animation ──

    def _trigger_shake(self):
        self.shake_intensity = SHAKE_MAX_INTENSITY
        self.shake_timer = SHAKE_DURATION_MS

    def _update_shake(self, dt_ms: int):
        if self.shake_timer <= 0:
            self.shake_intensity = 0.0
            return
        self.shake_timer -= dt_ms
        if self.shake_timer < 0:
            self.shake_timer = 0
        ratio = max(0.0, self.shake_timer / SHAKE_DURATION_MS)
        self.shake_intensity = SHAKE_MAX_INTENSITY * ratio

    def _get_shake_offset(self) -> tuple:
        if self.shake_intensity <= 0.0:
            return (0, 0)
        dx = random.uniform(-self.shake_intensity, self.shake_intensity)
        dy = random.uniform(-self.shake_intensity, self.shake_intensity)
        return (int(dx), int(dy))

    def _check_for_hits(self, combat: CombatManager, dx=0, dy=0):
        current_log_count = len(combat._log)
        if current_log_count != self._prev_log_count:
            self._log_scroll_offset = 0
        shake_source = getattr(combat, '_shake_source', None)
        if shake_source:
            self._trigger_shake()
            if shake_source == "player":
                self._player_anim.trigger_attack()
            elif shake_source == "enemy":
                self._enemy_anim.trigger_attack()
            combat._shake_source = None
        self._prev_log_count = current_log_count

        # Hit flash on HP changes
        if combat.player.current_hp < self._prev_player_hp:
            self._player_anim.trigger_hit()
        if combat.enemy.current_hp < self._prev_enemy_hp:
            self._enemy_anim.trigger_hit()
        self._prev_player_hp = combat.player.current_hp
        self._prev_enemy_hp = combat.enemy.current_hp

        # Spawn visual FX from combat hit info
        hit_info = getattr(combat, '_last_hit_info', None)
        if hit_info:
            missed = hit_info.get("missed", False)
            sprite_y = self._get_sprite_y()
            if missed:
                target = hit_info.get("target")
                if target == "enemy":
                    x = int(self.w * 0.72) + dx
                    y = sprite_y - 80 + dy
                else:
                    x = int(self.w * 0.25) + dx
                    y = sprite_y - 80 + dy
                miss_text = FloatingText("MISS!", x, y - 20, DIM_WHITE, 28)
                self._floating_texts.append(miss_text)
                combat._last_hit_info = None
                return  # Skip the rest of the FX processing

            target = hit_info.get("target")
            damage = hit_info.get("damage", 0)
            is_crit = hit_info.get("is_crit", False)
            if target == "enemy":
                x = int(self.w * 0.72) + dx
                y = sprite_y - 80 + dy
                spark_color = GOLD if is_crit else NEON_CYAN
                flash_color = WHITE
                flash_alpha = 120 if is_crit else 80
            else:
                x = int(self.w * 0.25) + dx
                y = sprite_y - 80 + dy
                spark_color = RED
                flash_color = RED
                flash_alpha = 80

            # Floating damage number
            text_color = GOLD if is_crit else WHITE
            text_size = 30 if is_crit else 22
            self._floating_texts.append(FloatingText(str(damage), x, y, text_color, text_size))

            # Sparks
            spark_count = 12 if is_crit else 8
            for _ in range(spark_count):
                size = random.randint(3, 5) if is_crit else random.randint(2, 4)
                sx = x + random.randint(-20, 20)
                sy = y + random.randint(-10, 10)
                self._sparks.append(Spark(sx, sy, spark_color, size))

            # Screen flash
            self._screen_flash.trigger(flash_color, 80, flash_alpha)

            # Critical popup
            if is_crit:
                self._critical_popups.append(CriticalPopup(x, y - 35))

            combat._last_hit_info = None

    def _pulse_brightness(self) -> float:
        return 0.85 + 0.15 * (0.5 + 0.5 * math.sin(self._pulse_timer * 0.006))

    def scroll_log_up(self):
        self._log_scroll_offset += 1

    def scroll_log_down(self):
        if self._log_scroll_offset > 0:
            self._log_scroll_offset -= 1

    # ── Main draw ──

    def _get_sprite_y(self) -> int:
        """Return the Y coordinate where sprites are drawn (bottom of sprite)."""
        stage_h = self._stage_bottom()
        header_h = 28
        inner_top = header_h + int(self.h * 0.018)
        inner_bottom = stage_h - int(self.h * 0.02)
        inner_h = inner_bottom - inner_top
        return inner_top + int(inner_h * 0.90)

    def draw(self, combat: CombatManager, dt_ms: int = 0):
        self._pulse_timer += dt_ms
        self._update_shake(dt_ms)
        dx, dy = self._get_shake_offset()
        self._check_for_hits(combat, dx, dy)
        self._player_anim.update(dt_ms)
        self._enemy_anim.update(dt_ms)

        # Update visual FX
        self._screen_flash.update(dt_ms)
        for ft in self._floating_texts[:]:
            if not ft.update(dt_ms):
                self._floating_texts.remove(ft)
        for sp in self._sparks[:]:
            if not sp.update(dt_ms):
                self._sparks.remove(sp)
        for cp in self._critical_popups[:]:
            if not cp.update(dt_ms):
                self._critical_popups.remove(cp)

        if combat.state == TurnState.INVENTORY:
            self._inv_visible = True
            self._inv_slide_direction = 1
        elif self._inv_slide_direction == 1 and self._inv_slide_progress >= 1.0:
            self._inv_slide_direction = -1

        if self._inv_visible:
            speed = 1.0 / max(1, INV_SLIDE_MS) * dt_ms
            if self._inv_slide_direction == 1:
                self._inv_slide_progress = min(1.0, self._inv_slide_progress + speed)
            elif self._inv_slide_direction == -1:
                self._inv_slide_progress = max(0.0, self._inv_slide_progress - speed)
                if self._inv_slide_progress <= 0.0:
                    self._inv_visible = False
                    self._inv_slide_direction = 0

        offscreen = self.offscreen
        old_screen = self.screen
        self.screen = offscreen

        self.screen.fill(BG_COLOR)
        for i in range(self.h):
            alpha = int(12 + 8 * math.sin(i * 0.005))
            pygame.draw.line(self.screen, (30 + alpha, 20 + alpha // 2, 55 + alpha), (0, i), (self.w, i))

        # ── STAGE (top 70%) ──
        self._draw_stage(combat)

        # ── COMMAND TRAY (bottom 30%) ──
        self._draw_tray(combat)

        self.screen = old_screen
        self.screen.blit(offscreen, (dx, dy))

        # Level-up celebration overlay (drawn on real screen, on top)
        if combat.state == TurnState.VICTORY and combat.victory_phase == "level_up":
            if self._lvl_up_scale < 1.0:
                self._lvl_up_scale = min(1.0, self._lvl_up_scale + dt_ms / 300.0)
            self._draw_level_up_overlay(combat)
        else:
            self._lvl_up_scale = 0.0

        # Inventory overlay on real screen (on top)
        if combat.state == TurnState.INVENTORY or self._inv_visible:
            self._draw_inventory_overlay(combat)

        # Visual FX (floating numbers, sparks, critical popups)
        for ft in self._floating_texts:
            ft.draw(self.screen)
        for sp in self._sparks:
            sp.draw(self.screen)
        for cp in self._critical_popups:
            cp.draw(self.screen, self.font_large)

        # Screen flash on top of everything
        self._screen_flash.draw(self.screen)

    # ── STAGE zone ──

    def _draw_stage(self, combat: CombatManager):
        stage_h = self._stage_bottom()
        hud_w = int(self.w * 0.32)
        edge_pad = int(self.w * 0.025)

        # ── Header bar ──
        header_h = 28
        header_y = 0
        header_surf = pygame.Surface((self.w, header_h), pygame.SRCALPHA)
        for i in range(header_h):
            a = int(120 + 20 * (1.0 - i / header_h))
            pygame.draw.line(header_surf, (PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], a),
                             (0, i), (self.w, i))
        self.screen.blit(header_surf, (0, header_y))
        self._draw_accent_line(0, header_h - 1, self.w, header_h - 1, NEON_CYAN_DIM, 1)

        # Turn state label — left side of header
        labels = {
            TurnState.WAIT: "Waiting...",
            TurnState.MENU_SELECT: "[ YOUR TURN ]",
            TurnState.SKILL_SELECT: "[ SKILLS ]",
            TurnState.ITEM_SELECT: "[ ITEMS ]",
            TurnState.PLAYER_ACTION: "[ EXECUTING... ]",
            TurnState.ENEMY_TURN: "[ ENEMY TURN ]",
            TurnState.INVENTORY: "[ INVENTORY ]",
        }
        if combat.state not in (TurnState.VICTORY, TurnState.DEFEAT):
            state_text = labels.get(combat.state, "")
            state_surf = self.font_hud.render(state_text, True, NEON_CYAN)
            self.screen.blit(state_surf, (14, header_y + (header_h - state_surf.get_height()) // 2))

        # Game title — center of header
        header_text = self.font_hud.render("SINON STRIKER", True, NEON_CYAN_DIM)
        self.screen.blit(header_text, ((self.w - header_text.get_width()) // 2,
                                        header_y + (header_h - header_text.get_height()) // 2))
        # Gold display — right side of header
        gold_text = f"* {combat.player.gold}"
        gold_surf = self.font_hud.render(gold_text, True, GOLD)
        self.screen.blit(gold_surf, (self.w - gold_surf.get_width() - 14,
                                      header_y + (header_h - gold_surf.get_height()) // 2))

        # Remaining stage area (shifted down by header height)
        inner_top = header_h + int(self.h * 0.018)
        inner_bottom = stage_h - int(self.h * 0.02)
        inner_h = inner_bottom - inner_top

        # Player HUD — top-left
        self._draw_hud(combat.player, edge_pad, inner_top, hud_w)

        # Enemy HUD — top-right
        self._draw_hud(combat.enemy, self.w - hud_w - edge_pad, inner_top, hud_w, is_boss=getattr(combat, 'is_boss', False))

        # Character sprites in center of stage
        sprite_y = inner_top + int(inner_h * 0.90)
        self._draw_sprites(combat, sprite_y)

        # VS text — center of stage
        vs_surf = self.font_xl.render("VS", True, NEON_CYAN)
        self.screen.blit(vs_surf, ((self.w - vs_surf.get_width()) // 2,
                                    (stage_h - vs_surf.get_height()) // 2 - int(self.h * 0.05)))

        # Victory/defeat overlay
        if combat.state in (TurnState.VICTORY, TurnState.DEFEAT):
            self._draw_victory_defeat_overlay(combat)

    def _draw_victory_defeat_overlay(self, combat: CombatManager):
        """Centered semi-transparent overlay for victory or defeat."""
        panel_w, panel_h = 420, 200
        tray_top = self._tray_top()
        # Ensure at least 15px clearance above the combat log tray
        max_py = tray_top - panel_h - 15
        py = min((self.h - panel_h) // 2, max_py)
        if py < 20:
            py = 20
        px = (self.w - panel_w) // 2

        # Semi-transparent backdrop
        backdrop = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 160))
        self.screen.blit(backdrop, (0, 0))

        # Solid panel
        panel = pygame.Surface((panel_w, panel_h))
        panel.fill(PANEL_BG)
        self.screen.blit(panel, (px, py))
        bcolor = GOLD if combat.state == TurnState.VICTORY else RED
        border = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(border, (*bcolor, 255), (0, 0, panel_w, panel_h), width=2, border_radius=8)
        self.screen.blit(border, (px, py))

        is_victory = combat.state == TurnState.VICTORY
        if is_victory and getattr(combat, 'is_boss', False):
            title_text = "BOSS DEFEATED!"
        else:
            title_text = "VICTORY!" if is_victory else "DEFEATED"
        title_color = GOLD if is_victory else RED

        title_surf = self.font_victory.render(title_text, True, title_color)
        self.screen.blit(title_surf, ((self.w - title_surf.get_width()) // 2, py + 22))

        # Reward / result line
        cur_ry = py + 72
        if is_victory:
            # XP earned
            xp_gained = getattr(combat, '_xp_gained', 0)
            if xp_gained > 0:
                xp_text = f"+{xp_gained} XP"
                xp_surf = self.font_victory_sub.render(xp_text, True, YELLOW)
                self.screen.blit(xp_surf, ((self.w - xp_surf.get_width()) // 2, cur_ry))
                cur_ry += 22

            # Gold earned
            gold_earned = getattr(combat, '_gold_dropped', 0)
            gold_total = combat.player.gold
            gold_text = f"* +{gold_earned} gold  (Total: {gold_total})"
            gold_surf = self.font_victory_sub.render(gold_text, True, GOLD)
            self.screen.blit(gold_surf, ((self.w - gold_surf.get_width()) // 2, cur_ry))
            cur_ry += 26

            # Loot notice
            loot_text = "\U0001f4e6 Loot has been added to your inventory."
            loot_surf = self.font_victory_sub.render(loot_text, True, DIM_WHITE)
            self.screen.blit(loot_surf, ((self.w - loot_surf.get_width()) // 2, cur_ry))
            cur_ry += 24
        else:
            reward_text = f"{combat.player.name} has fallen in battle."
            reward_surf = self.font_victory_sub.render(reward_text, True, DIM_WHITE)
            self.screen.blit(reward_surf, ((self.w - reward_surf.get_width()) // 2, cur_ry))
            cur_ry += 26

        # HP summary
        hp_text = f"HP remaining: {combat.player.current_hp}/{combat.player.max_hp}"
        hp_surf = self.font_victory_sub.render(hp_text, True, WHITE)
        self.screen.blit(hp_surf, ((self.w - hp_surf.get_width()) // 2, cur_ry))

        # Controls
        if getattr(combat, 'in_dungeon', False):
            ctrl_text = "ENTER - Continue    |    R - Rematch"
        else:
            ctrl_text = "ENTER - Return to Hub    |    R - Rematch"
        ctrl_surf = self.font_small.render(ctrl_text, True, (120, 120, 140))
        self.screen.blit(ctrl_surf, ((self.w - ctrl_surf.get_width()) // 2, py + panel_h - 32))

    def _draw_level_up_overlay(self, combat: CombatManager):
        """Full-screen level-up celebration with scale-in animation."""
        scale = min(1.0, self._lvl_up_scale)
        if scale <= 0:
            return
        eased = 1.0 - (1.0 - scale) ** 3

        # Full-screen dim
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(180 * eased)))
        self.screen.blit(dim, (0, 0))

        # Target panel size
        target_w, target_h = 440, 280
        panel_w = max(2, int(target_w * eased))
        panel_h = max(2, int(target_h * eased))

        # Render full panel off-screen
        full_surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        full_surf.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 240))
        pygame.draw.rect(full_surf, (*GOLD, 255), (0, 0, target_w, target_h), width=3, border_radius=10)

        # Gather level-up info (show the highest level reached)
        level_ups = getattr(combat, '_level_ups', [])
        if not level_ups:
            return
        lu = level_ups[-1]  # show final level reached
        p = combat.player
        old_hp = p.max_hp - lu['hp_gain']
        old_atk = p.atk - lu['atk_gain']
        old_def = p.defn - lu['def_gain']

        # Pulsing "LEVEL UP!" title
        pulse = 1.0 + 0.08 * math.sin(self._pulse_timer * 0.008)
        title_font = pygame.font.SysFont("arial", 42, bold=True)
        title_surf = title_font.render("LEVEL UP!", True, GOLD)
        if pulse != 1.0:
            tw, th = title_surf.get_size()
            title_surf = pygame.transform.scale(title_surf, (int(tw * pulse), int(th * pulse)))
        tx = (target_w - title_surf.get_width()) // 2
        full_surf.blit(title_surf, (tx, 18))

        # Reached level line
        sub_font = pygame.font.SysFont("arial", 20, bold=False)
        sub = sub_font.render(f"{p.name} reached Level {lu['level']}!", True, WHITE)
        full_surf.blit(sub, ((target_w - sub.get_width()) // 2, 72))

        # Stat lines with aligned columns
        stat_font = pygame.font.SysFont("arial", 18, bold=False)
        stat_y = 110
        line_h = 26
        stats = [
            ("HP", old_hp, p.max_hp, lu['hp_gain']),
            ("ATK", old_atk, p.atk, lu['atk_gain']),
            ("DEF", old_def, p.defn, lu['def_gain']),
        ]
        for label, old, new, gain in stats:
            line = f"  {label}  {old:>3} -> {new:>3}  (+{gain})"
            s = stat_font.render(line, True, WHITE)
            full_surf.blit(s, ((target_w - s.get_width()) // 2, stat_y))
            stat_y += line_h

        # HP restored notice
        restored = sub_font.render("HP fully restored!", True, GREEN)
        full_surf.blit(restored, ((target_w - restored.get_width()) // 2, stat_y + 8))

        # Controls hint
        hint = self.font_small.render("ENTER - Continue", True, (120, 120, 140))
        full_surf.blit(hint, ((target_w - hint.get_width()) // 2, target_h - 28))

        # Blit scaled or full
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        if eased < 1.0:
            scaled = pygame.transform.scale(full_surf, (panel_w, panel_h))
            self.screen.blit(scaled, (px, py))
        else:
            self.screen.blit(full_surf, (px, py))

    def _draw_hud(self, char, x: int, y: int, hud_w: int, is_boss: bool = False):
        """Draw a character stat panel with padded layout.
           Row 1: Name (centered)
           Row 2: HP bar with label
           Row 3: SP bar with label
           Row 4: XP bar with label
           Row 5: ATK | DEF stats
           Row 6-7: Equipment lines
           Row 8: Consumables count
        """
        m = 14           # internal panel padding (increased)
        row_gap = 6      # vertical gap between rows
        bar_h = 18       # HP bar height
        sp_h = 12        # SP bar height
        xp_bar_h = 8     # XP bar height
        stat_h = 22      # stat row height
        eq_h = 17        # equipment row height
        soft_cyan = (100, 200, 255)
        eq_gold = (200, 170, 50)

        # ── Pre-render text surrogates for measurement ──
        weapon = char.equipment.get("weapon")
        armor = char.equipment.get("armor")

        name_color = RED if is_boss else WHITE
        name_surf = self.font_medium.render(char.name, True, name_color)

        # ── Calculate dynamic height ──
        name_h = name_surf.get_height()
        equip_lines = (1 if weapon else 0) + (1 if armor else 0)
        if equip_lines == 0:
            equip_lines = 1
        active_sets = char.get_active_sets()
        set_bonus_lines = len(active_sets)
        content_h = (name_h + 4       # name row
                     + bar_h + 3       # HP bar
                     + sp_h + row_gap  # SP bar
                     + xp_bar_h + row_gap  # XP bar
                     + stat_h + row_gap
                     + equip_lines * eq_h
                     + (row_gap if set_bonus_lines > 0 else 0)
                     + (set_bonus_lines * eq_h if set_bonus_lines > 0 else 0)
                     + (row_gap if char.consumables else 0)
                     + (eq_h if char.consumables else 0))
        panel_h = content_h + m * 2

        # ── Glass panel (with status-based border color) ──
        border_color = RED if is_boss else NEON_CYAN
        if not is_boss:
            if char.has_status("focused"):
                border_color = GOLD
            elif char.has_status("vulnerable"):
                border_color = RED
        self._draw_glass_panel(x, y, hud_w, panel_h, border_color=border_color, border_alpha=220,
                               border_width=3 if is_boss else (2 if char.status_effects else 1), corner_radius=7)

        # Boss tint overlay
        if is_boss:
            boss_tint = pygame.Surface((hud_w, panel_h), pygame.SRCALPHA)
            boss_tint.fill((*RED, 20))
            self.screen.blit(boss_tint, (x, y))
            # BOSS label
            boss_label = self.font_hud.render("BOSS", True, RED)
            self.screen.blit(boss_label, (x + hud_w - boss_label.get_width() - 10, y + 6))

        # Status tint overlay
        if char.has_status("focused"):
            glow = pygame.Surface((hud_w, panel_h), pygame.SRCALPHA)
            glow.fill((*GOLD, 25))
            self.screen.blit(glow, (x, y))
        elif char.has_status("vulnerable"):
            tint = pygame.Surface((hud_w, panel_h), pygame.SRCALPHA)
            tint.fill((*RED, 25))
            self.screen.blit(tint, (x, y))

        # ── Draw content ──
        inner_w = hud_w - 2 * m
        cur_y = y + m
        cx = x + m

        # Row 1: Name (centered)
        self.screen.blit(name_surf, (cx + (inner_w - name_surf.get_width()) // 2, cur_y))
        cur_y += name_surf.get_height() + 4

        # Row 2: HP bar
        bar_w = inner_w
        bar_x = cx
        hp_pct = char.current_hp / char.max_hp if char.max_hp > 0 else 0
        bar_y = cur_y
        hp_bar_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(hp_bar_surf, (55, 10, 10, 200), (0, 0, bar_w, bar_h), border_radius=4)
        fill_w = min(bar_w, max(0, int(bar_w * hp_pct)))
        if fill_w > 0:
            if is_boss:
                fill_color = (220, 40, 40)
            else:
                fill_color = GREEN if hp_pct > 0.3 else RED
            pygame.draw.rect(hp_bar_surf, (*fill_color, 220), (0, 0, fill_w, bar_h), border_radius=4)
        self.screen.blit(hp_bar_surf, (bar_x, bar_y))
        # Label on the left
        hp_label_left = self.font_hud.render("HP", True, WHITE)
        self.screen.blit(hp_label_left, (bar_x + 4, bar_y + (bar_h - hp_label_left.get_height()) // 2))
        # Value centered
        hp_val_text = f"{char.current_hp}/{char.max_hp}"
        hp_val_surf = self.font_hud.render(hp_val_text, True, WHITE)
        self.screen.blit(hp_val_surf, (bar_x + (bar_w - hp_val_surf.get_width()) // 2,
                                        bar_y + (bar_h - hp_val_surf.get_height()) // 2))
        cur_y += bar_h + 3

        # Row 3: SP bar
        sp_pct = char.sp / char.max_sp if char.max_sp > 0 else 0
        sp_bar_surf = pygame.Surface((bar_w, sp_h), pygame.SRCALPHA)
        pygame.draw.rect(sp_bar_surf, (8, 12, 40, 180), (0, 0, bar_w, sp_h), border_radius=3)
        fill_w_sp = min(bar_w, max(0, int(bar_w * sp_pct)))
        if fill_w_sp > 0:
            pygame.draw.rect(sp_bar_surf, (80, 190, 240, 210), (0, 0, fill_w_sp, sp_h), border_radius=3)
        self.screen.blit(sp_bar_surf, (bar_x, cur_y))
        # Label on the left
        sp_label_left = self.font_hud.render("SP", True, (180, 220, 255))
        self.screen.blit(sp_label_left, (bar_x + 4, cur_y + (sp_h - sp_label_left.get_height()) // 2))
        # Value centered
        sp_val_text = f"{char.sp}/{char.max_sp}"
        sp_val_surf = self.font_hud.render(sp_val_text, True, (180, 220, 255))
        self.screen.blit(sp_val_surf, (bar_x + (bar_w - sp_val_surf.get_width()) // 2,
                                        cur_y + (sp_h - sp_val_surf.get_height()) // 2))
        cur_y += sp_h + row_gap

        # Row 4: XP bar
        if char.level >= char._max_level:
            xp_pct = 1.0
            xp_text_left = "Lv.MAX"
            xp_text_right = ""
        else:
            xp_pct = char.xp / char.xp_to_next if char.xp_to_next > 0 else 0
            xp_text_left = f"Lv.{char.level}"
            xp_text_right = f"{char.xp}/{char.xp_to_next}"
        xp_bar_surf = pygame.Surface((bar_w, xp_bar_h), pygame.SRCALPHA)
        pygame.draw.rect(xp_bar_surf, (30, 30, 45, 180), (0, 0, bar_w, xp_bar_h), border_radius=2)
        fill_w_xp = min(bar_w, max(0, int(bar_w * xp_pct)))
        if fill_w_xp > 0:
            pygame.draw.rect(xp_bar_surf, (120, 80, 220, 200), (0, 0, fill_w_xp, xp_bar_h), border_radius=2)
        self.screen.blit(xp_bar_surf, (bar_x, cur_y))
        lv_surf = self.font_hud.render(xp_text_left, True, WHITE)
        self.screen.blit(lv_surf, (bar_x + 4, cur_y + (xp_bar_h - lv_surf.get_height()) // 2))
        if xp_text_right:
            xp_num = self.font_hud.render(xp_text_right, True, WHITE)
            self.screen.blit(xp_num, (bar_x + bar_w - xp_num.get_width() - 4,
                                      cur_y + (xp_bar_h - xp_num.get_height()) // 2))
        cur_y += xp_bar_h + row_gap

        # Accent separator line
        self._draw_accent_line(cx, cur_y - 3, cx + inner_w, cur_y - 3, NEON_CYAN_DIM)

        # Row 5: ATK | DEF — equal-width columns, labels left, values right
        col_w = (inner_w - 20) // 2
        # ATK — left column
        atk_label_surf = self.font_hud.render("ATK", True, WHITE)
        atk_val_surf = self.font_stat.render(str(char.atk), True, soft_cyan)
        self.screen.blit(atk_label_surf, (cx + 5, cur_y + (stat_h - atk_label_surf.get_height()) // 2))
        self.screen.blit(atk_val_surf, (cx + col_w - atk_val_surf.get_width() - 5,
                                         cur_y + (stat_h - atk_val_surf.get_height()) // 2))
        # DEF — right column (20px gap)
        def_col_x = cx + col_w + 20
        def_label_surf = self.font_hud.render("DEF", True, WHITE)
        def_val_surf = self.font_stat.render(str(char.defn), True, soft_cyan)
        self.screen.blit(def_label_surf, (def_col_x + 5, cur_y + (stat_h - def_label_surf.get_height()) // 2))
        self.screen.blit(def_val_surf, (def_col_x + col_w - def_val_surf.get_width() - 5,
                                         cur_y + (stat_h - def_val_surf.get_height()) // 2))
        cur_y += stat_h + row_gap

        # Row 6-7: Equipment lines
        eq_max_w = inner_w - 10
        NO_EQ_COLOR = (180, 220, 255)

        if weapon:
            self._draw_hud_equip_line(cx + 5, cur_y, eq_max_w, weapon, is_weapon=True)
            cur_y += eq_h
        if armor:
            self._draw_hud_equip_line(cx + 5, cur_y, eq_max_w, armor, is_weapon=False)
            cur_y += eq_h

        if not weapon and not armor:
            empty_surf = self.font_hud.render("No equipment", True, NO_EQ_COLOR)
            self.screen.blit(empty_surf, (cx + (inner_w - empty_surf.get_width()) // 2,
                                           cur_y + (eq_h - empty_surf.get_height()) // 2))
            cur_y += eq_h

        # Set bonuses
        active_sets = char.get_active_sets()
        if active_sets:
            cur_y += row_gap
            for set_data in active_sets.values():
                set_text = f"SET: {set_data['description']}"
                set_surf = self.font_hud.render(set_text, True, GOLD)
                self.screen.blit(set_surf, (cx + 5, cur_y))
                cur_y += eq_h

        # Row 8: Consumables
        if char.consumables:
            cur_y += row_gap
            total_qty = sum(c.quantity for c in char.consumables)
            potion_text = f"Potions: {total_qty}"
            potion_surf = self.font_hud.render(potion_text, True, (100, 220, 100))
            self.screen.blit(potion_surf, (cx + 5, cur_y))

    def _draw_sprite(self, anim: SpriteAnim, surf, x: int, y: int, name: str = "Dragon"):
        """Draw an animated character sprite with idle bob, hit flash, and shadow."""
        dw, dh = surf.get_size()

        # Attack lunge offset
        atk_ox, atk_oy = anim.attack_offset
        # Idle bob
        bob_x, bob_y = anim.idle_offset

        sx = x - dw // 2 + atk_ox + bob_x
        sy = y - dh + atk_oy + bob_y

        # Shadow ellipse
        shadow_surf = pygame.Surface((dw - 10, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 80), (0, 0, dw - 10, 8))
        self.screen.blit(shadow_surf, (x - (dw - 10) // 2 + atk_ox, y - 4 + atk_oy))

        # Hit flash — tint white
        if anim.is_flash:
            flash = surf.copy()
            flash.fill((255, 255, 255, 180), special_flags=pygame.BLEND_RGBA_ADD)
            self.screen.blit(flash, (sx, sy))
        else:
            self.screen.blit(surf, (sx, sy))

        # Name below sprite
        name_surf = self.font_medium.render(name, True, WHITE)
        self.screen.blit(name_surf, (x - name_surf.get_width() // 2, y + 6))

    def _draw_sprites(self, combat: CombatManager, sprite_y: int):
        """Draw both character sprites with animations."""
        # Pre-load/generate sprites (cached in surface attrs for reuse)
        if not hasattr(self, '_sinon_surf'):
            self._sinon_surf = get_sinon_sprite()
        if not hasattr(self, '_enemy_surf') or getattr(self, '_cached_enemy_name', '') != combat.enemy.name:
            self._enemy_surf = get_enemy_sprite(combat.enemy.name)
            self._cached_enemy_name = combat.enemy.name

        # Focused glow around Sinon
        if combat.player.has_status("focused"):
            dw, dh = self._sinon_surf.get_size()
            glow_pulse = 0.5 + 0.5 * math.sin(self._pulse_timer * 0.01)
            glow = pygame.Surface((dw + 8, dh + 8), pygame.SRCALPHA)
            glow.fill((*GOLD, int(40 * glow_pulse)))
            sx = int(self.w * 0.25) - (dw + 8) // 2
            sy = sprite_y - dh - 4
            self.screen.blit(glow, (sx, sy))

        # Sinon
        self._draw_sprite(self._player_anim, self._sinon_surf,
                          int(self.w * 0.25), sprite_y, combat.player.name)
        # Enemy — attack animation goes toward player (negative direction)
        self._enemy_anim.attack_dir = -1
        self._draw_sprite(self._enemy_anim, self._enemy_surf,
                          int(self.w * 0.72), sprite_y, combat.enemy.name)
        self._enemy_anim.attack_dir = 1  # reset

    def _draw_hud_equip_line(self, x, y, max_w, item, is_weapon=True):
        """Draw a single equipment line inside the HUD — no truncation, scales font down if needed."""
        eq_gold = (200, 170, 50)
        slot_name = "Weapon" if is_weapon else "Armor"
        stat_parts = []
        for stat, value in item.stat_modifier.items():
            if stat in ("acc", "eva"):
                stat_parts.append(f"+{int(value * 100)}% {stat.upper()}")
            else:
                stat_parts.append(f"+{value} {stat.upper()}")
        stat_val = " ".join(stat_parts)
        full_text = f"{slot_name}: {item.name}  [{stat_val}]"

        # Try decreasing font sizes until it fits
        sizes = [15, 14, 13, 12, 11, 10]
        for size in sizes:
            font = pygame.font.SysFont("arial", size, bold=False)
            tw = font.size(full_text)[0]
            if tw <= max_w or size == sizes[-1]:
                surf = font.render(full_text, True, eq_gold)
                self.screen.blit(surf, (x + 5, y + (17 - surf.get_height()) // 2))
                break

    # ── COMMAND TRAY zone ──

    def _draw_tray(self, combat: CombatManager):
        tray_y = self._tray_top()
        tray_h = self._tray_height()

        # Dark gradient background for tray
        tray_surf = pygame.Surface((self.w, tray_h), pygame.SRCALPHA)
        for i in range(tray_h):
            grad_alpha = int(TRAY_BG_ALPHA * (0.6 + 0.4 * (i / max(1, tray_h))))
            pygame.draw.line(tray_surf, (PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], grad_alpha),
                             (0, i), (self.w, i))
        self.screen.blit(tray_surf, (0, tray_y))

        # Top border accent line
        self._draw_accent_line(0, tray_y, self.w, tray_y, NEON_CYAN, 2)

        # Dynamically size left/right sections
        is_skills = combat.state == TurnState.SKILL_SELECT
        menu_w = int(self.w * (0.58 if is_skills else 0.38))
        menu_pad = int(self.h * 0.018)

        if combat.state in (TurnState.MENU_SELECT, TurnState.PLAYER_ACTION):
            self._draw_command_buttons(combat, menu_pad, tray_y + menu_pad,
                                       menu_w - menu_pad * 2, tray_h - menu_pad * 2)
        elif combat.state == TurnState.SKILL_SELECT:
            self._draw_skill_menu(combat, menu_pad, tray_y + menu_pad,
                                  menu_w - menu_pad * 2, tray_h - menu_pad * 2)
        elif combat.state == TurnState.ITEM_SELECT:
            self._draw_item_menu(combat, menu_pad, tray_y + menu_pad,
                                 menu_w - menu_pad * 2, tray_h - menu_pad * 2)

        # Divider line
        self._draw_accent_line(menu_w, tray_y + int(tray_h * 0.1),
                                menu_w, tray_y + int(tray_h * 0.9), NEON_CYAN_DIM, 1)

        # Right section: Combat log (60% width)
        log_x = menu_w + int(self.w * 0.02)
        log_w = self.w - menu_w - int(self.w * 0.04)
        log_pad = 16
        self._draw_combat_log(combat, log_x + log_pad, tray_y + log_pad,
                              log_w - log_pad * 2, tray_h - log_pad * 2)

    def _draw_command_buttons(self, combat, x, y, w, h):
        """Draw command buttons as distinct items in the left section of the tray."""
        action_labels = {
            MenuAction.ATTACK: "Basic Strike",
            MenuAction.SKILL:  "Skills",
            MenuAction.ITEM:   "Items",
        }

        btn_h = min(42, (h - 20) // len(MENU_OPTIONS))
        btn_gap = 10
        inner_pad = 12

        for i, action in enumerate(MENU_OPTIONS):
            label = action_labels.get(action, str(action))
            btn_y = y + i * (btn_h + btn_gap)
            btn_rect = pygame.Rect(x, btn_y, w, btn_h)

            if i == combat.selected_index:
                pulse = self._pulse_brightness()
                sel_surf = pygame.Surface((w, btn_h), pygame.SRCALPHA)
                sel_surf.fill((*NEON_CYAN, int(50 * pulse)))
                self.screen.blit(sel_surf, (x, btn_y))
                pygame.draw.rect(self.screen, NEON_CYAN, btn_rect, 2, border_radius=5)
                text = f">  {label}"
                surf = self.font_medium.render(text, True, NEON_CYAN)
            else:
                unsel_bg = pygame.Surface((w, btn_h), pygame.SRCALPHA)
                unsel_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 140))
                self.screen.blit(unsel_bg, (x, btn_y))
                pygame.draw.rect(self.screen, NEON_CYAN_DIM, btn_rect, 1, border_radius=5)
                surf = self.font_medium.render(label, True, DIM_WHITE)

            self.screen.blit(surf, (x + inner_pad, btn_y + (btn_h - surf.get_height()) // 2))

    def _draw_skill_menu(self, combat, x, y, w, h):
        """Draw the skill sub-menu — padded buttons, wrapped desc, SP aligned to name row."""
        player = combat.player
        content_pad = 15    # padding from panel edges
        btn_pad_x = 14      # internal button horizontal padding
        btn_pad_y = 9       # internal button vertical padding
        btn_gap = 8         # gap between buttons
        btn_h = min(64, (h - content_pad * 2 - btn_gap) // max(1, len(SKILL_DEFS)))

        inner_w = w - content_pad * 2

        for i, skill in enumerate(SKILL_DEFS):
            btn_y = y + content_pad + i * (btn_h + btn_gap)
            btn_rect = pygame.Rect(x + content_pad, btn_y, inner_w, btn_h)
            cost = skill.get("cost", 0)
            can_afford = player.sp >= cost

            # Button background
            if i == combat.sub_selected_index:
                pulse = self._pulse_brightness()
                hl_color = NEON_CYAN if can_afford else RED
                sel_surf = pygame.Surface((inner_w, btn_h), pygame.SRCALPHA)
                sel_surf.fill((*hl_color, int(35 * pulse)))
                self.screen.blit(sel_surf, (btn_rect.x, btn_y))
                pygame.draw.rect(self.screen, hl_color, btn_rect, 2, border_radius=5)
            else:
                bg = pygame.Surface((inner_w, btn_h), pygame.SRCALPHA)
                bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 120))
                self.screen.blit(bg, (btn_rect.x, btn_y))
                pygame.draw.rect(self.screen, NEON_CYAN_DIM, btn_rect, 1, border_radius=5)

            # SP cost — right side, aligned with name row
            sp_color = NEON_CYAN if can_afford else RED
            sp_text = f"{cost} SP" if cost > 0 else "Free"
            sp_surf = self.font_hud.render(sp_text, True, sp_color)
            sp_x = btn_rect.x + inner_w - sp_surf.get_width() - btn_pad_x
            name_row_y = btn_y + btn_pad_y

            # Skill name (max width shrinks around SP cost)
            name_color = DIM_WHITE if not can_afford else (NEON_CYAN if i == combat.sub_selected_index else YELLOW)
            prefix = "> " if i == combat.sub_selected_index else ""
            full_name = prefix + skill["name"]
            name_max_w = sp_x - btn_pad_x - (btn_rect.x + btn_pad_x) - 10
            # Scale font down if name is too long
            name_font = self.font_stat
            if name_font.size(full_name)[0] > name_max_w:
                name_font = pygame.font.SysFont("arial", 16, bold=True)
            name_surf = name_font.render(full_name, True, name_color)
            self.screen.blit(name_surf, (btn_rect.x + btn_pad_x, name_row_y))
            self.screen.blit(sp_surf, (sp_x, name_row_y))

            # Description — wrap to fit
            desc_font = self.font_card_desc
            desc_lines = self._wrap_text(skill["desc"], desc_font, inner_w - btn_pad_x * 2)
            desc_y = name_row_y + name_surf.get_height() + 3
            for line in desc_lines[:2]:  # max 2 lines
                l_surf = desc_font.render(line, True, DIM_WHITE)
                self.screen.blit(l_surf, (btn_rect.x + btn_pad_x, desc_y))
                desc_y += l_surf.get_height() + 1

        # Bottom bar — SP display and hint with 15px margins
        sp_line = self.font_hud.render(f"SP: {player.sp}/{player.max_sp}", True, NEON_CYAN)
        self.screen.blit(sp_line, (x + content_pad, y + h - content_pad))
        hint = self.font_small.render("ESC/B: Back", True, (100, 100, 130))
        self.screen.blit(hint, (x + w - hint.get_width() - content_pad, y + h - content_pad))

    @staticmethod
    def _wrap_text(text: str, font, max_w: int) -> list:
        """Split text into lines that fit within max_w."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = current + " " + word if current else word
            if font.size(test)[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines if lines else [text]

    def _draw_item_menu(self, combat, x, y, w, h):
        """Draw the consumable item sub-menu — scrollable when many items."""
        player = combat.player
        items = player.consumables
        if not items:
            empty = self.font_medium.render("No consumable items.", True, DIM_WHITE)
            self.screen.blit(empty, (x + (w - empty.get_width()) // 2, y + h // 2 - 10))
            hint = self.font_small.render("ESC/B: Back", True, (100, 100, 130))
            self.screen.blit(hint, (x + w - hint.get_width() - 4, y + h - hint.get_height() - 2))
            return

        btn_h = 48
        btn_gap = 6
        row_h = btn_h + btn_gap
        max_visible = max(1, (h - 20) // row_h)
        max_scroll = max(0, len(items) - max_visible)

        # Add scroll tracking if not present
        if not hasattr(self, '_item_scroll'):
            self._item_scroll = 0

        # Clamp cursor + scroll
        if combat.sub_selected_index < self._item_scroll:
            self._item_scroll = combat.sub_selected_index
        elif combat.sub_selected_index >= self._item_scroll + max_visible:
            self._item_scroll = combat.sub_selected_index - max_visible + 1
        self._item_scroll = max(0, min(self._item_scroll, max_scroll))

        visible_end = min(len(items), self._item_scroll + max_visible)

        for vi, i in enumerate(range(self._item_scroll, visible_end)):
            item = items[i]
            btn_y = y + 4 + vi * row_h
            btn_rect = pygame.Rect(x, btn_y, w, btn_h)

            rarity_color = RARITY_COLOR.get(item.rarity, WHITE)

            if i == combat.sub_selected_index:
                pulse = self._pulse_brightness()
                sel_surf = pygame.Surface((w, btn_h), pygame.SRCALPHA)
                sel_surf.fill((*NEON_CYAN, int(45 * pulse)))
                self.screen.blit(sel_surf, (x, btn_y))
                pygame.draw.rect(self.screen, NEON_CYAN, btn_rect, 2, border_radius=5)
                name_text = f"> {item.name}"
                name_color = NEON_CYAN
            else:
                bg = pygame.Surface((w, btn_h), pygame.SRCALPHA)
                bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 130))
                self.screen.blit(bg, (x, btn_y))
                pygame.draw.rect(self.screen, NEON_CYAN_DIM, btn_rect, 1, border_radius=5)
                name_text = item.name
                name_color = rarity_color

            name_surf = self.font_medium.render(name_text, True, name_color)
            self.screen.blit(name_surf, (x + 10, btn_y + 5))

            qty = getattr(item, 'quantity', 1)
            desc_text = f"+{item.hp_restore} HP"
            if qty > 1:
                desc_text = f"x{qty}  {desc_text}"
            desc_surf = self.font_small.render(desc_text, True, WHITE)
            self.screen.blit(desc_surf, (x + 10, btn_y + 28))

        # HP + scroll indicator + hint
        hp_text = f"HP: {player.current_hp}/{player.max_hp}  |  {len(items)} items"
        hp_surf = self.font_hud.render(hp_text, True, DIM_WHITE)
        self.screen.blit(hp_surf, (x + 6, y + h - hp_surf.get_height() - 2))
        hint = self.font_small.render("ESC/B: Back", True, (100, 100, 130))
        self.screen.blit(hint, (x + w - hint.get_width() - 4, y + h - hint.get_height() - 2))

        # Scroll arrows
        if self._item_scroll > 0:
            arr = self.font_hud.render("^", True, (100, 100, 130))
            self.screen.blit(arr, (x + w // 2 - 10, y + 4))
        if self._item_scroll < max_scroll:
            arr = self.font_hud.render("v", True, (100, 100, 130))
            self.screen.blit(arr, (x + w // 2 + 10, y + 4))

    def _draw_combat_log(self, combat, x, y, w, h):
        """Draw the combat log with internal padding and scroll support."""
        inner_pad = 10
        line_h = 20
        line_gap = 4
        row_h = line_h + line_gap

        all_logs = combat._log
        max_visible = max(1, (h - inner_pad * 2) // row_h)

        # Clamp scroll offset
        max_scroll = max(0, len(all_logs) - max_visible)
        self._log_scroll_offset = min(self._log_scroll_offset, max_scroll)

        start = max(0, len(all_logs) - max_visible - self._log_scroll_offset)
        end = min(len(all_logs), start + max_visible)
        visible_logs = all_logs[start:end]

        # Glass panel background for the log area
        self._draw_glass_panel(x - 6, y - 6, w + 12, h + 12,
                               border_color=NEON_CYAN_DIM, border_alpha=100,
                               border_width=1, corner_radius=6)

        # Clip to prevent text overflow
        clip_rect = pygame.Rect(x + inner_pad, y + inner_pad, w - inner_pad * 2, h - inner_pad * 2)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        for i, msg in enumerate(visible_logs):
            truncated = _truncate_text(self.font_small, msg, w - inner_pad * 2)
            surf = self.font_small.render(truncated, True, WHITE)
            msg_y = y + h - inner_pad - (i + 1) * row_h + line_gap
            self.screen.blit(surf, (x + inner_pad, msg_y))

        self.screen.set_clip(old_clip)

        # Scroll indicator
        if self._log_scroll_offset > 0:
            hint = self.font_hud.render("^ More above", True, (100, 100, 130))
            self.screen.blit(hint, (x + (w - hint.get_width()) // 2, y + 2))

    # ── Inventory overlay ──

    def _draw_inventory_overlay(self, combat: CombatManager):
        t = self._inv_slide_progress
        eased = 1 - (1 - t) ** 3
        slide_offset = int(-420 * (1 - eased))

        panel_w = INV_PANEL_W
        panel_h = INV_PANEL_H
        px = (self.w - panel_w) // 2 + slide_offset
        py = (self.h - panel_h) // 2
        m = 18
        alpha_factor = eased

        backdrop = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, int(170 * alpha_factor)))
        self.screen.blit(backdrop, (0, 0))

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        border = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(border, (*NEON_CYAN, int(220 * alpha_factor)),
                         (0, 0, panel_w, panel_h), width=2, border_radius=8)
        self.screen.blit(border, (px, py))

        if alpha_factor < 0.3:
            return

        # Title + stats
        title_surf = self.font_xl.render("INVENTORY", True, NEON_CYAN)
        self.screen.blit(title_surf, (px + (panel_w - title_surf.get_width()) // 2, py + 10))
        p = combat.player
        atk_surf = self.font_stat.render(f"ATK {p.atk}", True, NEON_CYAN)
        def_surf = self.font_stat.render(f"DEF {p.defn}", True, NEON_CYAN)
        self.screen.blit(atk_surf, (px + panel_w - atk_surf.get_width() - m, py + 12))
        self.screen.blit(def_surf, (px + panel_w - def_surf.get_width() - m, py + 34))

        sep_y = py + 10 + title_surf.get_height() + 8
        pygame.draw.line(self.screen, NEON_CYAN_DIM, (px + m, sep_y), (px + panel_w - m, sep_y), 1)

        content_x = px + m
        content_w = panel_w - 2 * m
        in_equipped = combat.inv_section == "equipped"
        in_bag = combat.inv_section == "bag"

        # ── Equipped section ──
        eq_y = sep_y + 8
        eq_hdr_color = GOLD if in_equipped else DIM_WHITE
        eq_hdr_surf = self.font_medium.render("EQUIPPED" + ("  <" if in_equipped else ""), True, eq_hdr_color)
        self.screen.blit(eq_hdr_surf, (content_x, eq_y))
        eq_y += 24

        weapon = p.equipment.get("weapon")
        armor = p.equipment.get("armor")
        eq_slot_h = 34

        eq_panel_rect = pygame.Rect(content_x - 4, eq_y - 2, content_w + 8, eq_slot_h * 2 + 8)
        eq_panel_surf = pygame.Surface((eq_panel_rect.w, eq_panel_rect.h), pygame.SRCALPHA)
        eq_panel_surf.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 100))
        self.screen.blit(eq_panel_surf, (eq_panel_rect.x, eq_panel_rect.y))
        pygame.draw.rect(self.screen, NEON_CYAN if in_equipped else NEON_CYAN_DIM,
                         eq_panel_rect, 1, border_radius=4)

        # Weapon
        w_sel = in_equipped and combat.inv_equip_cursor == 0
        self._draw_equip_slot(content_x, eq_y, content_w, eq_slot_h, "W", weapon, w_sel, True)
        a_sel = in_equipped and combat.inv_equip_cursor == 1
        self._draw_equip_slot(content_x, eq_y + eq_slot_h, content_w, eq_slot_h, "A", armor, a_sel, False)
        eq_y += eq_slot_h * 2 + 14

        # ── Bag section ──
        bag_hdr_color = GOLD if in_bag else DIM_WHITE
        bag_hdr_surf = self.font_medium.render("BAG" + ("  <" if in_bag else ""), True, bag_hdr_color)
        self.screen.blit(bag_hdr_surf, (content_x, eq_y))
        eq_y += 24

        instr_reserved = 30
        bag_zone_top = eq_y - 2
        bag_zone_bottom = py + panel_h - instr_reserved - m
        bag_zone_h = bag_zone_bottom - bag_zone_top

        bag_panel_rect = pygame.Rect(content_x - 4, bag_zone_top, content_w + 8, bag_zone_h + 4)
        bag_panel_surf = pygame.Surface((bag_panel_rect.w, bag_panel_rect.h), pygame.SRCALPHA)
        bag_panel_surf.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 100))
        self.screen.blit(bag_panel_surf, (bag_panel_rect.x, bag_panel_rect.y))
        pygame.draw.rect(self.screen, NEON_CYAN if in_bag else NEON_CYAN_DIM,
                         bag_panel_rect, 1, border_radius=4)

        clip_rect = pygame.Rect(content_x, bag_zone_top, content_w, bag_zone_h)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)

        inventory = combat.player.inventory
        item_h = 40
        item_pad = 4
        max_items = max(1, bag_zone_h // (item_h + item_pad))

        if combat.inv_cursor < combat.inv_scroll_offset:
            combat.inv_scroll_offset = combat.inv_cursor
        elif combat.inv_cursor >= combat.inv_scroll_offset + max_items:
            combat.inv_scroll_offset = combat.inv_cursor - max_items + 1
        scroll = combat.inv_scroll_offset

        if not inventory:
            empty_surf = self.font_small.render("  (empty)", True, (80, 80, 100))
            self.screen.blit(empty_surf, (content_x + 4, bag_zone_top + 6))
        else:
            visible_count = min(len(inventory), scroll + max_items)
            for i in range(scroll, visible_count):
                v = i - scroll
                iy = bag_zone_top + 4 + v * (item_h + item_pad)
                if iy + item_h > bag_zone_bottom:
                    break
                item = inventory[i]
                bag_selected = in_bag and i == combat.inv_cursor
                self._draw_bag_item_row(content_x, iy, content_w, item_h, item, bag_selected)

            if visible_count < len(inventory):
                remaining = len(inventory) - visible_count
                last_v = visible_count - scroll
                more_y = bag_zone_top + 4 + last_v * (item_h + item_pad)
                if more_y + item_h <= bag_zone_bottom:
                    more_surf = self.font_small.render(f"+{remaining} more...", True, DIM_WHITE)
                    self.screen.blit(more_surf, (content_x + 4, more_y + (item_h - more_surf.get_height()) // 2))

        self.screen.set_clip(old_clip)

        # Instructions
        instr_y = py + panel_h - instr_reserved
        instr_text = "Tab: Section   W/S: Nav   E: Equip   U: Unequip   F: Sort   ESC: Back"
        instr_surf = self.font_small.render(instr_text, True, (100, 100, 130))
        self.screen.blit(instr_surf, (px + (panel_w - instr_surf.get_width()) // 2, instr_y + 6))

    def _draw_equip_slot(self, x, y, w, h, slot_label, item, selected, is_weapon):
        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._pulse_timer * 0.008)
            sel_bg = pygame.Surface((w, h), pygame.SRCALPHA)
            sel_bg.fill((*NEON_CYAN, int(35 * pulse)))
            self.screen.blit(sel_bg, (x, y))

        if item:
            accent = RARITY_ACCENT.get(item.rarity, (60, 60, 75))
            pygame.draw.rect(self.screen, accent, (x + 6, y + 6, 3, h - 12), border_radius=1)
            stat_val = f"+{item.atk} ATK" if is_weapon else f"+{item.defense} DEF"
            label_text = "Weapon" if is_weapon else "Armor"
            full = f"{label_text}: {item.name}  [{stat_val}]"
            if selected:
                full = f"> {full}"
                color = NEON_CYAN
            else:
                color = RARITY_COLOR.get(item.rarity, WHITE)
            surf = self.font_small.render(full, True, color)
            try_font = self.font_small
            if surf.get_width() > w - 14:
                for sz in (14, 13, 12):
                    try_font = pygame.font.SysFont("arial", sz, bold=False)
                    surf = try_font.render(full, True, color)
                    if surf.get_width() <= w - 14 or sz == 12:
                        break
            self.screen.blit(surf, (x + 12, y + (h - surf.get_height()) // 2))
        else:
            text = f"{'Weapon' if is_weapon else 'Armor'}: (empty)"
            if selected:
                text = f"> {text}"
                color = NEON_CYAN
            else:
                color = (80, 80, 100)
            surf = self.font_small.render(text, True, color)
            self.screen.blit(surf, (x + 12, y + (h - surf.get_height()) // 2))

    def _draw_bag_item_row(self, x, y, w, h, item, selected):
        from item import Weapon
        rarity_c = RARITY_COLOR.get(item.rarity, WHITE)
        accent_c = RARITY_ACCENT.get(item.rarity, (60, 60, 75))
        is_weapon = isinstance(item, Weapon)
        slot_name = "W" if is_weapon else "A"
        stat_val = f"+{item.atk} ATK" if is_weapon else f"+{item.defense} DEF"

        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._pulse_timer * 0.008)
            sel_bg = pygame.Surface((w, h), pygame.SRCALPHA)
            sel_bg.fill((*NEON_CYAN, int(30 * pulse)))
            self.screen.blit(sel_bg, (x, y))

        pygame.draw.rect(self.screen, accent_c, (x + 4, y + 6, 3, h - 12), border_radius=1)

        full = f"[{slot_name}] {item.name}  [{stat_val}]"
        if selected:
            full = f"> {full}"
            color = NEON_CYAN
        else:
            color = rarity_c
        surf = self.font_small.render(full, True, color)
        self.screen.blit(surf, (x + 12, y + (h - surf.get_height()) // 2))