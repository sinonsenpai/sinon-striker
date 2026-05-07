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
        # Dark gradient background
        self.screen.fill(BG_COLOR)
        for i in range(self.h):
            alpha = int(12 + 8 * math.sin(i * 0.005))
            pygame.draw.line(self.screen, (30 + alpha, 20 + alpha // 2, 55 + alpha),
                             (0, i), (self.w, i))

        # Center panel (tight fit for content only, footer goes below)
        panel_w = 460
        pad = 25
        # Calculate height: pad + title(36) + gap(8) + sep(1) + gap(30) + slider(18) + gap(24) +
        #                   slider(18) + gap(24) + toggle(28) + gap(26) + div(1) + gap(16) + back(36) + pad
        panel_h = pad + 36 + 8 + 1 + 30 + 18 + 24 + 18 + 24 + 28 + 26 + 1 + 16 + 36 + pad
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h),
                         width=2, border_radius=8)

        # Title
        title = self.font_title.render("OPTIONS", True, NEON_CYAN)
        title_y = py + pad
        self.screen.blit(title, ((self.w - title.get_width()) // 2, title_y))

        # Separator under title
        sep_y = title_y + title.get_height() + 8
        pygame.draw.line(self.screen, NEON_CYAN_DIM,
                         (px + pad, sep_y), (px + panel_w - pad, sep_y), 1)

        # Layout positions (relative to panel top-left)
        inner_left = px + pad
        inner_right = px + panel_w - pad
        slider_w = 170
        slider_h = 18
        pct_w = 40  # reserved width for percentage text
        slider_x = inner_right - slider_w - pct_w - 10
        pct_x = inner_right - pct_w

        # --- SFX Volume ---
        sfx_y = sep_y + 30
        selected = self.selected_index == 0
        self._draw_slider_row("SFX Volume", self.sfx_volume, sfx_y, inner_left, slider_x, slider_w, slider_h, pct_x, selected)

        # --- Music Volume ---
        music_y = sfx_y + 24
        selected = self.selected_index == 1
        self._draw_slider_row("Music Volume", self.music_volume, music_y, inner_left, slider_x, slider_w, slider_h, pct_x, selected)

        # --- Mute toggle ---
        mute_y = music_y + 24
        selected = self.selected_index == 2
        self._draw_toggle_row("Mute", self.muted, mute_y, inner_left, slider_x, 100, 28, selected)

        # --- Divider between settings and Back ---
        divider_y = mute_y + 26
        pygame.draw.line(self.screen, NEON_CYAN_DIM,
                         (px + pad + 20, divider_y), (px + panel_w - pad - 20, divider_y), 1)

        # --- Back button ---
        back_y = divider_y + 16
        self._draw_back_button(back_y, px, panel_w, pad)

        # Footer text below the panel, not inside it
        footer_y = py + panel_h + 20
        footer = self.font_hud.render(
            "[W/S or UP/DOWN] Navigate   [LEFT/RIGHT] Adjust   [ENTER/ESC] Back",
            True, DIM_WHITE)
        self.screen.blit(footer, ((self.w - footer.get_width()) // 2, footer_y))

    # ------------------------------------------------------------------ #
    #  Drawing helpers                                                   #
    # ------------------------------------------------------------------ #

    def _draw_slider_row(self, label, val, y, label_x, slider_x, slider_w, slider_h, pct_x, selected):
        # Label
        label_color = NEON_CYAN if selected else DIM_WHITE
        label_surf = self.font_medium.render(label, True, label_color)
        self.screen.blit(label_surf, (label_x, y + (slider_h - label_surf.get_height()) // 2))

        fill_w = int(slider_w * val)
        sy = y + (slider_h - slider_h) // 2  # vertically centered on row

        # Background
        slider_bg = pygame.Surface((slider_w, slider_h), pygame.SRCALPHA)
        bg_color = (40, 40, 55, 200) if selected else (30, 30, 40, 200)
        slider_bg.fill(bg_color)
        self.screen.blit(slider_bg, (slider_x, sy))

        # Fill (always bright cyan, consistent across both sliders)
        if fill_w > 0:
            pygame.draw.rect(self.screen, NEON_CYAN,
                             (slider_x, sy, fill_w, slider_h), border_radius=3)

        # Border
        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.006)
            border_alpha = int(150 + 80 * pulse)
            pygame.draw.rect(self.screen, (*NEON_CYAN, border_alpha),
                             (slider_x, sy, slider_w, slider_h), width=2, border_radius=3)
        else:
            pygame.draw.rect(self.screen, (60, 60, 75),
                             (slider_x, sy, slider_w, slider_h), width=1, border_radius=3)

        # Handle
        handle_x = slider_x + fill_w
        handle_y = sy + slider_h // 2
        pygame.draw.circle(self.screen, WHITE, (handle_x, handle_y), 4)

        # Percentage (right-aligned at same x)
        pct = int(val * 100)
        pct_surf = self.font_small.render(f"{pct}%", True, WHITE)
        self.screen.blit(pct_surf, (pct_x + (40 - pct_surf.get_width()),
                                      sy + (slider_h - pct_surf.get_height()) // 2))

    def _draw_back_button(self, y, px, panel_w, pad):
        selected = self.selected_index == 3
        btn_w, btn_h = 120, 36
        btn_x = px + (panel_w - btn_w) // 2

        # Button background
        btn_bg = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
        btn_bg.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 180))
        self.screen.blit(btn_bg, (btn_x, y))

        if selected:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.006)
            border_alpha = int(180 + 60 * pulse)
            pygame.draw.rect(self.screen, (*NEON_CYAN, border_alpha),
                             (btn_x, y, btn_w, btn_h), width=2, border_radius=6)
            text = ">  Back  <"
            color = NEON_CYAN
        else:
            pygame.draw.rect(self.screen, (60, 60, 75),
                             (btn_x, y, btn_w, btn_h), width=1, border_radius=6)
            text = "Back"
            color = DIM_WHITE

        surf = self.font_medium.render(text, True, color)
        self.screen.blit(surf, (btn_x + (btn_w - surf.get_width()) // 2,
                                 y + (btn_h - surf.get_height()) // 2))


    def _draw_toggle_row(self, label, enabled, y, label_x, toggle_x, toggle_w, toggle_h, selected):
        label_color = NEON_CYAN if selected else DIM_WHITE
        label_surf = self.font_medium.render(label, True, label_color)
        self.screen.blit(label_surf, (label_x, y + (toggle_h - label_surf.get_height()) // 2))

        bg_color = (0, 120, 110) if enabled else (55, 35, 45)
        border_color = NEON_CYAN if selected else (80, 80, 100)
        pygame.draw.rect(self.screen, bg_color, (toggle_x, y, toggle_w, toggle_h), border_radius=14)
        pygame.draw.rect(self.screen, border_color, (toggle_x, y, toggle_w, toggle_h), width=2, border_radius=14)

        knob_r = 10
        knob_x = toggle_x + (toggle_w - knob_r - 4 if enabled else knob_r + 4)
        knob_y = y + toggle_h // 2
        pygame.draw.circle(self.screen, WHITE, (knob_x, knob_y), knob_r)

        state_surf = self.font_small.render("ON" if enabled else "OFF", True, WHITE)
        self.screen.blit(state_surf, (toggle_x + toggle_w + 10, y + (toggle_h - state_surf.get_height()) // 2))

    def _save_settings(self):
        """Write current volumes to a JSON file."""
        try:
            with open("settings.json", "w") as f:
                json.dump({"sfx_volume": self.sfx_volume, "music_volume": self.music_volume, "muted": self.muted}, f)
        except Exception:
            pass
