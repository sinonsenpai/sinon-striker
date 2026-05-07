"""
Options Screen — volume sliders and settings panel.
"""

import math
import json
import pygame


BG_COLOR = (18, 14, 30)
WHITE = (230, 230, 245)
DIM_WHITE = (160, 160, 180)
NEON_CYAN = (0, 240, 255)
NEON_CYAN_DIM = (0, 100, 120)
PANEL_BG = (20, 15, 40)
PANEL_BORDER = (0, 240, 255)


class OptionsScreen:
    """Settings panel with volume sliders."""

    def __init__(self, screen: pygame.Surface, sound_manager):
        self.screen = screen
        self.snd = sound_manager
        self.w, self.h = screen.get_size()

        self.font_title = pygame.font.SysFont("arial", 36, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 22, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16, bold=False)
        self.font_hud = pygame.font.SysFont("arial", 14, bold=False)

        self.options = ["SFX Volume", "Music Volume", "Mute", "Back"]
        self.selected_index = 0

        # Sync with sound manager
        self.sfx_volume = self.snd.volume
        self.music_volume = self.snd.get_music_volume()
        self.muted = getattr(self.snd, "muted", False)

        self._elapsed = 0.0

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def move_up(self):
        self.selected_index = (self.selected_index - 1) % len(self.options)

    def move_down(self):
        self.selected_index = (self.selected_index + 1) % len(self.options)

    def adjust_selected(self, delta: float):
        """Adjust the selected slider by delta (clamped to 0..1)."""
        if self.selected_index == 0:
            self.sfx_volume = max(0.0, min(1.0, self.sfx_volume + delta))
            self.snd.volume = self.sfx_volume
            self.snd.adjust_volume(0)  # trigger immediate update
        elif self.selected_index == 1:
            self.music_volume = max(0.0, min(1.0, self.music_volume + delta))
            self.snd.set_music_volume(self.music_volume)
        elif self.selected_index == 2 and delta != 0:
            self.muted = not self.muted
            self.snd.set_muted(self.muted)

    def confirm(self):
        """Return action string or None."""
        if self.selected_index == 2:
            self.muted = not self.muted
            self.snd.set_muted(self.muted)
            return None
        if self.selected_index == 3:
            self._save_settings()
            return "back"
        return None

    def update(self, dt_ms: int):
        self._elapsed += dt_ms

    def draw(self, dt_ms: int):
        self.screen.fill(BG_COLOR)
        self._draw_background()

        # Main panel
        panel_w = 500
        panel_h = 436
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2 - 10
        pad = 24

        self._draw_panel_shadow(px, py, panel_w, panel_h)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((12, 10, 24, 232))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), width=2, border_radius=14)
        pygame.draw.rect(self.screen, (80, 180, 190), (px + 8, py + 8, panel_w - 16, panel_h - 16), width=1, border_radius=12)

        # Header
        title = self.font_title.render("OPTIONS", True, NEON_CYAN)
        subtitle = self.font_small.render("Audio and accessibility controls", True, DIM_WHITE)
        title_y = py + 22
        self.screen.blit(title, ((self.w - title.get_width()) // 2, title_y))
        self.screen.blit(subtitle, ((self.w - subtitle.get_width()) // 2, title_y + title.get_height() + 4))

        header_line_y = title_y + title.get_height() + subtitle.get_height() + 16
        pygame.draw.line(self.screen, NEON_CYAN_DIM, (px + pad, header_line_y), (px + panel_w - pad, header_line_y), 1)

        # Content cards
        card_x = px + pad
        card_w = panel_w - pad * 2
        row_h = 72
        gap = 9
        first_row_y = header_line_y + 16

        self._draw_slider_card(
            "SFX Volume",
            self.sfx_volume,
            first_row_y,
            card_x,
            card_w,
            row_h,
            selected=self.selected_index == 0,
        )
        self._draw_slider_card(
            "Music Volume",
            self.music_volume,
            first_row_y + row_h + gap,
            card_x,
            card_w,
            row_h,
            selected=self.selected_index == 1,
        )
        self._draw_toggle_card(
            "Mute",
            self.muted,
            first_row_y + (row_h + gap) * 2,
            card_x,
            card_w,
            row_h,
            selected=self.selected_index == 2,
        )

        # Back button
        back_y = py + panel_h - 58
        self._draw_back_button(back_y, px, panel_w, pad)

        footer = self.font_hud.render(
            "[W/S or UP/DOWN] Navigate   [LEFT/RIGHT] Adjust   [ENTER/ESC] Back",
            True,
            DIM_WHITE,
        )
        self.screen.blit(footer, ((self.w - footer.get_width()) // 2, py + panel_h + 18))

    # ------------------------------------------------------------------ #
    #  Drawing helpers                                                   #
    # ------------------------------------------------------------------ #

    def _draw_slider_card(self, label, val, y, x, w, h, selected):
        self._draw_card_base(x, y, w, h, selected)
        label_color = NEON_CYAN if selected else DIM_WHITE
        label_surf = self.font_medium.render(label, True, label_color)
        self.screen.blit(label_surf, (x + 16, y + 11))

        pct = int(val * 100)
        pct_surf = self.font_small.render(f"{pct}%", True, WHITE if selected else DIM_WHITE)
        pct_x = x + w - pct_surf.get_width() - 18
        pct_y = y + 14
        self.screen.blit(pct_surf, (pct_x, pct_y))

        track_x = x + 16
        track_y = y + 40
        track_w = w - 32
        track_h = 16
        fill_w = max(8, int(track_w * val))

        track = pygame.Surface((track_w, track_h), pygame.SRCALPHA)
        track.fill((28, 25, 42, 230))
        self.screen.blit(track, (track_x, track_y))
        pygame.draw.rect(self.screen, (64, 64, 84), (track_x, track_y, track_w, track_h), width=1, border_radius=8)

        if fill_w > 0:
            fill = pygame.Surface((fill_w, track_h), pygame.SRCALPHA)
            fill.fill((0, 240, 255, 220))
            self.screen.blit(fill, (track_x, track_y))

        thumb_x = track_x + fill_w
        thumb_y = track_y + track_h // 2
        pygame.draw.circle(self.screen, (245, 245, 255), (thumb_x, thumb_y), 8)
        pygame.draw.circle(self.screen, NEON_CYAN if selected else (170, 170, 190), (thumb_x, thumb_y), 8, 2)

    def _draw_toggle_card(self, label, enabled, y, x, w, h, selected):
        self._draw_card_base(x, y, w, h, selected)
        label_color = NEON_CYAN if selected else DIM_WHITE
        label_surf = self.font_medium.render(label, True, label_color)
        self.screen.blit(label_surf, (x + 16, y + 22))

        switch_w, switch_h = 100, 34
        switch_x = x + w - switch_w - 16
        switch_y = y + (h - switch_h) // 2
        bg_color = (44, 110, 100) if enabled else (56, 38, 48)
        border_color = NEON_CYAN if selected else (82, 82, 102)
        pygame.draw.rect(self.screen, bg_color, (switch_x, switch_y, switch_w, switch_h), border_radius=17)
        pygame.draw.rect(self.screen, border_color, (switch_x, switch_y, switch_w, switch_h), width=2, border_radius=17)

        knob_r = 12
        knob_x = switch_x + (switch_w - knob_r - 8 if enabled else knob_r + 8)
        knob_y = switch_y + switch_h // 2
        pygame.draw.circle(self.screen, WHITE, (knob_x, knob_y), knob_r)
        pygame.draw.circle(self.screen, (180, 180, 200), (knob_x, knob_y), knob_r, 2)

        state_text = "ON" if enabled else "OFF"
        state_color = WHITE if enabled else (190, 190, 210)
        state_surf = self.font_small.render(state_text, True, state_color)
        state_x = max(x + 16, switch_x - state_surf.get_width() - 14)
        self.screen.blit(state_surf, (state_x, switch_y + 7))

    def _draw_back_button(self, y, px, panel_w, pad):
        selected = self.selected_index == 3
        btn_w, btn_h = 148, 40
        btn_x = px + (panel_w - btn_w) // 2

        btn_bg = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        btn_bg.fill((18, 16, 30, 230))
        self.screen.blit(btn_bg, (btn_x, y))

        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.006)
            border_alpha = int(180 + 60 * pulse)
            pygame.draw.rect(self.screen, (*NEON_CYAN, border_alpha),
                             (btn_x, y, btn_w, btn_h), width=2, border_radius=20)
            text = "Back"
            color = NEON_CYAN
        else:
            pygame.draw.rect(self.screen, (60, 60, 75),
                             (btn_x, y, btn_w, btn_h), width=1, border_radius=20)
            text = "Back"
            color = DIM_WHITE

        surf = self.font_medium.render(text, True, color)
        self.screen.blit(surf, (btn_x + (btn_w - surf.get_width()) // 2,
                                 y + (btn_h - surf.get_height()) // 2))

    def _draw_card_base(self, x, y, w, h, selected):
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        card.fill((22, 18, 36, 210))
        self.screen.blit(card, (x, y))

        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.006)
            glow = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
            glow.fill((0, 240, 255, int(12 + 20 * pulse)))
            self.screen.blit(glow, (x - 6, y - 6))

            sheen = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(sheen, (255, 255, 255, int(12 + 10 * pulse)), (8, 8, w - 16, 14), border_radius=7)
            pygame.draw.line(sheen, (255, 255, 255, int(18 + 8 * pulse)), (16, 14), (w - 16, 14), 1)
            self.screen.blit(sheen, (x, y))

            pygame.draw.rect(self.screen, NEON_CYAN, (x, y, w, h), width=2, border_radius=12)
            pygame.draw.rect(self.screen, (160, 250, 255), (x + 2, y + 2, w - 4, h - 4), width=1, border_radius=10)
        else:
            pygame.draw.rect(self.screen, (60, 60, 82), (x, y, w, h), width=1, border_radius=12)

        accent_h = 26
        accent_color = NEON_CYAN if selected else NEON_CYAN_DIM
        pygame.draw.rect(self.screen, accent_color, (x + 8, y + 14, 4, accent_h), border_radius=2)

        if selected:
            # Add a faint diagonal highlight so the active row feels "lit" instead of only outlined.
            stripe = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.polygon(
                stripe,
                (0, 240, 255, 18),
                [(w * 0.18, 0), (w * 0.38, 0), (w * 0.56, h), (w * 0.36, h)],
            )
            self.screen.blit(stripe, (x, y))

    def _draw_background(self):
        for i in range(self.h):
            t = i / max(1, self.h - 1)
            r = int(14 + 18 * t)
            g = int(12 + 10 * t)
            b = int(26 + 22 * t)
            pygame.draw.line(self.screen, (r, g, b), (0, i), (self.w, i))

        pulses = [
            (self.w * 0.18, self.h * 0.2, 130, (0, 240, 255)),
            (self.w * 0.82, self.h * 0.74, 170, (255, 215, 0)),
            (self.w * 0.5, self.h * 0.48, 220, (120, 80, 255)),
        ]
        for cx, cy, radius, color in pulses:
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 28), (radius, radius), radius)
            pygame.draw.circle(glow, (*color, 14), (radius, radius), int(radius * 0.72))
            self.screen.blit(glow, (int(cx - radius), int(cy - radius)))

    def _draw_panel_shadow(self, px, py, w, h):
        shadow = pygame.Surface((w + 28, h + 28), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120), (14, 14, w, h), border_radius=18)
        self.screen.blit(shadow, (px - 14, py - 14))

    def _save_settings(self):
        """Write current volumes to a JSON file."""
        try:
            with open("settings.json", "w") as f:
                json.dump({"sfx_volume": self.sfx_volume, "music_volume": self.music_volume, "muted": self.muted}, f)
        except Exception:
            pass
