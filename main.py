"""
Main entry point for SINON STRIKER — turn-based battle RPG.
Handles title screen, hub town, dungeon runs, and battle loop via state management.
"""
import sys
import os
import random
import pygame

from character import Character, Enemy
from combat_manager import CombatManager, TurnState
from battle_ui import BattleUI
from title_screen import TitleScreen
from hub_screen import HubScreen, HubSubState
from item import Weapon, Armor, Rarity, ItemSlot, LootGenerator, Consumable, merge_into_stack
from audio import SoundManager
from dungeon import DungeonRun, RoomType, ENEMY_POOL
from dungeon_ui import DungeonUI
from enum import Enum, auto
from save_manager import save_game, load_game
from achievements import AchievementManager, AchievementToast
from skills import SkillRegistry, PlayerClass, SkillTree


class GameState(Enum):
    TITLE = auto()
    OPTIONS = auto()
    CLASS_SELECT = auto()   # pick Warrior/Mage/Rogue
    TREE_SELECT = auto()    # pick skill tree for chosen class
    HUB = auto()
    DUNGEON = auto()        # floor select
    DUNGEON_ROOM = auto()   # current room display
    BATTLE = auto()


WIDTH, HEIGHT = 800, 600
FPS = 60


def _trigger_title_burst(title, event):
    if hasattr(event, "pos"):
        x, y = event.pos
    else:
        x = random.randint(WIDTH // 3, 2 * WIDTH // 3)
        y = random.randint(HEIGHT // 2 - 40, HEIGHT // 2 + 80)
    title.trigger_burst(x, y)


def _handle_room(player, dungeon, dungeon_ui, snd, ach_manager=None):
    """Process the current dungeon room and return next state or None."""
    room = dungeon.current
    if not room:
        return GameState.HUB

    rtype = room["type"]

    if rtype == RoomType.COMBAT or rtype == RoomType.ELITE or rtype == RoomType.BOSS:
        # Create enemy and go to battle
        enemy_data = ENEMY_POOL.get(room["enemy"], ENEMY_POOL["slime"])
        if "floor" in room:
            from dungeon import scale_enemy
            enemy_data = scale_enemy(enemy_data, room["floor"])
        enemy = Enemy(
            enemy_data["name"], enemy_data["hp"], enemy_data["atk"], enemy_data["defn"],
            enemy_data.get("xp_reward", 0),
            enemy_data.get("gold_min", 20), enemy_data.get("gold_max", 40)
        )
        enemy._eva = enemy_data.get("eva", 0.05)
        is_boss = rtype == RoomType.BOSS
        # Sync run blessings to player for this combat
        player.run_blessings = dict(dungeon.blessings) if hasattr(dungeon, 'blessings') else {}
        combat = CombatManager(player, enemy, snd, ach_manager, is_boss=is_boss, floor=room.get("floor", 1))
        combat.in_dungeon = True
        combat._apply_blessings()
        return ("battle", combat)

    elif rtype == RoomType.LOOT:
        item = LootGenerator.generate(floor=room.get("floor", 1))
        return ("loot", item)

    elif rtype == RoomType.REST:
        heal = int(player.max_hp * 0.3)
        player.current_hp = min(player.max_hp, player.current_hp + heal)
        dungeon.mark_cleared()
        if snd:
            snd.play("rest_heal")
        return "rest"

    elif rtype == RoomType.SHOP:
        # Shop is handled in-room via key presses
        return "shop"

    elif rtype == RoomType.SHRINE:
        # Shrine offers 3 blessings
        return "shrine"

    elif rtype == RoomType.TRAP:
        # Trap triggers immediately with Rogue dodge chance
        dodge = False
        if hasattr(player, 'player_class') and player.player_class:
            from skills import PlayerClass
            if player.player_class == PlayerClass.ROGUE and random.random() < 0.5:
                dodge = True
        if dodge:
            if ach_manager:
                ach_manager.unlock("light_footed")
            return ("trap", "dodge")
        effect = random.choice(["spike", "gas", "collapse"])
        return ("trap", effect)

    elif rtype == RoomType.EXIT:
        bonus = dungeon.floor * 20 + dungeon.room_index * 10
        player.gold += bonus
        dungeon.total_gold += bonus
        dungeon.mark_cleared()
        if ach_manager:
            ach_manager.inc("dungeons_completed")
        return ("complete", dungeon.floor)

    return None


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SINON STRIKER")
    clock = pygame.time.Clock()

    snd = SoundManager()
    snd.init()
    snd.play_title_music()

    ach_manager = AchievementManager()
    ach_manager.load()
    ach_toast = AchievementToast(WIDTH)

    state = GameState.TITLE
    title_screen = TitleScreen(screen)
    hub_screen = None
    dungeon_run = None
    dungeon_ui = DungeonUI(screen)
    player = None
    current_floor = 1

    combat = None
    ui = None
    god_mode = False
    options_screen = None

    # Class / Tree selection state
    class_idx = 0
    tree_idx = 0
    selected_class = None

    # Loot display temp state
    loot_item = None
    dungeon_sub = ""  # "loot", "rest", "complete", "death", "shop"

    running = True
    while running:
        dt_ms = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if player is not None:
                    save_game(player, snd, ach_manager, current_floor)
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                if state == GameState.BATTLE and ui is not None:
                    if event.y > 0:
                        ui.scroll_log_up()
                    elif event.y < 0:
                        ui.scroll_log_down()

            elif event.type == pygame.KEYDOWN:
                # ── TITLE ──────────────────────────────────────────
                if state == GameState.TITLE:
                    if event.key in (pygame.K_w, pygame.K_UP):
                        title_screen.move_up()
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        title_screen.move_down()
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        result = title_screen.confirm()
                        if result == "options":
                            options_screen = title_screen.enter_options(snd)
                            state = GameState.OPTIONS
                        elif result in ("continue", "new_game"):
                            pass  # fade handles the transition
                    _trigger_title_burst(title_screen, event)

                # ── OPTIONS ───────────────────────────────────────
                elif state == GameState.OPTIONS and options_screen is not None:
                    if event.key in (pygame.K_w, pygame.K_UP):
                        options_screen.move_up()
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        options_screen.move_down()
                    elif event.key == pygame.K_LEFT:
                        options_screen.adjust_selected(-0.05)
                    elif event.key == pygame.K_RIGHT:
                        options_screen.adjust_selected(0.05)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        result = options_screen.confirm()
                        if result == "back":
                            state = GameState.TITLE
                    elif event.key == pygame.K_ESCAPE:
                        state = GameState.TITLE

                # ── CLASS SELECT ──────────────────────────────────
                elif state == GameState.CLASS_SELECT:
                    classes = list(PlayerClass)
                    if event.key in (pygame.K_w, pygame.K_UP):
                        class_idx = (class_idx - 1) % len(classes)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        class_idx = (class_idx + 1) % len(classes)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        selected_class = classes[class_idx]
                        player = Character("Hero", max_hp=100, atk=15, defn=5)
                        player.apply_class_stats(selected_class)
                        tree_idx = 0
                        state = GameState.TREE_SELECT

                # ── TREE SELECT ───────────────────────────────────
                elif state == GameState.TREE_SELECT:
                    trees = SkillRegistry.get_trees_for_class(selected_class)
                    if event.key in (pygame.K_w, pygame.K_UP):
                        tree_idx = (tree_idx - 1) % len(trees)
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        tree_idx = (tree_idx + 1) % len(trees)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        player.chosen_tree = trees[tree_idx]
                        hub_screen = HubScreen(screen, player, ach_manager, snd)
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        save_game(player, snd, ach_manager, current_floor)
                        state = GameState.HUB

                # ── HUB ────────────────────────────────────────────
                elif state == GameState.HUB and hub_screen is not None:
                    sub = hub_screen.sub_state
                    if sub == HubSubState.MAIN:
                        if event.key == pygame.K_LEFT:
                            hub_screen.move_left()
                        elif event.key == pygame.K_RIGHT:
                            hub_screen.move_right()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            result = hub_screen.confirm()
                            if result == "battle":
                                pass  # handled in update
                        elif event.key == pygame.K_a:
                            hub_screen.open_achievements()
                        elif event.key == pygame.K_ESCAPE:
                            snd.play("menu_back")
                            hub_screen.cancel()

                    elif sub == HubSubState.SMITHY_INVENTORY:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            hub_screen.smithy_move_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            hub_screen.smithy_move_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            hub_screen.smithy_sell()
                        elif event.key == pygame.K_f:
                            hub_screen.smithy_sort()
                        elif event.key == pygame.K_ESCAPE:
                            snd.play("menu_back")
                            hub_screen.cancel()
                            save_game(player, snd, ach_manager, current_floor)

                    elif sub == HubSubState.APOTHECARY:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            hub_screen.shop_move_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            hub_screen.shop_move_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            hub_screen.shop_buy()
                        elif event.key == pygame.K_ESCAPE:
                            snd.play("menu_back")
                            hub_screen.cancel()
                            save_game(player, snd, ach_manager, current_floor)

                    elif sub == HubSubState.MERCHANT:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            hub_screen.merchant_move_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            hub_screen.merchant_move_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            hub_screen.merchant_buy()
                        elif event.key == pygame.K_ESCAPE:
                            snd.play("menu_back")
                            hub_screen.cancel()
                            save_game(player, snd, ach_manager, current_floor)

                    elif sub == HubSubState.RETURN_PROMPT:
                        if event.key == pygame.K_y:
                            result = hub_screen.confirm_return()
                            if result == "title":
                                title_screen.start_fade_in()
                                snd.play_title_music()
                                state = GameState.TITLE
                        elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                            snd.play("menu_back")
                            hub_screen.decline_return()

                    elif sub == HubSubState.TOAST:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                            hub_screen.cancel()
                            save_game(player, snd, ach_manager, current_floor)

                    elif sub == HubSubState.ACHIEVEMENTS:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            hub_screen.achievements_move_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            hub_screen.achievements_move_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                            snd.play("menu_back")
                            hub_screen.cancel()
                            save_game(player, snd, ach_manager, current_floor)

                # ── DUNGEON (floor select) ────────────────────────
                elif state == GameState.DUNGEON:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        dungeon_run = DungeonRun(player, floor=current_floor)
                        ach_manager.set("deepest_floor", max(ach_manager.counters.get("deepest_floor", 0), dungeon_run.floor))
                        dungeon_ui.set_run(dungeon_run)
                        dungeon_sub = ""
                        loot_item = None
                        state = GameState.DUNGEON_ROOM
                    elif event.key == pygame.K_ESCAPE:
                        state = GameState.HUB
                    elif event.key == pygame.K_F3:
                        # DEV: Jump straight to a loot room
                        dungeon_run = DungeonRun(player, floor=current_floor)
                        dungeon_run.rooms = [
                            {"type": RoomType.LOOT, "enemy": None, "cleared": False},
                            {"type": RoomType.EXIT, "enemy": None, "cleared": False},
                        ]
                        dungeon_run.total_rooms = 2
                        dungeon_run.room_index = 0
                        dungeon_ui.set_run(dungeon_run)
                        dungeon_ui.reset_chest()
                        dungeon_sub = ""
                        loot_item = None
                        state = GameState.DUNGEON_ROOM

                # ── DUNGEON ROOM ──────────────────────────────────
                elif state == GameState.DUNGEON_ROOM and dungeon_run is not None:
                    if dungeon_sub == "branch":
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            dungeon_ui.branch_selection = 0
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            dungeon_ui.branch_selection = 1
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            dungeon_run.resolve_branch(dungeon_ui.branch_selection)
                            dungeon_sub = ""
                        continue

                    # Block ENTER while cleared overlay is playing
                    if dungeon_run.room_cleared:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            pass  # ignore, overlay still playing
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "":
                        result = _handle_room(player, dungeon_run, dungeon_ui, snd, ach_manager)
                        if result == "rest":
                            dungeon_sub = "rest"
                        elif result == "shop":
                            dungeon_sub = "shop"
                        elif result == "shrine":
                            dungeon_sub = "shrine"
                        elif isinstance(result, tuple) and result[0] == "trap":
                            dungeon_sub = result[1]  # "dodge", "spike", "gas", "collapse"
                            _apply_trap(player, result[1], dungeon_run, ach_manager)
                            dungeon_run.mark_cleared()
                        elif isinstance(result, tuple) and result[0] == "complete":
                            dungeon_sub = "complete"
                        elif isinstance(result, tuple) and result[0] == "battle":
                            combat = result[1]
                            ui = BattleUI(screen)
                            god_mode = False
                            dungeon_sub = ""
                            snd.start_battle_music()
                            state = GameState.BATTLE
                        elif isinstance(result, tuple) and result[0] == "loot":
                            loot_item = result[1]
                            dungeon_sub = "loot"
                            dungeon_ui.reset_chest()  # Start with closed chest
                    # Shop hotkeys (only when inside shop)
                    if dungeon_sub == "shop":
                        if event.key == pygame.K_1:
                            _buy_dungeon_shop(player, 0)
                        elif event.key == pygame.K_2:
                            _buy_dungeon_shop(player, 1)
                        elif event.key == pygame.K_ESCAPE:
                            dungeon_run.mark_cleared()
                            dungeon_sub = ""
                    elif dungeon_sub == "loot":
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            if not dungeon_ui.chest_opened:
                                # First press: open chest
                                dungeon_ui.chest_opened = True
                                dungeon_ui.chest_anim_timer = 300
                                dungeon_ui._spawn_chest_sparks()
                                snd.play("loot_drop")
                                dungeon_run.mark_cleared()
                            else:
                                # Second press: take item and advance
                                if loot_item:
                                    if isinstance(loot_item, Consumable):
                                        merge_into_stack(player.consumables, loot_item)
                                    else:
                                        player.inventory.append(loot_item)
                                    ach_manager.inc("items_found")
                                    if getattr(loot_item, "rarity", None) and loot_item.rarity.name == "LEGENDARY":
                                        ach_manager.inc("legendaries_found")
                                    loot_item = None
                                dungeon_ui.reset_chest()
                                dungeon_sub = ""
                                save_game(player, snd, ach_manager, current_floor)
                    elif dungeon_sub == "shrine":
                        if event.key == pygame.K_1 and dungeon_run.current:
                            dungeon_run.blessings["might"] = True
                            dungeon_run.mark_cleared()
                            dungeon_sub = ""
                            ach_manager.unlock("blessed")
                            ach_manager.inc("shrines_used")
                        elif event.key == pygame.K_2 and dungeon_run.current:
                            dungeon_run.blessings["fortitude"] = True
                            dungeon_run.mark_cleared()
                            dungeon_sub = ""
                            ach_manager.unlock("blessed")
                            ach_manager.inc("shrines_used")
                        elif event.key == pygame.K_3 and dungeon_run.current:
                            dungeon_run.blessings["vitality"] = True
                            dungeon_run.mark_cleared()
                            dungeon_sub = ""
                            ach_manager.unlock("blessed")
                            ach_manager.inc("shrines_used")
                    elif dungeon_sub in ("spike", "gas", "collapse", "dodge"):
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            dungeon_sub = ""
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "rest":
                        # Advance past rest room
                        if dungeon_run.current and dungeon_run.current["cleared"]:
                            dungeon_sub = ""
                    elif event.key == pygame.K_ESCAPE and dungeon_sub == "complete":
                        pass
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "complete":
                        current_floor = dungeon_run.floor + 1
                        # SP regen per floor
                        player.sp = min(player.max_sp, player.sp + 10)
                        snd.play("floor_up")
                        dungeon_sub = ""
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        save_game(player, snd, ach_manager, current_floor)
                        state = GameState.HUB
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "death":
                        # Game Over: full restore + floor reset + gold penalty
                        player.current_hp = player.max_hp
                        player.sp = player.max_sp
                        ach_manager.inc("deaths")
                        current_floor = 1
                        lost_gold = player.gold // 2
                        player.gold -= lost_gold
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        save_game(player, snd, ach_manager, current_floor)
                        state = GameState.HUB
                        dungeon_run = None
                    elif dungeon_sub == "complete" or dungeon_sub == "death":
                        pass  # prevent fall-through to battle
                # ── BATTLE ────────────────────────────────────────
                elif state == GameState.BATTLE and combat is not None:
                    if event.key in (pygame.K_PAGEUP, pygame.K_HOME):
                        if ui is not None:
                            ui.scroll_log_up()
                    elif event.key in (pygame.K_PAGEDOWN, pygame.K_END):
                        if ui is not None:
                            ui.scroll_log_down()

                    if combat.state == TurnState.VICTORY:
                        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            if combat.victory_phase == "level_up":
                                # Dismiss level-up overlay, clear so next ENTER exits
                                combat.victory_phase = "rewards"
                                combat._level_ups.clear()
                            elif combat._level_ups:
                                # First ENTER — show level-up celebration
                                combat.victory_phase = "level_up"
                                snd.play("level_up")
                            else:
                                # No level-up, exit battle
                                snd.stop_battle_music()
                                # Flawless victory check
                                if player.current_hp == player.max_hp:
                                    ach_manager.inc("flawless_victories")
                                if dungeon_run is not None:
                                    dungeon_run.enemies_defeated += 1
                                    dungeon_run.total_gold += combat._gold_dropped
                                    dungeon_run.mark_cleared()
                                    dungeon_sub = ""
                                    snd.play_hub_music()
                                    save_game(player, snd, ach_manager, current_floor)
                                    state = GameState.DUNGEON_ROOM
                                else:
                                    hub_screen.start_fade_in()
                                    snd.play_hub_music()
                                    save_game(player, snd, ach_manager, current_floor)
                                    state = GameState.HUB
                        elif event.key == pygame.K_r:
                            combat.reset()

                    elif combat.state == TurnState.DEFEAT:
                        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            snd.stop_battle_music()
                            if dungeon_run is not None:
                                dungeon_sub = "death"
                                snd.play_hub_music()
                                state = GameState.DUNGEON_ROOM
                            else:
                                hub_screen.start_fade_in()
                                snd.play_hub_music()
                                state = GameState.HUB
                        elif event.key == pygame.K_r:
                            combat.reset()

                    elif event.key == pygame.K_F1:
                        debug_weapon = Weapon("Debug Blade", Rarity.LEGENDARY, 50)
                        debug_armor = Armor("Debug Plate", Rarity.LEGENDARY, 50)
                        player.equip(debug_weapon)
                        player.equip(debug_armor)
                        combat._add_log("[DEBUG] Equipped Legendary gear (+50 ATK / +50 DEF)")

                    elif event.key == pygame.K_F2:
                        god_mode = not god_mode
                        combat._add_log(f"[DEBUG] God Mode {'ON' if god_mode else 'OFF'}")

                    elif event.key == pygame.K_F4:
                        # DEV: Equip full Dragon Set for set bonus testing
                        old_atk = player.atk
                        old_def = player.defn
                        dragon_weapon = Weapon("Fine Blade", Rarity.RARE, 50, set_name="Dragon")
                        dragon_armor = Armor("Fine Scale", Rarity.RARE, 50, set_name="Dragon")
                        player.equip(dragon_weapon)
                        player.equip(dragon_armor)
                        new_atk = player.atk
                        new_def = player.defn
                        combat._add_log(f"[DEV] Dragon Set equipped! ATK {old_atk} -> {new_atk}  |  DEF {old_def} -> {new_def}")

                    elif combat.state == TurnState.INVENTORY:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            combat.move_inv_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            combat.move_inv_down()
                        elif event.key == pygame.K_e:
                            combat.equip_selected()
                        elif event.key == pygame.K_u:
                            combat.unequip_selected()
                        elif event.key == pygame.K_TAB:
                            combat.toggle_inv_section()
                        elif event.key == pygame.K_f:
                            combat.sort_inventory()
                        elif event.key in (pygame.K_ESCAPE, pygame.K_b, pygame.K_i):
                            snd.play("menu_back")
                            combat.close_inventory()

                    elif combat.state == TurnState.MENU_SELECT:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            combat.move_menu_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            combat.move_menu_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            combat.confirm_action()
                        elif event.key == pygame.K_i:
                            combat.open_inventory()

                    elif combat.state == TurnState.SKILL_SELECT:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            combat.move_sub_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            combat.move_sub_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            combat.confirm_sub_action()
                        elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                            snd.play("menu_back")
                            combat.cancel_sub_menu()

                    elif combat.state == TurnState.ITEM_SELECT:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            combat.move_sub_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            combat.move_sub_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            combat.confirm_sub_action()
                        elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                            snd.play("menu_back")
                            combat.cancel_sub_menu()

        # ── State updates ─────────────────────────────────────────
        if state == GameState.TITLE:
            title_screen.update(dt_ms)
            if title_screen.fade_done:
                action = title_screen.chosen_action
                player = Character("Hero", max_hp=100, atk=15, defn=5)
                if action == "continue":
                    loaded, current_floor = load_game(player)
                    if not loaded:
                        current_floor = 1
                    ach_manager.load()
                    hub_screen = HubScreen(screen, player, ach_manager, snd)
                    hub_screen.start_fade_in()
                    snd.play_hub_music()
                    save_game(player, snd, ach_manager, current_floor)
                    state = GameState.HUB
                else:
                    # New Game — delete old save and start fresh
                    if os.path.exists("save_data.json"):
                        os.remove("save_data.json")
                    if os.path.exists("achievements.json"):
                        os.remove("achievements.json")
                    ach_manager.reset()
                    current_floor = 1
                    class_idx = 0
                    state = GameState.CLASS_SELECT

        elif state == GameState.OPTIONS and options_screen is not None:
            options_screen.update(dt_ms)

        elif state == GameState.HUB and hub_screen is not None:
            hub_screen.update(dt_ms)
            if hub_screen.fade_done:
                state = GameState.DUNGEON

        elif state == GameState.DUNGEON:
            dungeon_ui.floor_display = current_floor
            dungeon_ui.update(dt_ms)

        elif state == GameState.DUNGEON_ROOM and dungeon_run is not None:
            dungeon_ui.update(dt_ms)
            if dungeon_run.update(dt_ms):
                # Cleared overlay finished
                if dungeon_run.branching:
                    dungeon_sub = "branch"
                    dungeon_ui.branch_selection = 0
                else:
                    dungeon_run.advance()
                    dungeon_sub = ""
                    if dungeon_run.done:
                        current_floor = dungeon_run.floor + 1
                        player.sp = min(player.max_sp, player.sp + 10)
                        snd.play("floor_up")
                        ach_manager.inc("dungeons_completed")
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        save_game(player, snd, ach_manager, current_floor)
                        state = GameState.HUB

        elif state == GameState.BATTLE and combat is not None:
            if god_mode:
                player.current_hp = player.max_hp
            combat.update(dt_ms)

        # ── Achievement checks ────────────────────────────────────
        if player is not None:
            ach_manager.set("level_reached", player.level)
            # Tourist: track visited biomes
            if dungeon_run is not None:
                biome_name = dungeon_run.biome["name"]
                if biome_name == "The Depths":
                    ach_manager.set("visited_depths", 1)
                elif biome_name == "The Catacombs":
                    ach_manager.set("visited_catacombs", 1)
                elif biome_name == "The Abyss":
                    ach_manager.set("visited_abyss", 1)
                if ach_manager.counters.get("visited_depths", 0) and \
                   ach_manager.counters.get("visited_catacombs", 0) and \
                   ach_manager.counters.get("visited_abyss", 0):
                    ach_manager.unlock("tourist")
            if player.player_class:
                pc = player.player_class
                if pc == PlayerClass.WARRIOR:
                    ach_manager.set("level_warrior", player.level)
                elif pc == PlayerClass.MAGE:
                    ach_manager.set("level_mage", player.level)
                elif pc == PlayerClass.ROGUE:
                    ach_manager.set("level_rogue", player.level)
            # Scholar: check if player has unlocked all 8 skills
            available = SkillRegistry.get_available_skills(player)
            if len(available) >= 8:
                ach_manager.unlock("scholar")
            if player.get_active_sets():
                ach_manager.unlock("set_bonus")

        # ── Rendering ─────────────────────────────────────────────
        if state == GameState.TITLE:
            title_screen.draw(dt_ms)

        elif state == GameState.OPTIONS and options_screen is not None:
            options_screen.draw(dt_ms)

        elif state == GameState.CLASS_SELECT:
            _draw_class_select(screen, class_idx, dt_ms)

        elif state == GameState.TREE_SELECT:
            _draw_tree_select(screen, selected_class, tree_idx, dt_ms)

        elif state == GameState.HUB and hub_screen is not None:
            hub_screen.draw(dt_ms)

        elif state == GameState.DUNGEON:
            dungeon_ui.draw_floor_select()

        elif state == GameState.DUNGEON_ROOM and dungeon_run is not None:
            if dungeon_sub == "branch":
                dungeon_ui.draw_branch_choice()
            elif dungeon_sub == "loot":
                dungeon_ui.draw_loot_info(loot_item)
            elif dungeon_sub == "rest":
                dungeon_ui.draw_room()
                dungeon_ui.draw_room_cleared()
            elif dungeon_sub == "shop":
                dungeon_ui.draw_room()
            elif dungeon_sub == "shrine":
                dungeon_ui.draw_shrine()
            elif dungeon_sub in ("spike", "gas", "collapse", "dodge"):
                dungeon_ui.draw_trap_result(dungeon_sub)
            elif dungeon_sub == "complete":
                dungeon_ui.draw_run_complete()
            elif dungeon_sub == "death":
                dungeon_ui.draw_death(dt_ms)
            else:
                dungeon_ui.draw_room()
                if dungeon_run.room_cleared:
                    dungeon_ui.draw_room_cleared()

        elif state == GameState.BATTLE and combat is not None and ui is not None:
            ui.draw(combat, dt_ms)

        # ── Achievement toasts (render above all states) ──────────
        toast_finished = ach_toast.update(dt_ms)
        if toast_finished or ach_toast.is_idle():
            next_toast = ach_manager.pop_toast()
            if next_toast:
                ach_toast.show(next_toast)
                snd.play("achievement_unlock")
        if not ach_toast.is_idle():
            ach_toast.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


def _draw_class_select(screen, class_idx, dt_ms):
    """Draw the class selection screen."""
    import math
    w, h = screen.get_size()
    screen.fill((18, 14, 30))

    classes = list(PlayerClass)
    stats = {
        PlayerClass.WARRIOR: "HP 120  ATK 18  DEF 8  SP 50  Crit 5%",
        PlayerClass.MAGE: "HP 90  ATK 12  DEF 4  SP 75  Crit 5%",
        PlayerClass.ROGUE: "HP 100  ATK 15  DEF 5  SP 55  Crit 10%",
    }
    descs = {
        PlayerClass.WARRIOR: "Tanky brawler. Vanguard shield or Berserker rage.",
        PlayerClass.MAGE: "Spellcaster. Pyromancy fire or Arcanist control.",
        PlayerClass.ROGUE: "Nimble killer. Assassin burst or Trickster poison.",
    }

    font_title = pygame.font.SysFont("arial", 36, bold=True)
    font_class = pygame.font.SysFont("arial", 28, bold=True)
    font_stat = pygame.font.SysFont("arial", 16, bold=False)
    font_desc = pygame.font.SysFont("arial", 14, bold=False)
    font_hint = pygame.font.SysFont("arial", 15, bold=False)

    title = font_title.render("CHOOSE YOUR CLASS", True, (0, 240, 255))
    screen.blit(title, ((w - title.get_width()) // 2, h * 0.12))

    panel_w, panel_h = 400, 280
    px = (w - panel_w) // 2
    py = int(h * 0.22)

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((20, 15, 40, 225))
    screen.blit(panel, (px, py))
    pygame.draw.rect(screen, (0, 240, 255), (px, py, panel_w, panel_h), 2, border_radius=8)

    for i, pc in enumerate(classes):
        btn_y = py + 20 + i * 85
        btn_rect = pygame.Rect(px + 20, btn_y, panel_w - 40, 70)

        selected = i == class_idx
        if selected:
            pulse = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.005)
            sel = pygame.Surface((btn_rect.w, btn_rect.h), pygame.SRCALPHA)
            sel.fill((*((0, 240, 255)), int(35 * pulse)))
            screen.blit(sel, (btn_rect.x, btn_rect.y))
            pygame.draw.rect(screen, (0, 240, 255), btn_rect, 2, border_radius=5)
        else:
            pygame.draw.rect(screen, (60, 60, 75), btn_rect, 1, border_radius=5)

        prefix = "> " if selected else ""
        name = font_class.render(f"{prefix}{pc.value}", True, (0, 240, 255) if selected else (160, 160, 180))
        screen.blit(name, (btn_rect.x + 12, btn_rect.y + 8))

        stat_text = font_stat.render(stats[pc], True, (200, 200, 220))
        screen.blit(stat_text, (btn_rect.x + 12, btn_rect.y + 36))

        desc_text = font_desc.render(descs[pc], True, (140, 140, 165))
        screen.blit(desc_text, (btn_rect.x + 12, btn_rect.y + 54))

    hint = font_hint.render("[W/S or UP/DOWN] Navigate   [ENTER] Confirm", True, (100, 100, 130))
    screen.blit(hint, ((w - hint.get_width()) // 2, py + panel_h + 14))


def _draw_tree_select(screen, selected_class, tree_idx, dt_ms):
    """Draw the skill tree selection screen."""
    import math
    w, h = screen.get_size()
    screen.fill((18, 14, 30))

    trees = SkillRegistry.get_trees_for_class(selected_class)

    font_title = pygame.font.SysFont("arial", 36, bold=True)
    font_tree = pygame.font.SysFont("arial", 28, bold=True)
    font_desc = pygame.font.SysFont("arial", 14, bold=False)
    font_hint = pygame.font.SysFont("arial", 15, bold=False)

    title = font_title.render(f"{selected_class.value} — CHOOSE YOUR TREE", True, (0, 240, 255))
    screen.blit(title, ((w - title.get_width()) // 2, h * 0.12))

    panel_w, panel_h = 420, 200
    px = (w - panel_w) // 2
    py = int(h * 0.28)

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((20, 15, 40, 225))
    screen.blit(panel, (px, py))
    pygame.draw.rect(screen, (0, 240, 255), (px, py, panel_w, panel_h), 2, border_radius=8)

    for i, tree in enumerate(trees):
        btn_y = py + 20 + i * 75
        btn_rect = pygame.Rect(px + 20, btn_y, panel_w - 40, 60)

        selected = i == tree_idx
        color = (0, 240, 255) if selected else (160, 160, 180)
        if selected:
            pulse = 0.7 + 0.3 * math.sin(pygame.time.get_ticks() * 0.005)
            sel = pygame.Surface((btn_rect.w, btn_rect.h), pygame.SRCALPHA)
            sel.fill((*((0, 240, 255)), int(35 * pulse)))
            screen.blit(sel, (btn_rect.x, btn_rect.y))
            pygame.draw.rect(screen, (0, 240, 255), btn_rect, 2, border_radius=5)
        else:
            pygame.draw.rect(screen, (60, 60, 75), btn_rect, 1, border_radius=5)

        prefix = "> " if selected else ""
        name = font_tree.render(f"{prefix}{tree.value}", True, color)
        screen.blit(name, (btn_rect.x + 12, btn_rect.y + 6))

        desc = "Tank / Support" if tree.value == "Vanguard" else \
               "Damage / Risk" if tree.value == "Berserker" else \
               "Fire / DOT" if tree.value == "Pyromancy" else \
               "Control / Debuff" if tree.value == "Arcanist" else \
               "Single-target Burst" if tree.value == "Assassin" else \
               "Poison / Evasion"
        desc_text = font_desc.render(desc, True, (140, 140, 165))
        screen.blit(desc_text, (btn_rect.x + 12, btn_rect.y + 38))

    hint = font_hint.render("[W/S or UP/DOWN] Navigate   [ENTER] Confirm", True, (100, 100, 130))
    screen.blit(hint, ((w - hint.get_width()) // 2, py + panel_h + 14))


def _apply_trap(player, trap_type, dungeon, ach_manager):
    """Apply trap effect to player."""
    if trap_type == "dodge":
        return
    elif trap_type == "spike":
        dmg = int(player.max_hp * 0.15)
        player.current_hp = max(1, player.current_hp - dmg)
    elif trap_type == "gas":
        player.add_status("poison", "debuff", 2, {})
    elif trap_type == "collapse":
        player.add_status("stun", "debuff", 1, {})


def _buy_dungeon_shop(player, idx):
    items = [
        {"name": "Small Potion", "cost": 60, "hp": 30},
        {"name": "Large Potion", "cost": 144, "hp": 75},
    ]
    if idx < len(items):
        item = items[idx]
        if player.gold >= item["cost"]:
            player.gold -= item["cost"]
            from item import Consumable, Rarity, merge_into_stack
            potion = Consumable(item["name"], Rarity.COMMON, item["hp"])
            merge_into_stack(player.consumables, potion)


if __name__ == "__main__":
    main()
