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


def _draw_wisp(surf, w, h):
    """Floating flame spirit — orange teardrop with glowing eye."""
    cx, cy = w // 2, h // 2
    # Flame body (teardrop shape)
    flame = [(cx, cy - 8), (cx - 6, cy + 2), (cx + 6, cy + 2)]
    pygame.draw.polygon(surf, (255, 120, 20), flame)
    # Inner glow
    inner = [(cx, cy - 5), (cx - 3, cy + 1), (cx + 3, cy + 1)]
    pygame.draw.polygon(surf, (255, 200, 60), inner)
    # Floating wisps
    for dx, dy in [(-8, -4), (8, -4), (-6, 2), (6, 2)]:
        pygame.draw.circle(surf, (255, 160, 40), (cx + dx, cy + dy), 1)
    # Eye
    pygame.draw.circle(surf, (255, 255, 200), (cx, cy - 2), 2)
    pygame.draw.circle(surf, (255, 255, 255), (cx, cy - 2), 1)


def _draw_cultist(surf, w, h):
    """Dark magic user — purple robe, hood, red eyes."""
    cx, cy = w // 2, h // 2
    # Robe body
    pygame.draw.polygon(surf, (50, 15, 60), [(cx - 7, cy + 4), (cx, cy - 2), (cx + 7, cy + 4), (cx + 4, cy + 10), (cx - 4, cy + 10)])
    # Hood (pointed)
    hood_points = [(cx - 6, cy + 2), (cx, cy - 10), (cx + 6, cy + 2)]
    pygame.draw.polygon(surf, (40, 10, 50), hood_points)
    # Eyes (glowing red)
    pygame.draw.circle(surf, (255, 30, 30), (cx - 2, cy - 2), 2)
    pygame.draw.circle(surf, (255, 30, 30), (cx + 2, cy - 2), 2)
    pygame.draw.circle(surf, (255, 100, 100), (cx - 2, cy - 2), 1)
    pygame.draw.circle(surf, (255, 100, 100), (cx + 2, cy - 2), 1)
    # Dark aura (fixed positions)
    for ax, ay in [(cx - 6, cy + 8), (cx, cy + 10), (cx + 6, cy + 7)]:
        pygame.draw.circle(surf, (80, 20, 100), (ax, ay), 1)


def _draw_golem(surf, w, h):
    """Stone guardian — big gray blocks, cracks, glowing core."""
    cx, cy = w // 2, h // 2
    # Body
    pygame.draw.rect(surf, (90, 85, 75), (cx - 9, cy - 2, 18, 16), border_radius=2)
    # Head
    pygame.draw.rect(surf, (100, 95, 85), (cx - 6, cy - 10, 12, 10), border_radius=2)
    # Shoulder plates
    pygame.draw.rect(surf, (80, 75, 65), (cx - 11, cy - 2, 22, 4), border_radius=1)
    # Arms
    pygame.draw.rect(surf, (85, 80, 70), (cx - 12, cy + 2, 4, 8))
    pygame.draw.rect(surf, (85, 80, 70), (cx + 8, cy + 2, 4, 8))
    # Core (glowing orange)
    pygame.draw.circle(surf, (255, 140, 30), (cx, cy + 4), 3)
    pygame.draw.circle(surf, (255, 200, 100), (cx, cy + 4), 1)
    # Crack lines
    pygame.draw.line(surf, (60, 55, 45), (cx - 2, cy - 6), (cx - 4, cy - 2), 1)
    pygame.draw.line(surf, (60, 55, 45), (cx + 3, cy - 7), (cx + 5, cy - 3), 1)
    # Eyes (empty sockets)
    pygame.draw.circle(surf, (30, 28, 25), (cx - 3, cy - 6), 2)
    pygame.draw.circle(surf, (30, 28, 25), (cx + 3, cy - 6), 2)


def _draw_shadow_stalker(surf, w, h):
    """Stealth assassin — dark slender, cape, green eyes."""
    cx, cy = w // 2, h // 2
    # Cape (wide dark triangle)
    cape_points = [(cx - 9, cy - 2), (cx, cy + 12), (cx + 9, cy - 2)]
    pygame.draw.polygon(surf, (15, 15, 25), cape_points)
    # Body (lean)
    pygame.draw.rect(surf, (25, 25, 40), (cx - 4, cy - 4, 8, 14), border_radius=1)
    # Hood/mask
    pygame.draw.polygon(surf, (20, 20, 35), [(cx - 5, cy), (cx, cy - 10), (cx + 5, cy)])
    # Eyes (glowing green)
    pygame.draw.circle(surf, (50, 255, 80), (cx - 2, cy - 4), 2)
    pygame.draw.circle(surf, (50, 255, 80), (cx + 2, cy - 4), 2)
    pygame.draw.circle(surf, (150, 255, 180), (cx - 2, cy - 4), 1)
    pygame.draw.circle(surf, (150, 255, 180), (cx + 2, cy - 4), 1)
    # Dagger
    pygame.draw.line(surf, (180, 180, 200), (cx + 5, cy + 2), (cx + 12, cy - 4), 1)
    pygame.draw.line(surf, (200, 200, 220), (cx + 12, cy - 4), (cx + 14, cy - 6), 1)


def _draw_abyssal_warden(surf, w, h):
    """Abyssal Warden boss — large demonic form, dark red/gold."""
    cx, cy = w // 2, h // 2
    # Body
    pygame.draw.rect(surf, (120, 15, 25), (cx - 9, cy - 3, 18, 18), border_radius=3)
    # Head
    pygame.draw.polygon(surf, (140, 20, 30), [(cx - 6, cy - 4), (cx, cy - 12), (cx + 6, cy - 4)])
    # Horns
    pygame.draw.polygon(surf, (200, 180, 60), [(cx - 4, cy - 10), (cx - 7, cy - 16), (cx - 2, cy - 10)])
    pygame.draw.polygon(surf, (200, 180, 60), [(cx + 4, cy - 10), (cx + 7, cy - 16), (cx + 2, cy - 10)])
    # Eyes (white with red pupil)
    pygame.draw.circle(surf, (255, 255, 255), (cx - 3, cy - 7), 2)
    pygame.draw.circle(surf, (255, 255, 255), (cx + 3, cy - 7), 2)
    pygame.draw.circle(surf, (255, 20, 20), (cx - 3, cy - 7), 1)
    pygame.draw.circle(surf, (255, 20, 20), (cx + 3, cy - 7), 1)
    # Wings
    wing_left = [(cx - 9, cy), (cx - 16, cy - 6), (cx - 8, cy + 2)]
    wing_right = [(cx + 9, cy), (cx + 16, cy - 6), (cx + 8, cy + 2)]
    pygame.draw.polygon(surf, (80, 10, 15), wing_left)
    pygame.draw.polygon(surf, (80, 10, 15), wing_right)
    # Gold trim
    pygame.draw.rect(surf, (200, 180, 60), (cx - 9, cy + 13, 18, 2))
    pygame.draw.rect(surf, (200, 180, 60), (cx - 7, cy + 4, 2, 8))
    pygame.draw.rect(surf, (200, 180, 60), (cx + 5, cy + 4, 2, 8))


ENEMY_DRAW_FUNCS = {
    "Slime": _draw_slime,
    "Dragon": _draw_dragon,
    "Vanguard Brute": _draw_vanguard,
    "Wisp": _draw_wisp,
    "Cultist": _draw_cultist,
    "Golem": _draw_golem,
    "Shadow Stalker": _draw_shadow_stalker,
    "Abyssal Warden": _draw_abyssal_warden,
}


def get_enemy_sprite(enemy_name: str):
    draw = ENEMY_DRAW_FUNCS.get(enemy_name, _draw_slime)
    return make_pixel_sprite(draw)


# ── Skill Icons ───────────────────────────────────────────────────────

def _icon_star(surf, w, h):
    """Star-Shatter Strike — four-pointed cyan star."""
    cx, cy = w // 2, h // 2
    color = (0, 240, 255)
    pts = [(cx, cy - 6), (cx + 2, cy - 2), (cx + 6, cy), (cx + 2, cy + 2),
           (cx, cy + 6), (cx - 2, cy + 2), (cx - 6, cy), (cx - 2, cy - 2)]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.circle(surf, (100, 250, 255), (cx, cy), 2)


def _icon_target(surf, w, h):
    """Astral Focus — crosshair/target reticle."""
    cx, cy = w // 2, h // 2
    color = (0, 210, 230)
    pygame.draw.circle(surf, color, (cx, cy), 6, 1)
    pygame.draw.line(surf, color, (cx, cy - 5), (cx, cy + 5), 1)
    pygame.draw.line(surf, color, (cx - 5, cy), (cx + 5, cy), 1)
    pygame.draw.circle(surf, (100, 240, 255), (cx, cy), 2)


def _icon_flame(surf, w, h):
    """Blazing Strike — orange/red flame."""
    cx, cy = w // 2, h // 2
    flame_pts = [(cx, cy - 7), (cx - 4, cy - 1), (cx - 2, cy + 3), (cx, cy + 6),
                 (cx + 2, cy + 3), (cx + 4, cy - 1)]
    pygame.draw.polygon(surf, (255, 120, 20), flame_pts)
    inner_pts = [(cx, cy - 4), (cx - 2, cy - 1), (cx, cy + 3), (cx + 2, cy - 1)]
    pygame.draw.polygon(surf, (255, 200, 60), inner_pts)


def _icon_drip(surf, w, h):
    """Venom Strike — green poison drip."""
    cx, cy = w // 2, h // 2
    color = (80, 200, 60)
    drip_pts = [(cx, cy - 6), (cx - 4, cy + 1), (cx + 4, cy + 1)]
    pygame.draw.polygon(surf, color, drip_pts)
    pygame.draw.circle(surf, color, (cx, cy + 4), 2)
    highlight = [(cx, cy - 3), (cx - 1, cy), (cx + 1, cy)]
    pygame.draw.polygon(surf, (140, 240, 120), highlight)


def _icon_bolt(surf, w, h):
    """Shockwave — yellow lightning bolt."""
    cx, cy = w // 2, h // 2
    color = (255, 230, 60)
    bolt_pts = [(cx + 2, cy - 6), (cx - 2, cy - 1), (cx + 1, cy - 1),
                (cx - 2, cy + 5), (cx + 1, cy + 1), (cx - 1, cy + 1)]
    pygame.draw.polygon(surf, color, bolt_pts)
    pygame.draw.circle(surf, (255, 250, 200), (cx - 1, cy - 5), 1)


SKILL_ICONS = {
    "Star-Shatter Strike": _icon_star,
    "Astral Focus": _icon_target,
    "Blazing Strike": _icon_flame,
    "Venom Strike": _icon_drip,
    "Shockwave": _icon_bolt,
}


def get_skill_icon(skill_name: str):
    """Return a 32x32 pixel-art icon surface for the given skill name."""
    draw = SKILL_ICONS.get(skill_name)
    if draw is None:
        return pygame.Surface((32, 32), pygame.SRCALPHA)
    return make_pixel_sprite(draw, base_size=(16, 16), display_size=(32, 32))


# ── Hub Sinon (smaller) ────────────────────────────────────────────────

def get_hub_sinon():
    """Smaller Sinon sprite for the hub town (32x48 display size)."""
    return make_pixel_sprite(_draw_sinon, display_size=(32, 48))
