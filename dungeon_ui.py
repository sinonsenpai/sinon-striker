"""
Dungeon UI — floor select, room display, room cleared overlay, and shop.
"""

import math
import pygame
import random
from dungeon import RoomType, ROOM_ICONS, ROOM_COLORS, ROOM_LABELS, ENEMY_POOL, FLAVOR


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
        self._elapsed = 0.0
        self.branch_selection = 0

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

    def reset_branch_selection(self):
        self.branch_selection = 0

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

        # Room counter
        counter = self.font_medium.render(f"Room {self.run.room_index + 1} / {total}", True, DIM_WHITE)
        self.screen.blit(counter, ((self.w - counter.get_width()) // 2, 30))

        # Progress bar
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

        # Description
        desc = self._room_desc(room)
        desc_surf = self.font_small.render(desc, True, DIM_WHITE)
        self.screen.blit(desc_surf, ((self.w - desc_surf.get_width()) // 2, 190))

        # Action hint
        hint = self._room_hint(room)
        hint_color = GOLD if rtype == RoomType.EXIT else (RED if rtype == RoomType.BOSS else NEON_CYAN)
        hint_surf = self.font_medium.render(hint, True, hint_color)
        self.screen.blit(hint_surf, ((self.w - hint_surf.get_width()) // 2, 240))

        # HP/SP summary
        p = self.run.player
        hp_sp = self.font_small.render(f"HP: {p.current_hp}/{p.max_hp}   SP: {p.sp}/{p.max_sp}", True, WHITE)
        self.screen.blit(hp_sp, ((self.w - hp_sp.get_width()) // 2, 280))

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

    # ── Branch choice ─────────────────────────────────────────────

    def draw_branch_choice(self):
        """Draw two room cards side by side for the player to choose."""
        if not self.run or not self.run.branching:
            return

        self.screen.fill(BG_COLOR)

        # Title
        title = self.font_title.render("Choose Your Path", True, NEON_CYAN)
        self.screen.blit(title, ((self.w - title.get_width()) // 2, 40))

        # Subtitle
        sub = self.font_small.render("The corridor splits ahead...", True, DIM_WHITE)
        self.screen.blit(sub, ((self.w - sub.get_width()) // 2, 85))

        # Cards
        card_w, card_h = 250, 200
        gap = 30
        total_w = card_w * 2 + gap
        start_x = (self.w - total_w) // 2
        card_y = (self.h - card_h) // 2 - 20

        for i, room in enumerate(self.run.branch_choices):
            cx = start_x + i * (card_w + gap)
            selected = i == self.branch_selection

            # Card background
            card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            card.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 220))
            self.screen.blit(card, (cx, card_y))

            # Border color
            border_color = NEON_CYAN if selected else NEON_CYAN_DIM
            border_width = 3 if selected else 1
            pygame.draw.rect(self.screen, border_color,
                             (cx, card_y, card_w, card_h), width=border_width, border_radius=8)

            # Selection pulse
            if selected:
                pulse = 0.7 + 0.3 * math.sin(self._elapsed * 0.005)
                sel_overlay = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                sel_overlay.fill((*NEON_CYAN, int(20 * pulse)))
                self.screen.blit(sel_overlay, (cx, card_y))

            # Room type icon and label
            rtype = room["type"]
            icon_text = ROOM_ICONS.get(rtype, "?")
            label = ROOM_LABELS.get(rtype, "?")
            color = ROOM_COLORS.get(rtype, WHITE)

            self._draw_room_icon(icon_text, cx + card_w // 2, card_y + 30, color, size=28)

            label_surf = self.font_large.render(label, True, color)
            lx = cx + (card_w - label_surf.get_width()) // 2
            self.screen.blit(label_surf, (lx, card_y + 65))

            # Flavor text (wrapped)
            flavor = room.get("flavor", "")
            flavor_font = self.font_small
            max_w = card_w - 24
            words = flavor.split()
            lines = []
            current = ""
            for word in words:
                test = current + " " + word if current else word
                if flavor_font.size(test)[0] <= max_w:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)

            fy = card_y + 100
            for line in lines[:3]:  # max 3 lines
                fs = flavor_font.render(line, True, DIM_WHITE)
                self.screen.blit(fs, (cx + (card_w - fs.get_width()) // 2, fy))
                fy += fs.get_height() + 2

            # Risk / Reward hints
            hint_y = card_y + card_h - 52
            if rtype == RoomType.BOSS:
                risk = "Risk: EXTREME"
                reward = "Reward: Rare+ Gear"
            elif rtype in (RoomType.COMBAT, RoomType.ELITE):
                risk = "Risk: High" if rtype == RoomType.ELITE else "Risk: Low"
                reward = "Reward: XP + Gold"
            elif rtype == RoomType.LOOT:
                risk = "Risk: None"
                reward = "Reward: Gear"
            elif rtype == RoomType.REST:
                risk = "Risk: None"
                reward = "Reward: HP Restore"
            elif rtype == RoomType.SHOP:
                risk = "Risk: None"
                reward = "Reward: Consumables"
            else:
                risk = ""
                reward = ""

            if risk:
                rs = self.font_hud.render(risk, True, (170, 170, 190))
                self.screen.blit(rs, (cx + (card_w - rs.get_width()) // 2, hint_y))
                hint_y += rs.get_height() + 2
            if reward:
                rw = self.font_hud.render(reward, True, (170, 170, 190))
                self.screen.blit(rw, (cx + (card_w - rw.get_width()) // 2, hint_y))

            # Direction hint
            dir_text = "< LEFT" if i == 0 else "RIGHT >"
            dir_color = NEON_CYAN if selected else (80, 80, 100)
            dir_surf = self.font_small.render(dir_text, True, dir_color)
            self.screen.blit(dir_surf, (cx + (card_w - dir_surf.get_width()) // 2, card_y + card_h - 18))

        # Controls hint at bottom
        ctrl = self.font_small.render("[LEFT/RIGHT] Select   [ENTER] Confirm", True, (90, 90, 115))
        self.screen.blit(ctrl, ((self.w - ctrl.get_width()) // 2, self.h - 40))

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
