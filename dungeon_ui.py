"""
Dungeon UI — floor select, room display, room cleared overlay, and shop.
"""

import math
import pygame
import random
from dungeon import RoomType, ROOM_ICONS, ROOM_COLORS, ROOM_LABELS, ENEMY_POOL, FLAVOR


BG_COLOR = (10, 10, 16)
NEON_CYAN = (90, 220, 220)
NEON_CYAN_DIM = (38, 92, 102)
GOLD = (224, 186, 96)
GOLD_DIM = (112, 92, 42)
WHITE = (236, 236, 244)
DIM_WHITE = (156, 156, 176)
RED = (212, 68, 78)
GREEN = (72, 192, 112)
PANEL_BG = (18, 16, 28)

ROUTE_BG = BG_COLOR
ROUTE_FOG = (24, 18, 42)
ROUTE_PANEL_FILL = (20, 15, 40, 232)
ROUTE_PANEL_BORDER = (0, 240, 255)
ROUTE_PANEL_INNER = (255, 255, 255, 14)
ROUTE_TAB_FILL = (18, 16, 30, 236)
ROUTE_TAB_BORDER = (0, 240, 255)
ROUTE_TAB_INNER = (255, 255, 255, 16)
ROUTE_TEXT = WHITE
ROUTE_MUTED = DIM_WHITE
ROUTE_LOCKED = (78, 78, 96)
ROUTE_ACCENT = GOLD
ROUTE_CURRENT = GOLD
ROUTE_AVAILABLE = GREEN
ROUTE_SELECTED = NEON_CYAN
ROUTE_BOSS = RED

ROUTE_LABELS = {
    RoomType.COMBAT: "Combat",
    RoomType.ELITE: "Elite",
    RoomType.LOOT: "Treasure",
    RoomType.REST: "Rest",
    RoomType.SHOP: "Shop",
    RoomType.EXIT: "Exit",
    RoomType.BOSS: "Boss",
    RoomType.SHRINE: "Event",
    RoomType.TRAP: "Hazard",
}


class DungeonUI:
    """Renders the dungeon floor select, room overview, and transitions."""

    def __init__(self, screen: pygame.Surface, dungeon_run=None):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.run = dungeon_run
        self.floor_display = 1
        self.font_title = pygame.font.SysFont("arial", 36, bold=True)
        self.font_large = pygame.font.SysFont("arial", 28, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 22, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16, bold=False)
        self.font_hud = pygame.font.SysFont("arial", 14, bold=False)
        self.font_icon = pygame.font.SysFont("arial", 40, bold=True)
        self.font_map_title = pygame.font.SysFont("arial", 40, bold=True)
        self.font_map_subtitle = pygame.font.SysFont("arial", 20, bold=True)
        self.font_map_meta = pygame.font.SysFont("arial", 15, bold=False)
        self._elapsed = 0.0
        self.route_focus_layer = 0
        self.route_selection_index = 0

        # Chest / loot state
        self.chest_opened = False
        self.chest_anim_timer = 0.0
        self.chest_sparks = []

    def reset_chest(self):
        self.chest_opened = False
        self.chest_anim_timer = 0.0
        self.chest_sparks = []

    def update(self, dt_ms: int):
        self._elapsed += dt_ms

        # Chest spark animation
        if self.chest_opened and self.chest_anim_timer > 0:
            self.chest_anim_timer -= dt_ms
            if self.chest_anim_timer < 0:
                self.chest_anim_timer = 0
        for sp in self.chest_sparks[:]:
            sp["timer"] += dt_ms
            sp["x"] += sp["vx"] * dt_ms / 16
            sp["y"] += sp["vy"] * dt_ms / 16
            if sp["timer"] > sp["lifetime"]:
                self.chest_sparks.remove(sp)

    def set_run(self, run):
        self.run = run

    def reset_route_selection(self):
        if not self.run or not getattr(self.run, "map", None):
            self.route_focus_layer = 0
            self.route_selection_index = 0
            return
        current = self.run.current
        if current and current.cleared and not self.run.done:
            options = self.run.available_nodes
            self.route_focus_layer = options[0].layer if options else current.layer + 1
        else:
            self.route_focus_layer = current.layer if current else 0
        self.route_selection_index = 0

    def _route_layers(self):
        if not self.run or not getattr(self.run, "map", None):
            return []
        layers = {}
        for node in self.run.map.nodes:
            layers.setdefault(node.layer, []).append(node)
        return [layers[idx] for idx in sorted(layers.keys())]

    def _route_map_label(self, node):
        return ROUTE_LABELS.get(node.node_type, ROOM_LABELS.get(node.node_type, "?"))

    def _text_contrast_color(self, bg_color):
        r, g, b = bg_color[:3]
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return (18, 18, 24) if luminance > 160 else (245, 245, 250)

    def _render_text_with_outline(self, text, font, fill, outline=(0, 0, 0), outline_px=2):
        base = font.render(text, True, fill)
        if outline_px <= 0:
            return base
        surf = pygame.Surface((base.get_width() + outline_px * 2, base.get_height() + outline_px * 2), pygame.SRCALPHA)
        for ox, oy in ((-outline_px, 0), (outline_px, 0), (0, -outline_px), (0, outline_px), (-outline_px, -outline_px), (-outline_px, outline_px), (outline_px, -outline_px), (outline_px, outline_px)):
            shadow = font.render(text, True, outline)
            surf.blit(shadow, (outline_px + ox, outline_px + oy))
        surf.blit(base, (outline_px, outline_px))
        return surf

    def _route_curve_points(self, start, end, bend=0.18, segments=20):
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        c1 = (x1 + dx * 0.34, y1 + dy * bend)
        c2 = (x1 + dx * 0.66, y2 - dy * bend)
        points = []
        for i in range(segments + 1):
            t = i / segments
            u = 1.0 - t
            x = (
                (u ** 3) * x1
                + 3 * (u ** 2) * t * c1[0]
                + 3 * u * (t ** 2) * c2[0]
                + (t ** 3) * x2
            )
            y = (
                (u ** 3) * y1
                + 3 * (u ** 2) * t * c1[1]
                + 3 * u * (t ** 2) * c2[1]
                + (t ** 3) * y2
            )
            points.append((int(x), int(y)))
        return points

    def _draw_route_connection(self, surf, start, end, color, alpha=120, active=False, completed=False):
        shadow_alpha = 42 if not completed else 20
        if active:
            alpha = min(255, alpha + 90)
            shadow_alpha = 58
        line_color = (*color, alpha)
        points = self._route_curve_points(start, end, bend=0.10 if active else 0.16, segments=26)
        if len(points) >= 2:
            pygame.draw.lines(surf, (0, 0, 0, shadow_alpha), False, points, 8 if active else 5)
            pygame.draw.lines(surf, line_color, False, points, 4 if active else 2)
            if completed:
                pygame.draw.lines(surf, (*color, 42), False, points, 1)
            if active:
                pulse = 0.55 + 0.45 * math.sin(self._elapsed * 0.009)
                glow = (*color, int(170 * pulse))
                pygame.draw.lines(surf, glow, False, points, 6)
                if points:
                    pygame.draw.circle(surf, glow, points[-1], 5)

    def _draw_route_background(self, biome_tint):
        self.screen.fill(ROUTE_BG)

        base = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        base.fill((7, 6, 10, 255))
        self.screen.blit(base, (0, 0))

        # Soft layered glow, kept deliberately restrained for readability.
        glows = [
            (int(self.w * 0.16), int(self.h * 0.22), (*biome_tint[:3], 18), 180),
            (int(self.w * 0.80), int(self.h * 0.18), (*NEON_CYAN, 12), 220),
            (int(self.w * 0.52), int(self.h * 0.82), (*ROUTE_FOG, 10), 240),
        ]
        for gx, gy, color, radius in glows:
            for step in range(5):
                r = radius + step * 28
                alpha = max(0, color[3] - step * 3)
                glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*color[:3], alpha), (r, r), r)
                self.screen.blit(glow, (gx - r, gy - r))

        # Sparse dust and a couple of wide translucent bands to avoid a flat backdrop.
        particle_count = 22 + self.run.floor * 2
        for i in range(particle_count):
            px = int((self._elapsed * 0.012 + i * 83) % (self.w + 120)) - 60
            py = int((i * 59 + self._elapsed * 0.0065) % (self.h - 40)) + 20
            alpha = 12 + (i % 4) * 4
            size = 1 + (i % 3)
            pygame.draw.circle(self.screen, (210, 220, 245, alpha), (px, py), size)

        band = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for idx in range(4):
            band.fill((0, 0, 0, 0))
            band_alpha = 8 if idx % 2 == 0 else 4
            y = int(self.h * (0.18 + idx * 0.20))
            pygame.draw.rect(band, (255, 255, 255, band_alpha), (0, y, self.w, 34))
            self.screen.blit(band, (0, 0))

        vignette = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for i in range(10):
            alpha = 20 + i * 10
            margin = i * 18
            pygame.draw.rect(
                vignette,
                (0, 0, 0, alpha),
                (margin, margin, self.w - margin * 2, self.h - margin * 2),
                2,
                border_radius=14,
            )
        self.screen.blit(vignette, (0, 0))

    def _draw_route_panel(self, rect):
        shadow = pygame.Surface((rect.w + 18, rect.h + 18), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 110))
        self.screen.blit(shadow, (rect.x - 9, rect.y + 9))

        frame = pygame.Surface(rect.size, pygame.SRCALPHA)
        frame.fill(ROUTE_PANEL_FILL)
        self.screen.blit(frame, rect.topleft)
        pygame.draw.rect(self.screen, ROUTE_PANEL_BORDER, rect, 2, border_radius=18)

        inner = rect.inflate(-14, -14)
        pygame.draw.rect(self.screen, ROUTE_PANEL_INNER, inner, 1, border_radius=14)

    def _draw_route_tab(self, center_x, y, text, accent, is_boss=False):
        chip = self.font_hud.render(text, True, ROUTE_TEXT)
        chip_w = chip.get_width() + 22
        chip_h = chip.get_height() + 12
        chip_x = int(center_x - chip_w // 2)
        chip_surf = pygame.Surface((chip_w, chip_h), pygame.SRCALPHA)
        fill = ROUTE_TAB_FILL if not is_boss else (34, 20, 22, 240)
        chip_surf.fill(fill)
        pygame.draw.rect(chip_surf, accent, (0, 0, chip_w, chip_h), 1, border_radius=9)
        pygame.draw.rect(chip_surf, ROUTE_TAB_INNER, (3, 3, chip_w - 6, chip_h - 6), 1, border_radius=7)
        chip_surf.blit(chip, (11, 6))
        self.screen.blit(chip_surf, (chip_x, y))

    def _draw_route_legend(self, x, y):
        # Kept for future expansion, but the current map layout no longer draws this
        # inline because it was competing with the route space on smaller windows.
        items = [
            ("Current", ROUTE_CURRENT),
            ("Available", ROUTE_AVAILABLE),
            ("Cleared", ROUTE_ACCENT),
            ("Locked", ROUTE_LOCKED),
            ("Boss", ROUTE_BOSS),
        ]
        cursor_x = x
        for label, color in items:
            text = self.font_hud.render(label, True, ROUTE_TEXT)
            box_w = text.get_width() + 18
            box_h = text.get_height() + 8
            box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            box.fill((20, 15, 40, 220))
            pygame.draw.rect(box, color, (0, 0, box_w, box_h), 1, border_radius=8)
            pygame.draw.rect(box, (255, 255, 255, 12), (3, 3, box_w - 6, box_h - 6), 1, border_radius=6)
            box.blit(text, (9, 4))
            self.screen.blit(box, (cursor_x, y))
            cursor_x += box_w + 10

    def _draw_route_node_card(self, node, rect, current_id, selected_id, available_ids):
        x, y, w, h = rect
        is_current = node.id == current_id
        is_completed = node.id in self.run.map.completed_ids
        is_available = node.id in available_ids
        is_selected = node.id == selected_id
        color = ROOM_COLORS.get(node.node_type, ROUTE_TEXT)

        bg_color = (28, 26, 34)
        if is_completed:
            bg_color = tuple(max(24, int(c * 0.22) + 16) for c in color)
        elif is_available or is_current:
            bg_color = tuple(min(255, int(c * 0.84) + 30) for c in color)

        bg_alpha = 238 if (is_available or is_current or is_completed) else 176
        accent = color if (is_available or is_current or is_completed) else ROUTE_LOCKED
        label_color = self._text_contrast_color(bg_color)
        if not (is_available or is_current or is_completed):
            label_color = ROUTE_MUTED

        if is_current:
            pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.006)
            glow = pygame.Surface((w + 44, h + 44), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*ROUTE_CURRENT, int(42 * pulse)), (8, 8, w + 28, h + 28))
            pygame.draw.ellipse(glow, (*color, int(24 * pulse)), (18, 18, w + 8, h + 8))
            self.screen.blit(glow, (x - 22, y - 22))

        if is_selected:
            pulse = 0.55 + 0.45 * math.sin(self._elapsed * 0.008)
            glow = pygame.Surface((w + 34, h + 34), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*ROUTE_SELECTED, int(28 * pulse)), (5, 5, w + 24, h + 24))
            self.screen.blit(glow, (x - 17, y - 17))

        node_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        node_surf.fill((*bg_color, bg_alpha))
        pygame.draw.rect(node_surf, (255, 255, 255, 24), (5, 5, w - 10, h // 2), border_radius=12)
        pygame.draw.rect(node_surf, (255, 255, 255, 10), (8, 9, w - 16, 6), border_radius=4)
        self.screen.blit(node_surf, (x, y))

        border_color = accent
        border_alpha = 255 if is_selected else (235 if is_current else (220 if is_available or is_completed else 112))
        border_w = 4 if is_selected else (3 if is_current else 2)
        pygame.draw.rect(self.screen, (0, 0, 0, 125), (x + 2, y + 4, w, h), border_w + 2, border_radius=18)
        pygame.draw.rect(self.screen, (*border_color, border_alpha), (x, y, w, h), border_w, border_radius=18)

        # Inner emblem that gives the nodes a readable focal point without clutter.
        emblem_r = max(10, min(w, h) // 4)
        emblem_center = (x + w // 2, y + h // 2 - 8)
        emblem = pygame.Surface((emblem_r * 2 + 10, emblem_r * 2 + 10), pygame.SRCALPHA)
        emblem_color = color if (is_available or is_current or is_completed) else ROUTE_MUTED
        if is_completed:
            emblem_color = tuple(max(80, int(c * 0.72)) for c in color)
        pygame.draw.circle(emblem, (*emblem_color, 54 if (is_available or is_current) else 38), (emblem_r + 5, emblem_r + 5), emblem_r + 2)
        pygame.draw.circle(emblem, (*emblem_color, 165 if (is_available or is_current or is_completed) else 96), (emblem_r + 5, emblem_r + 5), emblem_r, 2)
        self.screen.blit(emblem, (emblem_center[0] - emblem.get_width() // 2, emblem_center[1] - emblem.get_height() // 2))

        icon = self.font_icon.render(node.icon_letter, True, emblem_color)
        self.screen.blit(icon, (x + (w - icon.get_width()) // 2, y + 5))

        label = self._route_map_label(node)
        outline = (255, 255, 255) if label_color[0] < 90 else (0, 0, 0)
        label_surf = self._render_text_with_outline(label, self.font_hud, label_color, outline=outline, outline_px=1)
        label_bg = pygame.Surface((label_surf.get_width() + 12, label_surf.get_height() + 8), pygame.SRCALPHA)
        label_bg.fill((18, 16, 30, 186))
        pygame.draw.rect(label_bg, (*border_color, 180 if (is_available or is_current or is_completed) else 120), (0, 0, label_bg.get_width(), label_bg.get_height()), 1, border_radius=9)
        label_bg.blit(label_surf, (6, 4))
        self.screen.blit(label_bg, (x + (w - label_bg.get_width()) // 2, y + h - label_bg.get_height() - 6))

        if is_completed:
            check = self.font_hud.render("✓", True, GOLD)
            self.screen.blit(check, (x + w - check.get_width() - 6, y + 4))

    def _selectable_nodes_for_layer(self, layer: int):
        if not self.run or not getattr(self.run, "map", None):
            return []
        current = self.run.current
        if current is None:
            return []
        if not current.cleared:
            return [current] if layer == current.layer else []
        if layer != current.layer + 1:
            return []
        return [node for node in self.run.available_nodes if node.layer == layer]

    def route_move_left(self):
        if not self.run:
            return
        self.route_focus_layer = max(0, self.route_focus_layer - 1)
        self.route_selection_index = 0

    def route_move_right(self):
        if not self.run or not getattr(self.run, "map", None):
            return
        max_layer = max(node.layer for node in self.run.map.nodes) if self.run.map.nodes else 0
        self.route_focus_layer = min(max_layer, self.route_focus_layer + 1)
        self.route_selection_index = 0

    def route_move_up(self):
        options = self._selectable_nodes_for_layer(self.route_focus_layer)
        if options:
            self.route_selection_index = (self.route_selection_index - 1) % len(options)

    def route_move_down(self):
        options = self._selectable_nodes_for_layer(self.route_focus_layer)
        if options:
            self.route_selection_index = (self.route_selection_index + 1) % len(options)

    def route_selected_node(self):
        options = self._selectable_nodes_for_layer(self.route_focus_layer)
        if not options:
            return None
        return options[self.route_selection_index % len(options)]

    # ── Floor select ──────────────────────────────────────────────

    def draw_floor_select(self):
        self.screen.fill(BG_COLOR)
        px = (self.w - 440) // 2
        py = (self.h - 320) // 2  # Was 280 — more space
        m = 20

        panel = pygame.Surface((440, 320), pygame.SRCALPHA)  # Was 280 — taller
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 225))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, 440, 320), 2, border_radius=8)

        title = self.font_title.render("DUNGEON", True, NEON_CYAN)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, py + 20))

        floor_num = self.floor_display
        is_boss_floor = floor_num % 5 == 0
        floor_text = f"Floor {floor_num}"
        if is_boss_floor:
            floor_text += " - Boss Floor!"
        floor_color = RED if is_boss_floor else GOLD
        floor = self.font_large.render(floor_text, True, floor_color)
        self.screen.blit(floor, ((self.w - floor.get_width()) // 2, py + 70))

        info_lines = ["~5 rooms", "Recommended Gear: Any", "No HP/SP restore between rooms"]
        cy = py + 110
        for line in info_lines:
            s = self.font_small.render(line, True, DIM_WHITE)
            self.screen.blit(s, ((self.w - s.get_width()) // 2, cy))
            cy += 22

        cta_surf = self.font_medium.render("Press ENTER to descend", True, NEON_CYAN)
        pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.005)
        cta_surf.set_alpha(int(255 * pulse))
        self.screen.blit(cta_surf, ((self.w - cta_surf.get_width()) // 2, py + 210))  # Was 200

        hint = self.font_hud.render("ESC: Back to Hub", True, (120, 120, 140))  # Slightly brighter
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, py + 260))  # Was 252

        debug = self.font_hud.render("F3: Test Loot Room", True, (100, 100, 80))
        self.screen.blit(debug, ((self.w - debug.get_width()) // 2, py + 285))  # Was 270

    def draw_route_map(self):
        if not self.run or not getattr(self.run, "map", None):
            self.screen.fill(BG_COLOR)
            msg = self.font_large.render("No route map available.", True, DIM_WHITE)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2))
            return

        biome_tint = self.run.biome.get("bg_tint", (8, 8, 16))
        self._draw_route_background(biome_tint)

        ordered_layers = self._route_layers()
        layer_count = len(ordered_layers)
        if layer_count == 0:
            return
        for nodes in ordered_layers:
            nodes.sort(key=lambda n: n.position)

        current = self.run.current
        current_id = current.id if current else None
        available_ids = {node.id for node in self.run.available_nodes}
        selected = self.route_selected_node()
        selected_id = selected.id if selected else None

        # Header
        title_text = f"FLOOR {self.run.floor}"
        title_shadow = self.font_map_title.render(title_text, True, (0, 0, 0))
        title = self.font_map_title.render(title_text, True, ROUTE_CURRENT)
        title_box_w = max(260, title.get_width() + 46)
        title_box_h = 54
        title_box_x = (self.w - title_box_w) // 2
        title_box_y = 6
        title_box = pygame.Surface((title_box_w, title_box_h), pygame.SRCALPHA)
        title_box.fill(ROUTE_PANEL_FILL)
        pygame.draw.rect(title_box, ROUTE_PANEL_BORDER, (0, 0, title_box_w, title_box_h), 2, border_radius=16)
        pygame.draw.rect(title_box, ROUTE_PANEL_INNER, (6, 6, title_box_w - 12, title_box_h - 12), 1, border_radius=12)
        title_box.blit(title_shadow, ((title_box_w - title_shadow.get_width()) // 2 + 2, 6))
        title_box.blit(title, ((title_box_w - title.get_width()) // 2, 4))
        self.screen.blit(title_box, (title_box_x, title_box_y))

        cleared = len(self.run.map.completed_ids)
        summary_text = f"Cleared {cleared}/{self.run.total_rooms} · {self.run.remaining_count()} room(s) remaining"
        if self.run.done:
            summary_text += " · Floor cleared"
        route_meta = f"{self.run.biome['name']}  ·  {summary_text}"
        route_meta_surf = self.font_map_meta.render(route_meta, True, ROUTE_MUTED)
        route_meta_w = min(self.w - 80, route_meta_surf.get_width() + 24)
        route_meta_box = pygame.Surface((route_meta_w, 24), pygame.SRCALPHA)
        route_meta_box.fill((20, 15, 40, 210))
        pygame.draw.rect(route_meta_box, ROUTE_TAB_BORDER, (0, 0, route_meta_w, 24), 1, border_radius=10)
        pygame.draw.rect(route_meta_box, (255, 255, 255, 10), (3, 3, route_meta_w - 6, 18), 1, border_radius=8)
        route_meta_box.blit(route_meta_surf, ((route_meta_w - route_meta_surf.get_width()) // 2, 4))
        self.screen.blit(route_meta_box, ((self.w - route_meta_w) // 2, 62))

        # Main route frame
        frame_rect = pygame.Rect(18, 92, self.w - 36, self.h - 178)
        self._draw_route_panel(frame_rect)

        # Layout
        max_layer_nodes = max(len(nodes) for nodes in ordered_layers)
        node_w = 104 if layer_count <= 4 else (96 if layer_count == 5 else 88)
        node_h = 64 if max_layer_nodes <= 2 else (60 if max_layer_nodes == 3 else 56)
        map_left = frame_rect.left + 62
        map_right = frame_rect.right - 62
        map_top = frame_rect.top + 48
        map_bottom = frame_rect.bottom - 82
        map_h = max(1, map_bottom - map_top)
        x_gap = (map_right - map_left) / max(1, layer_count - 1)

        positions: dict[int, tuple[int, int, int, int]] = {}
        for layer_idx, nodes in enumerate(ordered_layers):
            count = len(nodes)
            x_center = int(map_left + layer_idx * x_gap)
            layer_norm = layer_idx / max(1, layer_count - 1)
            layer_wave = int(math.sin(layer_norm * math.pi) * 10)
            layer_shift = int(math.cos(layer_norm * math.pi * 1.4) * 5)
            if count == 1:
                y_positions = [map_top + map_h // 2]
            else:
                # Interior layers get a wider vertical lane so stacked rooms do not feel crowded.
                interior_depth = min(layer_idx, layer_count - 1 - layer_idx)
                span_factor = 0.52 + min(0.18, interior_depth * 0.08) + max(0, count - 2) * 0.04
                span_px = min(map_h - 12, int(map_h * span_factor))
                start_y = map_top + (map_h - span_px) // 2
                step = span_px / max(1, count - 1)
                y_positions = []
                for pos in range(count):
                    y_positions.append(int(start_y + pos * step))
            for pos, node in enumerate(nodes):
                node_bias = pos - (count - 1) / 2.0
                y = y_positions[pos] + layer_wave + int(node_bias * 2)
                x_nudge = 0 if count == 1 else int(node_bias * 9) + layer_shift
                positions[node.id] = (x_center - node_w // 2 + x_nudge, y, node_w, node_h)

        # Layer markers
        for layer_idx, nodes in enumerate(ordered_layers):
            x_center = int(map_left + layer_idx * x_gap)
            if layer_idx == 0:
                label_text = "START"
                accent = ROUTE_AVAILABLE
                is_boss = False
            elif layer_idx == layer_count - 1:
                label_text = "BOSS"
                accent = ROUTE_BOSS
                is_boss = True
            else:
                label_text = f"LAYER {layer_idx}"
                accent = ROUTE_ACCENT
                is_boss = False
            self._draw_route_tab(x_center, frame_rect.top + 8, label_text, accent, is_boss=is_boss)

        # Connections first, nodes on top
        connection_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for node in self.run.map.nodes:
            start_rect = positions.get(node.id)
            if start_rect is None:
                continue
            sx, sy, sw, sh = start_rect
            start = (sx + sw, sy + sh // 2)
            color = ROOM_COLORS.get(node.node_type, DIM_WHITE)
            is_completed = node.id in self.run.map.completed_ids
            for target_id in node.connections:
                target_rect = positions.get(target_id)
                if target_rect is None:
                    continue
                tx, ty, tw, th = target_rect
                end = (tx, ty + th // 2)
                is_live = node.id == current_id and target_id in available_ids
                alpha = 150 if is_live else (62 if is_completed else 100)
                self._draw_route_connection(
                    connection_surf,
                    start,
                    end,
                    color,
                    alpha=alpha,
                    active=is_live,
                    completed=is_completed,
                )
        self.screen.blit(connection_surf, (0, 0))

        # Nodes
        for node in self.run.map.nodes:
            rect = positions.get(node.id)
            if rect is None:
                continue
            self._draw_route_node_card(node, rect, current_id, selected_id, available_ids)

        # Selected node info
        if selected is not None:
            is_ready = selected.id in available_ids or selected.id == current_id
            accent = ROOM_COLORS.get(selected.node_type, NEON_CYAN)
            top_line = self._route_map_label(selected)
            if selected.node_type in (RoomType.COMBAT, RoomType.ELITE, RoomType.BOSS) and selected.enemy:
                enemy_name = ENEMY_POOL.get(selected.enemy, {}).get("name", selected.enemy)
                top_line = f"{top_line} · {enemy_name}"
            elif selected.node_type == RoomType.LOOT:
                top_line = "Treasure cache · Reward room"
            elif selected.node_type == RoomType.REST:
                top_line = "Rest point · Recover HP"
            elif selected.node_type == RoomType.SHOP:
                top_line = "Shop · Buy supplies"
            elif selected.node_type == RoomType.SHRINE:
                top_line = "Event · Choose a blessing"
            elif selected.node_type == RoomType.TRAP:
                top_line = "Hazard · Dangerous route"
            else:
                top_line = f"{self._route_map_label(selected)} · Explore onward"

            top_color = ROUTE_TEXT if is_ready else ROUTE_MUTED
            info_w = min(self.w - 80, max(360, self.font_medium.render(top_line, True, top_color).get_width() + 34))
            info_h = 64
            info_x = (self.w - info_w) // 2
            info_y = self.h - 96
            info_box = pygame.Surface((info_w, info_h), pygame.SRCALPHA)
            info_box.fill(ROUTE_PANEL_FILL)
            pygame.draw.rect(info_box, (*accent, 220), (0, 0, info_w, info_h), 1, border_radius=12)
            pygame.draw.rect(info_box, (255, 255, 255, 12), (4, 4, info_w - 8, info_h - 8), 1, border_radius=10)
            accent_bar = pygame.Rect(10, 10, 6, info_h - 20)
            pygame.draw.rect(info_box, (*accent, 220), accent_bar, border_radius=3)
            info_text = self._render_text_with_outline(top_line, self.font_medium, top_color, outline=(0, 0, 0), outline_px=1)
            info_box.blit(info_text, (22, 8))
            if selected.id == current_id and not selected.cleared:
                sub_line = "Current node · Enter to descend"
            else:
                sub_line = "Enter to select this route"
            sub_color = accent if is_ready else DIM_WHITE
            sub_text = self._render_text_with_outline(sub_line, self.font_hud, sub_color, outline=(0, 0, 0), outline_px=1)
            info_box.blit(sub_text, (22, 34))
            self.screen.blit(info_box, (info_x, info_y))

        layer_note = self._render_text_with_outline(
            "← / → Layer    ↑ / ↓ Node    Enter Select    Esc Retreat",
            self.font_map_meta,
            ROUTE_TEXT,
            outline=(0, 0, 0),
            outline_px=1,
        )
        note_w = layer_note.get_width() + 18
        note_h = layer_note.get_height() + 8
        note_x = (self.w - note_w) // 2
        note_y = self.h - 28
        note_surf = pygame.Surface((note_w, note_h), pygame.SRCALPHA)
        note_surf.fill((20, 15, 40, 235))
        pygame.draw.rect(note_surf, ROUTE_TAB_BORDER, (0, 0, note_w, note_h), 1, border_radius=10)
        pygame.draw.rect(note_surf, (255, 255, 255, 12), (3, 3, note_w - 6, note_h - 6), 1, border_radius=8)
        note_surf.blit(layer_note, (9, 4))
        self.screen.blit(note_surf, (note_x, note_y))

    # ── Room display ──────────────────────────────────────────────

    def draw_room(self):
        """Show current room type with large icon and label."""
        self.screen.fill(BG_COLOR)

        if not self.run or not self.run.current:
            return

        room = self.run.current
        rtype = room["type"]
        icon = ROOM_ICONS.get(rtype, "?")
        color = ROOM_COLORS.get(rtype, WHITE)
        label = ROOM_LABELS.get(rtype, "?")
        total = self.run.total_rooms
        reachable = len(self.run.available_nodes) if hasattr(self.run, "available_nodes") else 0

        # Room counter
        counter = self.font_medium.render(f"Floor {self.run.floor} · Room {self.run.room_index + 1} / {total}", True, DIM_WHITE)
        self.screen.blit(counter, ((self.w - counter.get_width()) // 2, 30))
        bar_w, bar_h = 400, 6
        bx = (self.w - bar_w) // 2
        by = 60
        pygame.draw.rect(self.screen, (30, 30, 50), (bx, by, bar_w, bar_h), border_radius=3)
        prog = min(1.0, self.run.room_index / max(1, total))
        fill_w = int(bar_w * prog)
        if fill_w > 0:
            pygame.draw.rect(self.screen, NEON_CYAN, (bx, by, fill_w, bar_h), border_radius=3)

        # Big icon (procedural)
        self._draw_room_icon(icon, self.w // 2, 120, color, size=48)

        # Room label
        label_surf = self.font_large.render(f"{label} Room", True, color)
        self.screen.blit(label_surf, ((self.w - label_surf.get_width()) // 2, 150))

        sub = self.font_small.render(f"{self.run.biome['name']}  ·  {reachable} reachable paths", True, DIM_WHITE)
        self.screen.blit(sub, ((self.w - sub.get_width()) // 2, 176))

        # Description
        desc = self._room_desc(room)
        desc_surf = self.font_small.render(desc, True, DIM_WHITE)
        self.screen.blit(desc_surf, ((self.w - desc_surf.get_width()) // 2, 208))

        # Action hint
        hint = self._room_hint(room)
        hint_color = GOLD if rtype == RoomType.EXIT else (RED if rtype == RoomType.BOSS else NEON_CYAN)
        hint_surf = self.font_medium.render(hint, True, hint_color)
        self.screen.blit(hint_surf, ((self.w - hint_surf.get_width()) // 2, 250))

        # HP/SP summary
        p = self.run.player
        hp_sp = self.font_small.render(f"HP: {p.current_hp}/{p.max_hp}   SP: {p.sp}/{p.max_sp}", True, WHITE)
        self.screen.blit(hp_sp, ((self.w - hp_sp.get_width()) // 2, 292))

        # Boss room pulsing red border overlay
        if rtype == RoomType.BOSS:
            pulse = 0.6 + 0.4 * math.sin(self._elapsed * 0.006)
            border_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            pygame.draw.rect(border_surf, (255, 60, 60, int(40 * pulse)), (8, 8, self.w - 16, self.h - 16), width=4, border_radius=10)
            self.screen.blit(border_surf, (0, 0))

        if rtype == RoomType.SHOP:
            self._draw_dungeon_shop()

    def _room_desc(self, room):
        if "flavor" in room:
            return room["flavor"]
        rtype = room["type"]
        if rtype == RoomType.COMBAT:
            enemy = ENEMY_POOL.get(room["enemy"], {})
            return f"A {enemy.get('name', 'foe')} blocks your path!"
        elif rtype == RoomType.ELITE:
            enemy = ENEMY_POOL.get(room["enemy"], {})
            return f"A powerful {enemy.get('name', 'foe')} awaits!"
        elif rtype == RoomType.BOSS:
            enemy = ENEMY_POOL.get(room["enemy"], {})
            return f"BOSS: {enemy.get('name', 'foe')} stands before you!"
        elif rtype == RoomType.LOOT:
            return "A treasure chest glimmers in the dark."
        elif rtype == RoomType.REST:
            return "A safe alcove to catch your breath."
        elif rtype == RoomType.SHOP:
            return "A wandering merchant offers supplies."
        elif rtype == RoomType.EXIT:
            return "The exit is near. Escape with your spoils!"
        return ""

    def _room_hint(self, room):
        rtype = room["type"]
        hints = {
            RoomType.COMBAT: "Press ENTER to fight",
            RoomType.ELITE: "Press ENTER to challenge",
            RoomType.BOSS: "Press ENTER to confront the boss",
            RoomType.LOOT: "Press ENTER to open",
            RoomType.REST: "Press ENTER to rest",
            RoomType.SHOP: "Press ENTER to open shop",
            RoomType.EXIT: "Press ENTER to complete the run",
        }
        return hints.get(rtype, "")

    # ── Room cleared overlay ──────────────────────────────────────

    def draw_room_cleared(self):
        """Overlay shown briefly after clearing a room."""
        if not self.run:
            return
        # Solid dark backdrop
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        # Panel behind text
        panel_w, panel_h = 380, 90
        px = (self.w - panel_w) // 2
        py = (self.h - panel_h) // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 235))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, GOLD, (px, py, panel_w, panel_h), 2, border_radius=8)

        text = f"Room {self.run.room_index + 1} / {self.run.total_rooms} Cleared!"
        surf = self.font_large.render(text, True, GOLD)
        self.screen.blit(surf, ((self.w - surf.get_width()) // 2, py + 12))

        p = self.run.player
        recap = f"HP: {p.current_hp}/{p.max_hp}   SP: {p.sp}/{p.max_sp}"
        rsurf = self.font_small.render(recap, True, WHITE)
        self.screen.blit(rsurf, ((self.w - rsurf.get_width()) // 2, py + 52))

    # ── Loot display ──────────────────────────────────────────────

    def draw_loot_info(self, item):
        """Draw the loot reveal screen with chest and item card."""
        self.screen.fill(BG_COLOR)

        if not self.chest_opened:
            self._draw_closed_chest()
            hint = self.font_medium.render("A treasure chest! Press ENTER to open.", True, NEON_CYAN)
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, self.h // 2 + 90))
        else:
            self._draw_open_chest()
            self._draw_item_card(item)
            hint = self.font_medium.render("ENTER - Take & Continue", True, NEON_CYAN)
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, self.h // 2 + 130))

    def _draw_closed_chest(self):
        """Draw a closed treasure chest in the center of the screen."""
        cx = self.w // 2
        cy = self.h // 2

        # Chest body
        body_w, body_h = 100, 60
        body_x = cx - body_w // 2
        body_y = cy - 10
        pygame.draw.rect(self.screen, (140, 100, 60), (body_x, body_y, body_w, body_h), border_radius=4)
        pygame.draw.rect(self.screen, (120, 85, 50), (body_x, body_y, body_w, body_h), width=2, border_radius=4)

        # Lid (triangle-ish trapezoid)
        lid_h = 25
        lid_points = [
            (body_x - 5, body_y),
            (body_x + body_w + 5, body_y),
            (body_x + body_w - 10, body_y - lid_h),
            (body_x + 10, body_y - lid_h),
        ]
        pygame.draw.polygon(self.screen, (200, 170, 50), lid_points)
        pygame.draw.polygon(self.screen, (180, 150, 40), lid_points, width=2)

        # Latch
        latch_w, latch_h = 12, 14
        latch_x = cx - latch_w // 2
        latch_y = body_y - 4
        pygame.draw.rect(self.screen, (255, 215, 0), (latch_x, latch_y, latch_w, latch_h), border_radius=2)

        # Ground shadow
        shadow = pygame.Surface((body_w + 10, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), (0, 0, body_w + 10, 8))
        self.screen.blit(shadow, (cx - (body_w + 10) // 2, body_y + body_h - 2))

    def _draw_open_chest(self):
        """Draw an open treasure chest with lid flipped back."""
        cx = self.w // 2
        cy = self.h // 2

        body_w, body_h = 100, 60
        body_x = cx - body_w // 2
        body_y = cy - 10

        # Lid flipped open (drawn behind body)
        lid_h = 25
        lid_points = [
            (body_x - 5, body_y),
            (body_x + 15, body_y),
            (body_x + 5, body_y - lid_h - 10),
            (body_x - 15, body_y - lid_h),
        ]
        pygame.draw.polygon(self.screen, (200, 170, 50), lid_points)
        pygame.draw.polygon(self.screen, (180, 150, 40), lid_points, width=2)

        # Chest body
        pygame.draw.rect(self.screen, (140, 100, 60), (body_x, body_y, body_w, body_h), border_radius=4)
        pygame.draw.rect(self.screen, (120, 85, 50), (body_x, body_y, body_w, body_h), width=2, border_radius=4)

        # Inner glow (treasure inside)
        glow = pygame.Surface((body_w - 16, body_h - 16), pygame.SRCALPHA)
        glow.fill((*GOLD, 40))
        self.screen.blit(glow, (body_x + 8, body_y + 8))

        # Ground shadow
        shadow = pygame.Surface((body_w + 10, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), (0, 0, body_w + 10, 8))
        self.screen.blit(shadow, (cx - (body_w + 10) // 2, body_y + body_h - 2))

        # Sparks
        for sp in self.chest_sparks:
            alpha = max(0, 255 - int(255 * (sp["timer"] / sp["lifetime"])))
            size = sp["size"]
            spark_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            spark_surf.fill((*sp["color"], alpha))
            self.screen.blit(spark_surf, (int(sp["x"]), int(sp["y"])))

    def _spawn_chest_sparks(self):
        """Burst of sparks when the chest opens."""
        cx = self.w // 2
        cy = self.h // 2 - 20
        for _ in range(10):
            angle = random.uniform(-math.pi, 0)
            speed = random.uniform(2.0, 5.0)
            self.chest_sparks.append({
                "x": cx + random.randint(-30, 30),
                "y": cy + random.randint(-10, 10),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "timer": 0,
                "lifetime": random.randint(400, 700),
                "color": GOLD,
                "size": random.randint(3, 5),
            })

    def _draw_item_card(self, item):
        """Draw the revealed item card above the open chest."""
        from item import Weapon, Armor, Consumable, Rarity

        panel_w, panel_h = 320, 140
        px = (self.w - panel_w) // 2
        py = self.h // 2 - 150

        # Rarity colors
        if isinstance(item, Consumable):
            rarity_color = (185, 185, 195)
            glow_color = None
        else:
            rarity_colors = {
                Rarity.COMMON: (185, 185, 195),
                Rarity.RARE: (60, 140, 255),
                Rarity.EPIC: (180, 60, 255),
                Rarity.LEGENDARY: (255, 215, 0),
            }
            rarity_color = rarity_colors.get(item.rarity, WHITE)
            glow_colors = {
                Rarity.RARE: (60, 140, 255),
                Rarity.EPIC: (180, 60, 255),
                Rarity.LEGENDARY: (255, 215, 0),
            }
            glow_color = glow_colors.get(item.rarity)

        # Rarity glow behind card
        if glow_color:
            pulse = 0.6 + 0.4 * math.sin(self._elapsed * 0.006)
            glow = pygame.Surface((panel_w + 16, panel_h + 16), pygame.SRCALPHA)
            glow.fill((*glow_color, int(35 * pulse)))
            self.screen.blit(glow, (px - 8, py - 8))

        # Panel background
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 235))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, rarity_color, (px, py, panel_w, panel_h), width=2, border_radius=8)

        # Title
        title = self.font_large.render("LOOT!", True, GOLD)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, py + 12))

        # Item slot tag
        if isinstance(item, Weapon):
            slot_text = "[Weapon]"
        elif isinstance(item, Armor):
            slot_text = "[Armor]"
        elif isinstance(item, Consumable):
            slot_text = "[Consumable]"
        else:
            slot_text = "[Item]"
        slot_surf = self.font_hud.render(slot_text, True, DIM_WHITE)
        self.screen.blit(slot_surf, ((self.w - slot_surf.get_width()) // 2, py + 42))

        # Item name
        name_surf = self.font_medium.render(item.name, True, rarity_color)
        self.screen.blit(name_surf, ((self.w - name_surf.get_width()) // 2, py + 62))

        # Item stats
        if isinstance(item, Weapon):
            stat_text = f"+{item.atk} ATK"
        elif isinstance(item, Armor):
            stat_text = f"+{item.defense} DEF"
        elif isinstance(item, Consumable):
            stat_text = f"+{item.hp_restore} HP"
        else:
            stat_text = ""
        if stat_text:
            stat_surf = self.font_small.render(stat_text, True, WHITE)
            self.screen.blit(stat_surf, ((self.w - stat_surf.get_width()) // 2, py + 90))

        # Rarity label
        if not isinstance(item, Consumable):
            rarity_surf = self.font_small.render(item.rarity.name, True, rarity_color)
            self.screen.blit(rarity_surf, ((self.w - rarity_surf.get_width()) // 2, py + 112))

    # ── Shrine ─────────────────────────────────────────────────────

    def draw_shrine(self):
        """Draw the shrine room with 3 blessing choices."""
        self.screen.fill(BG_COLOR)
        title = self.font_title.render("Ancient Shrine", True, GOLD)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, 60))

        desc = self.font_medium.render("Choose a blessing:", True, DIM_WHITE)
        self.screen.blit(desc, ((self.w - desc.get_width()) // 2, 110))

        blessings = [
            ("1", "Blessing of Might", "+20% ATK for this run", (255, 100, 60)),
            ("2", "Blessing of Fortitude", "+20% DEF for this run", (60, 160, 255)),
            ("3", "Blessing of Vitality", "Regen 5 HP/turn for this run", (80, 220, 80)),
        ]
        for i, (key, name, effect, color) in enumerate(blessings):
            by = 170 + i * 90
            panel = pygame.Surface((500, 70), pygame.SRCALPHA)
            panel.fill((20, 15, 40, 200))
            self.screen.blit(panel, ((self.w - 500) // 2, by))
            pygame.draw.rect(self.screen, color, ((self.w - 500) // 2, by, 500, 70), 1, border_radius=5)

            key_surf = self.font_large.render(key, True, color)
            self.screen.blit(key_surf, ((self.w - 500) // 2 + 20, by + 12))

            name_surf = self.font_medium.render(name, True, WHITE)
            self.screen.blit(name_surf, ((self.w - 500) // 2 + 60, by + 8))

            eff_surf = self.font_small.render(effect, True, DIM_WHITE)
            self.screen.blit(eff_surf, ((self.w - 500) // 2 + 60, by + 40))

        hint = self.font_hud.render("[1/2/3] Pick a blessing", True, (120, 120, 140))
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, 450))

    # ── Trap ───────────────────────────────────────────────────────

    def draw_trap_result(self, trap_type: str):
        """Draw the trap result overlay."""
        self.screen.fill(BG_COLOR)

        trap_info = {
            "spike": ("Spike Trap!", "You take 15% max HP damage.", RED),
            "gas": ("Poison Gas!", "You are Poisoned for 2 turns.", (100, 200, 80)),
            "collapse": ("Collapse!", "You are Stunned for 1 turn.", (255, 255, 100)),
            "dodge": ("Trap Dodged!", "Your Rogue instincts saved you.", NEON_CYAN),
        }
        info = trap_info.get(trap_type, ("Trap!", "Something happened.", RED))

        icon = self.font_icon.render("⚠", True, info[2])
        self.screen.blit(icon, ((self.w - icon.get_width()) // 2, 140))

        title = self.font_title.render(info[0], True, info[2])
        self.screen.blit(title, ((self.w - title.get_width()) // 2, 200))

        desc = self.font_small.render(info[1], True, DIM_WHITE)
        self.screen.blit(desc, ((self.w - desc.get_width()) // 2, 250))

        hint = self.font_hud.render("[ENTER] Continue", True, (120, 120, 140))
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, 400))

    # ── Exit / Run complete ───────────────────────────────────────

    def draw_run_complete(self):
        self.screen.fill(BG_COLOR)
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 10))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render("Dungeon Cleared!", True, GOLD)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, self.h // 2 - 60))

        bonus = self.run.floor * 20 + self.run.room_index * 10
        lines = [
            f"Rooms cleared: {self.run.room_index}/{self.run.total_rooms}",
            f"Enemies defeated: {self.run.enemies_defeated}",
            f"Gold earned: {self.run.total_gold} (+{bonus} bonus)",
        ]
        cy = self.h // 2
        for line in lines:
            s = self.font_small.render(line, True, WHITE)
            self.screen.blit(s, ((self.w - s.get_width()) // 2, cy))
            cy += 24

        hint = self.font_medium.render("Press ENTER to return to Hub", True, GOLD)
        self.screen.blit(hint, ((self.w - hint.get_width()) // 2, cy + 20))

    # ── Death screen ──────────────────────────────────────────────

    def draw_death(self, dt_ms: int):
        # Dark red-tinted background
        self.screen.fill((10, 0, 0))

        # Vignette overlay (radial gradient approximation)
        for i in range(8):
            alpha = 100 - i * 12
            margin = i * 40
            vw = self.w - margin * 2
            vh = self.h - margin * 2
            if vw > 0 and vh > 0:
                v_surf = pygame.Surface((vw, vh), pygame.SRCALPHA)
                v_surf.fill((60, 0, 0, max(0, alpha)))
                self.screen.blit(v_surf, (margin, margin))

        # Pulsing "GAME OVER" title
        pulse = abs(math.sin(dt_ms * 0.003)) * 30
        title_color = (min(255, int(255 + pulse)), min(255, int(50 + pulse)), min(255, int(50 + pulse)))
        title = self.font_large.render("GAME OVER", True, title_color)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, self.h // 2 - 180))

        # Subtitle
        subtitle = self.font_medium.render("You fell in the dungeon...", True, DIM_WHITE)
        self.screen.blit(subtitle, ((self.w - subtitle.get_width()) // 2, self.h // 2 - 130))

        # Run Stats Panel
        panel_w, panel_h = 380, 160
        px = (self.w - panel_w) // 2
        py = self.h // 2 - 90

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((*PANEL_BG, 200))
        self.screen.blit(panel_surf, (px, py))
        pygame.draw.rect(self.screen, RED, (px, py, panel_w, panel_h), 2, border_radius=8)

        # Panel header
        header = self.font_medium.render("Run Summary", True, RED)
        self.screen.blit(header, ((self.w - header.get_width()) // 2, py + 10))

        player = self.run.player
        lost_gold = player.gold // 2
        lines = [
            f"Floor reached: {self.run.floor}",
            f"Rooms cleared: {self.run.room_index}/{self.run.total_rooms}",
            f"Enemies defeated: {self.run.enemies_defeated}",
            f"Gold earned this run: {self.run.total_gold}",
            f"Gold lost (50%): {lost_gold}",
        ]
        cy = py + 40
        for line in lines:
            s = self.font_small.render(line, True, WHITE)
            self.screen.blit(s, ((self.w - s.get_width()) // 2, cy))
            cy += 22

        # Penalty notice
        penalty = self.font_small.render("Half your gold was lost in the fall...", True, RED)
        penalty_surf = penalty.convert_alpha()
        penalty_surf.set_alpha(180)
        self.screen.blit(penalty_surf, ((self.w - penalty_surf.get_width()) // 2, self.h // 2 + 90))

        # Footer
        footer = self.font_medium.render("Press ENTER to return to Hub (Floor reset to 1)", True, DIM_WHITE)
        self.screen.blit(footer, ((self.w - footer.get_width()) // 2, self.h // 2 + 140))

    # ── Dungeon shop ──────────────────────────────────────────────

    def _draw_dungeon_shop(self):
        from item import Consumable, Rarity, merge_into_stack
        p = self.run.player
        items = [
            {"name": "Small Potion", "cost": 60, "hp": 30},
            {"name": "Large Potion", "cost": 144, "hp": 75},
        ]

        # Shop panel
        panel_w, panel_h = 380, 130
        px = (self.w - panel_w) // 2
        py = 300
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 220))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, NEON_CYAN, (px, py, panel_w, panel_h), 1, border_radius=6)

        # Gold
        gold_text = f"* Gold: {p.gold}g"
        gsurf = self.font_small.render(gold_text, True, GOLD)
        self.screen.blit(gsurf, (px + panel_w - gsurf.get_width() - 12, py + 8))

        # Items
        for i, item in enumerate(items):
            y = py + 30 + i * 30
            can = p.gold >= item["cost"]
            color = WHITE if can else (120, 120, 120)
            text = f"[{i + 1}] {item['name']}  {item['cost']}g  (+{item['hp']} HP)"
            s = self.font_small.render(text, True, color)
            self.screen.blit(s, (px + 12, y))

        # Controls
        hint = self.font_hud.render("1/2: Buy   ESC: Leave", True, (120, 120, 140))
        self.screen.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 22))

    def _draw_room_icon(self, icon_type: str, cx: int, cy: int, color, size: int = 32):
        """Draw a procedural room type icon centered at (cx, cy)."""
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        half = size // 2
        if icon_type == "combat":
            # Crossed swords
            pygame.draw.line(s, color, (half - 4, 4), (half + 4, size - 4), max(1, size // 12))
            pygame.draw.line(s, color, (half + 4, 4), (half - 4, size - 4), max(1, size // 12))
            pygame.draw.line(s, color, (half, 2), (half, size // 3), max(1, size // 10))
            pygame.draw.line(s, color, (half, size - size // 3), (half, size - 2), max(1, size // 10))
        elif icon_type == "elite":
            # Star
            points = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                r = half - 2 if i % 2 == 0 else half // 2
                px = half + r * math.cos(angle)
                py = half - r * math.sin(angle)
                points.append((px, py))
            pygame.draw.polygon(s, color, points)
        elif icon_type == "loot":
            # Diamond / gem
            pygame.draw.polygon(s, color, [
                (half, 2), (size - 2, half), (half, size - 2), (2, half)
            ])
        elif icon_type == "rest":
            # Crescent moon
            pygame.draw.circle(s, color, (half - 1, half), half - 3, max(1, size // 10))
            pygame.draw.circle(s, (0, 0, 0, 0), (half + 2, half), half - 4)
        elif icon_type == "shop":
            # Potion flask
            neck_w = max(2, size // 5)
            pygame.draw.rect(s, color, (half - neck_w // 2, 2, neck_w, size // 3), border_radius=1)
            pygame.draw.ellipse(s, color, (2, size // 3, size - 4, size - size // 3 - 2), width=max(1, size // 12))
        elif icon_type == "exit":
            # Up arrow
            pygame.draw.polygon(s, color, [
                (half, 2), (size - 4, size // 2), (half + size // 5, size // 2),
                (half + size // 5, size - 4), (half - size // 5, size - 4),
                (half - size // 5, size // 2), (4, size // 2)
            ])
        elif icon_type == "boss":
            # Skull-like shape: two eye circles + jaw line
            head_r = half - 4
            pygame.draw.circle(s, color, (half, half - 2), head_r, max(1, size // 10))
            # Eyes
            eye_r = max(2, size // 8)
            pygame.draw.circle(s, color, (half - 4, half - 4), eye_r)
            pygame.draw.circle(s, color, (half + 4, half - 4), eye_r)
            # Jaw / mouth
            jaw_y = half + 5
            pygame.draw.line(s, color, (half - 5, jaw_y), (half + 5, jaw_y), max(1, size // 12))
            pygame.draw.line(s, color, (half - 3, jaw_y + 3), (half + 3, jaw_y + 3), max(1, size // 12))
        self.screen.blit(s, (cx - half, cy - half))
