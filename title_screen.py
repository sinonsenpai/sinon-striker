"""
Title Screen - starfield background, glowing SINON STRIKER title, and menu options.
"""

import math
import random
import sys
import os
import pygame

BG_COLOR = (18, 14, 30)
NEON_CYAN = (0, 240, 255)
NEON_CYAN_DIM = (0, 100, 120)
GOLD = (255, 215, 0)
GOLD_DIM = (120, 100, 30)
WHITE = (230, 230, 245)
DIM_WHITE = (160, 160, 180)
STAR_COLOR = (180, 200, 230)

SAVE_FILE = "save_data.json"

STAR_COUNT = 130
BURST_PARTICLE_COUNT = 16
BURST_LIFETIME_MS = 700
BURST_SPEED = 2.5


class Star:
    """A single drifting, twinkling star particle."""
    def __init__(self, w: int, h: int, init: bool = True):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h) if init else -5.0
        self.size = random.uniform(0.8, 2.8)
        self.speed = random.uniform(0.2, 1.2) * self.size * 0.6
        self.brightness = random.uniform(100, 240)
        self.twinkle_rate = random.uniform(0.015, 0.06)
        self.phase = random.uniform(0, math.pi * 2)
        self.is_cyan = random.random() < 0.18

    def update(self, dt_ms: int, w: int, h: int):
        self.y += self.speed * dt_ms / 16.0
        if self.y > h + 10:
            self.y = -5.0
            self.x = random.uniform(0, w)
            self.speed = random.uniform(0.2, 1.2) * self.size * 0.6

    def alpha(self, time_ms: float) -> int:
        wave = 0.55 + 0.45 * math.sin(time_ms * self.twinkle_rate + self.phase)
        return max(0, min(255, int(self.brightness * wave)))


class BurstParticle:
    """A particle that flies outward from a burst point."""
    def __init__(self, x: float, y: float):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(1.0, BURST_SPEED)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life_ms = random.uniform(300, 600)
        self.max_life = self.life_ms
        self.is_gold = random.random() < 0.25

    def update(self, dt_ms: int):
        self.x += self.vx * dt_ms / 16.0
        self.y += self.vy * dt_ms / 16.0
        self.life_ms -= dt_ms

    @property
    def alive(self) -> bool:
        return self.life_ms > 0

    @property
    def alpha(self) -> int:
        return max(0, min(255, int(255 * self.life_ms / self.max_life)))


class ParticleBurst:
    """A group of particles emitted at a screen position."""
    def __init__(self, x: int, y: int):
        self.particles = [BurstParticle(float(x), float(y)) for _ in range(BURST_PARTICLE_COUNT)]
        self.age_ms = 0

    def update(self, dt_ms: int):
        self.age_ms += dt_ms
        for p in self.particles:
            p.update(dt_ms)

    @property
    def alive(self) -> bool:
        return self.age_ms < BURST_LIFETIME_MS or any(p.alive for p in self.particles)


class TitleScreen:
    """Renders and manages the title screen state."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.w, self.h = screen.get_size()

        # ── Stars ──
        self.stars = [Star(self.w, self.h, init=True) for _ in range(STAR_COUNT)]
        self._elapsed_ms = 0.0

        # ── Fonts ──
        self.font_title = pygame.font.SysFont("arial", 62, bold=True)
        self.font_subtitle = pygame.font.SysFont("arial", 22, bold=False)
        self.font_menu = pygame.font.SysFont("arial", 28, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16, bold=False)
        self.font_hint = pygame.font.SysFont("arial", 15, bold=False)

        # ── Menu ──
        self._has_save = os.path.exists(SAVE_FILE)
        if self._has_save:
            self.menu_options = ["Continue", "New Game", "Options", "Quit"]
        else:
            self.menu_options = ["New Game", "Options", "Quit"]
        self.selected_index = 0
        self.cursor_icon = ">"
        self._chosen_action = None  # "continue" or "new_game"

        # ── Fade ──
        self.fade_alpha = 0.0   # 0..255
        self._fade_target = 0.0
        self._fade_speed = 0.0   # units per ms

        # ── Bursts ──
        self.bursts: list[ParticleBurst] = []

        # ── Placeholder message ──
        self._placeholder_text = ""
        self._placeholder_timer = 0

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def move_up(self):
        self.selected_index = (self.selected_index - 1) % len(self.menu_options)

    def move_down(self):
        self.selected_index = (self.selected_index + 1) % len(self.menu_options)

    def confirm(self):
        """Returns an action string or None."""
        if self._has_save:
            # Menu: Continue, New Game, Options, Quit
            if self.selected_index == 0:
                self._start_fade(255, 0.52)
                self._chosen_action = "continue"
                return "continue"
            elif self.selected_index == 1:
                self._start_fade(255, 0.52)
                self._chosen_action = "new_game"
                return "new_game"
            elif self.selected_index == 2:
                return "options"
            elif self.selected_index == 3:
                pygame.quit()
                sys.exit()
        else:
            # Menu: New Game, Options, Quit
            if self.selected_index == 0:
                self._start_fade(255, 0.52)
                self._chosen_action = "new_game"
                return "new_game"
            elif self.selected_index == 1:
                return "options"
            elif self.selected_index == 2:
                pygame.quit()
                sys.exit()

    def enter_options(self, snd):
        from options_screen import OptionsScreen
        return OptionsScreen(self.screen, snd)

    def trigger_burst(self, x: int, y: int):
        self.bursts.append(ParticleBurst(x, y))

    def update(self, dt_ms: int):
        self._elapsed_ms += dt_ms

        # Stars
        for star in self.stars:
            star.update(dt_ms, self.w, self.h)

        # Bursts (update & cull dead)
        for burst in self.bursts:
            burst.update(dt_ms)
        self.bursts = [b for b in self.bursts if b.alive]

        # Fade
        if self.fade_alpha != self._fade_target:
            step = self._fade_speed * dt_ms
            if self._fade_target > self.fade_alpha:
                self.fade_alpha = min(self._fade_target, self.fade_alpha + step)
            else:
                self.fade_alpha = max(self._fade_target, self.fade_alpha - step)

        # Placeholder timer
        if self._placeholder_timer > 0:
            self._placeholder_timer -= dt_ms
            if self._placeholder_timer <= 0:
                self._placeholder_text = ""

    @property
    def fade_done(self) -> bool:
        return self.fade_alpha >= 255 and self._fade_target == 255

    @property
    def chosen_action(self) -> str:
        """Returns 'continue' or 'new_game' after confirm()."""
        return self._chosen_action

    def start_fade_in(self):
        self.fade_alpha = 255.0
        self._start_fade(0, 0.52)

    def draw(self, dt_ms: int):
        self.screen.fill(BG_COLOR)

        # ── Starfield ──
        for star in self.stars:
            a = star.alpha(self._elapsed_ms)
            if a < 20:
                continue
            if star.is_cyan:
                color = (0, min(255, a + 80), min(255, a + 80))
            else:
                color = (a, a, a)
            r = max(1, int(star.size))
            pygame.draw.circle(self.screen, color, (int(star.x), int(star.y)), r)

        # ── Particle bursts ──
        for burst in self.bursts:
            for p in burst.particles:
                if p.alive:
                    a = p.alpha
                    if a < 20:
                        continue
                    if p.is_gold:
                        c = (GOLD[0], GOLD[1], GOLD[2])
                    else:
                        c = NEON_CYAN
                    bright = int(a / 255.0 * 150 + 60)
                    color = tuple(min(255, ch * bright // 200) for ch in c)
                    pygame.draw.circle(self.screen, color, (int(p.x), int(p.y)), 2)

        # ── Title glow aura (multiple expanding layers with reduced alpha) ──
        title_text = "SINON STRIKER"
        glow_layers = [
            (NEON_CYAN, 20, 10),
            (NEON_CYAN_DIM, 50, 7),
            (GOLD_DIM, 35, 4),
            (NEON_CYAN, 80, 2),
        ]
        for color, alpha, expand in glow_layers:
            glow_surf = self.font_title.render(title_text, True, color)
            w2, h2 = glow_surf.get_width() + expand * 2, glow_surf.get_height() + expand * 2
            scaled = pygame.transform.scale(glow_surf, (w2, h2))
            alpha_surf = pygame.Surface((w2, h2), pygame.SRCALPHA)
            alpha_surf.blit(scaled, (0, 0))
            alpha_surf.set_alpha(alpha)
            x_pos = (self.w - w2) // 2
            y_pos = int(self.h * 0.22) - expand
            self.screen.blit(alpha_surf, (x_pos, y_pos))

        # ── Main title (gold, with subtle pulse) ──
        pulse = 0.88 + 0.12 * math.sin(self._elapsed_ms * 0.0025)
        title_surf = self.font_title.render(title_text, True, (*GOLD, int(255 * pulse)))
        title_y = int(self.h * 0.22)
        self.screen.blit(title_surf, ((self.w - title_surf.get_width()) // 2, title_y))

        # ── Subtitle ──
        sub_text = "Shatter the Stars"
        sub_surf = self.font_subtitle.render(sub_text, True, DIM_WHITE)
        sub_y = title_y + self.font_title.get_height() + 12
        self.screen.blit(sub_surf, ((self.w - sub_surf.get_width()) // 2, sub_y))

        # ── Menu options ──
        menu_start_y = int(self.h * 0.55)
        spacing = 42
        menu_w = 260
        menu_h = 38

        for i, option in enumerate(self.menu_options):
            opt_y = menu_start_y + i * spacing
            bg_x = (self.w - menu_w) // 2
            bg_y = opt_y - 5

            if i == self.selected_index:
                pulse_m = 0.7 + 0.3 * math.sin(self._elapsed_ms * 0.0055)
                # Glass-like selection panel
                sel_surf = pygame.Surface((menu_w, menu_h), pygame.SRCALPHA)
                sel_surf.fill((15, 10, 35, int(180 * pulse_m)))
                self.screen.blit(sel_surf, (bg_x, bg_y))
                pygame.draw.rect(self.screen, NEON_CYAN, (bg_x, bg_y, menu_w, menu_h),
                                 1, border_radius=5)
                text = f"{self.cursor_icon} {option} {self.cursor_icon}"
                color = NEON_CYAN
            else:
                pygame.draw.rect(self.screen, (20, 15, 40, 120),
                                 (bg_x, bg_y, menu_w, menu_h), border_radius=5)
                pygame.draw.rect(self.screen, NEON_CYAN_DIM, (bg_x, bg_y, menu_w, menu_h),
                                 1, border_radius=5)
                text = option
                color = DIM_WHITE

            opt_surf = self.font_menu.render(text, True, color)
            self.screen.blit(opt_surf, ((self.w - opt_surf.get_width()) // 2, opt_y))

        # ── Placeholder message ──
        if self._placeholder_text:
            msg_surf = self.font_small.render(self._placeholder_text, True, GOLD)
            self.screen.blit(msg_surf,
                             ((self.w - msg_surf.get_width()) // 2,
                              menu_start_y + len(self.menu_options) * spacing + 15))

        # ── Hint ──
        hint = self.font_hint.render("[W/S or UP/DOWN] Navigate   [ENTER or SPACE] Select", True, (90, 90, 115))
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, self.h - 30))

        # ── Fade overlay ──
        if self.fade_alpha > 1:
            fade = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fade.fill((0, 0, 0, min(255, int(self.fade_alpha))))
            self.screen.blit(fade, (0, 0))

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                  #
    # ------------------------------------------------------------------ #

    def _start_fade(self, target: float, duration_sec: float):
        self._fade_target = target
        if duration_sec > 0:
            self._fade_speed = 255.0 / (duration_sec * 1000.0)
        else:
            self.fade_alpha = target

    def _show_placeholder(self, text: str):
        self._placeholder_text = text
        self._placeholder_timer = 1500
