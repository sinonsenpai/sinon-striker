"""
Sprite module — programmatic pixel-art character sprites and animations.
Drawn with pygame.draw primitives, no external image files needed.
"""

import math
import pygame

SPRITE_BASE_W, SPRITE_BASE_H = 24, 32
SPRITE_DISPLAY_W, SPRITE_DISPLAY_H = 72, 96
SCALE_FACTOR = SPRITE_DISPLAY_W / SPRITE_BASE_W


def make_pixel_sprite(draw_func, base_size=None, display_size=None):
    """Draw on a small surface and scale up with NEAREST neighbour for crisp pixels."""
    bw, bh = base_size or (SPRITE_BASE_W, SPRITE_BASE_H)
    dw, dh = display_size or (SPRITE_DISPLAY_W, SPRITE_DISPLAY_H)
    small = pygame.Surface((bw, bh), pygame.SRCALPHA)
    draw_func(small, bw, bh)
    return pygame.transform.scale(small, (dw, dh))


# ── Animation state ────────────────────────────────────────────────────

class SpriteAnim:
    """Tracks animation state for a character sprite."""
    def __init__(self):
        self.age_ms = 0.0
        self.hit_timer = 0.0
        self.attack_timer = 0.0
        self.attack_dir = 1  # 1 = forward, -1 = backward

    def update(self, dt_ms: float):
        self.age_ms += dt_ms
        if self.hit_timer > 0:
            self.hit_timer = max(0, self.hit_timer - dt_ms)
        if self.attack_timer > 0:
            self.attack_timer = max(0, self.attack_timer - dt_ms)

    def trigger_hit(self):
        self.hit_timer = 200

    def trigger_attack(self):
        self.attack_timer = 200

    @property
    def idle_offset(self) -> tuple:
        bob = int(math.sin(self.age_ms * 0.004) * 2)
        return (0, bob)

    @property
    def attack_offset(self) -> tuple:
        if self.attack_timer <= 0:
            return (0, 0)
        t = self.attack_timer / 200
        dist = int(15 * max(0, (t if t < 0.5 else 1 - t) * 2))
        return (dist * self.attack_dir, 0)

    @property
    def is_flash(self) -> bool:
        return self.hit_timer > 0


# ── Sinon Sprite ───────────────────────────────────────────────────────

def _draw_sinon(surf, w, h):
    """Draw Sinon at base resolution (24x32) with navy body, cyan hair, scarf, sword."""
    cx, cy = w // 2, h // 2

    # -- Legs --
    leg_w, leg_h = 5, 9
    leg_y = 22
    pygame.draw.rect(surf, (35, 35, 50), (cx - leg_w - 2, leg_y, leg_w, leg_h))
    pygame.draw.rect(surf, (30, 30, 45), (cx + 2, leg_y, leg_w, leg_h))

    # -- Body (torso) --
    body_w, body_h = 12, 14
    body_x, body_y = cx - body_w // 2, 10
    pygame.draw.rect(surf, (20, 30, 60), (body_x, body_y, body_w, body_h), border_radius=2)

    # -- Hair (spiky polygon above body) --
    hair_points = [
        (cx - 5, body_y),       # left base
        (cx - 3, body_y - 7),   # left spike
        (cx - 1, body_y - 3),   # mid-left
        (cx, body_y - 8),       # top spike
        (cx + 1, body_y - 3),   # mid-right
        (cx + 4, body_y - 7),   # right spike
        (cx + 6, body_y),       # right base
    ]
    pygame.draw.polygon(surf, (0, 180, 255), hair_points)

    # -- Eyes --
    eye_y = 14
    pygame.draw.circle(surf, (255, 255, 255), (cx - 2, eye_y), 2)
    pygame.draw.circle(surf, (255, 255, 255), (cx + 3, eye_y), 2)
    pygame.draw.circle(surf, (0, 200, 255), (cx - 2, eye_y), 1)
    pygame.draw.circle(surf, (0, 200, 255), (cx + 3, eye_y), 1)

    # -- Scarf --
    scarf_points = [(body_x + body_w, body_y + 3), (body_x + body_w + 5, body_y + 7),
                    (body_x + body_w + 3, body_y + 4)]
    pygame.draw.polygon(surf, (0, 240, 255), scarf_points)

    # -- Sword (thin cyan line) --
    sword_start = (body_x - 1, body_y + 5)
    sword_end = (body_x - 1, body_y - 2)
    pygame.draw.line(surf, (0, 240, 255), sword_start, sword_end, 2)
    # crossguard
    gx, gy = body_x - 1, body_y + 5
    pygame.draw.line(surf, (0, 200, 255), (gx - 2, gy), (gx + 2, gy), 1)


def get_sinon_sprite():
    return make_pixel_sprite(_draw_sinon)


# ── Enemy Sprites ──────────────────────────────────────────────────────

def _draw_slime(surf, w, h):
    """Green blob — ellipse body with eyes."""
    cx, cy = w // 2, h // 2
    # Body
    body_rect = (cx - 8, cy - 6, 16, 16)
    pygame.draw.ellipse(surf, (60, 200, 80), body_rect)
    # Highlight
    hl_rect = (cx - 4, cy - 5, 6, 4)
    pygame.draw.ellipse(surf, (100, 240, 120), hl_rect)
    # Eyes
    pygame.draw.ellipse(surf, (255, 255, 255), (cx - 5, cy - 3, 5, 6))
    pygame.draw.ellipse(surf, (255, 255, 255), (cx + 1, cy - 3, 5, 6))
    pygame.draw.circle(surf, (0, 0, 0), (cx - 3, cy), 1)
    pygame.draw.circle(surf, (0, 0, 0), (cx + 3, cy), 1)


def _draw_dragon(surf, w, h):
    """Red dragon — body, wings, tail, yellow eyes."""
    cx, cy = w // 2, h // 2
    # Body
    body_rect = (cx - 7, cy - 4, 14, 14)
    pygame.draw.rect(surf, (180, 40, 40), body_rect, border_radius=3)
    # Head triangle
    head_points = [(cx + 7, cy - 4), (cx + 7, cy + 1), (cx + 14, cy - 2)]
    pygame.draw.polygon(surf, (200, 50, 50), head_points)
    # Wings
    wing_left = [(cx - 7, cy - 2), (cx - 12, cy - 8), (cx - 7, cy - 4)]
    wing_right = [(cx + 7, cy - 6), (cx + 7, cy), (cx + 12, cy - 8)]
    pygame.draw.polygon(surf, (140, 30, 30), wing_left)
    pygame.draw.polygon(surf, (140, 30, 30), wing_right)
    # Eyes
    pygame.draw.circle(surf, (255, 240, 60), (cx + 10, cy - 3), 1)
    # Tail
    tail_start = (cx - 7, cy + 4)
    tail_end = (cx - 14, cy + 8)
    pygame.draw.line(surf, (180, 40, 40), tail_start, tail_end, 2)


def _draw_vanguard(surf, w, h):
    """Large purple brute — bulky body, arms, orange eyes, club."""
    cx, cy = w // 2, h // 2
    # Body
    pygame.draw.rect(surf, (60, 20, 80), (cx - 8, cy - 5, 16, 16), border_radius=2)
    # Head
    pygame.draw.rect(surf, (80, 30, 100), (cx - 5, cy - 11, 10, 8), border_radius=2)
    # Arms
    pygame.draw.rect(surf, (50, 15, 70), (cx - 12, cy - 3, 4, 12))   # left arm
    pygame.draw.rect(surf, (50, 15, 70), (cx + 8, cy - 3, 4, 12))    # right arm
    # Eyes
    pygame.draw.circle(surf, (255, 160, 40), (cx - 2, cy - 8), 2)
    pygame.draw.circle(surf, (255, 160, 40), (cx + 2, cy - 8), 2)
    # Club
    club_x, club_y = cx + 10, cy - 3
    pygame.draw.rect(surf, (100, 60, 30), (club_x - 1, club_y - 4, 3, 10))  # handle
    pygame.draw.polygon(surf, (120, 120, 120), [(club_x - 3, club_y - 4),
                                                   (club_x + 4, club_y - 4),
                                                   (club_x + 1, club_y - 8)])  # axe head


ENEMY_DRAW_FUNCS = {
    "Slime": _draw_slime,
    "Dragon": _draw_dragon,
    "Vanguard Brute": _draw_vanguard,
}


def get_enemy_sprite(enemy_name: str):
    draw = ENEMY_DRAW_FUNCS.get(enemy_name, _draw_slime)
    return make_pixel_sprite(draw)


# ── Hub Sinon (smaller) ────────────────────────────────────────────────

def get_hub_sinon():
    """Smaller Sinon sprite for the hub town (32x48 display size)."""
    return make_pixel_sprite(_draw_sinon, display_size=(32, 48))
