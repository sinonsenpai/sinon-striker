"""
Main entry point for SINON STRIKER — turn-based battle RPG.
Handles title screen, hub town, dungeon runs, and battle loop via state management.
"""
import sys
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


class GameState(Enum):
    TITLE = auto()
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


def _handle_room(player, dungeon, dungeon_ui, snd):
    """Process the current dungeon room and return next state or None."""
    room = dungeon.current
    if not room:
        return GameState.HUB

    rtype = room["type"]

    if rtype == RoomType.COMBAT or rtype == RoomType.ELITE:
        # Create enemy and go to battle
        enemy_data = ENEMY_POOL.get(room["enemy"], ENEMY_POOL["slime"])
        enemy = Enemy(enemy_data["name"], enemy_data["hp"], enemy_data["atk"], enemy_data["defn"], enemy_data.get("xp_reward", 0))
        combat = CombatManager(player, enemy, snd)
        return ("battle", combat)

    elif rtype == RoomType.LOOT:
        item = LootGenerator.generate()
        return ("loot", item)

    elif rtype == RoomType.REST:
        heal = int(player.max_hp * 0.3)
        player.current_hp = min(player.max_hp, player.current_hp + heal)
        dungeon.mark_cleared()
        return "rest"

    elif rtype == RoomType.SHOP:
        # Shop is handled in-room via key presses
        return "shop"

    elif rtype == RoomType.EXIT:
        bonus = dungeon.floor * 20 + dungeon.room_index * 10
        player.gold += bonus
        dungeon.total_gold += bonus
        dungeon.mark_cleared()
        return "complete"

    return None


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SINON STRIKER")
    clock = pygame.time.Clock()

    snd = SoundManager()
    snd.init()
    snd.play_title_music()

    state = GameState.TITLE
    title_screen = TitleScreen(screen)
    hub_screen = None
    dungeon_run = None
    dungeon_ui = DungeonUI(screen)
    player = None

    combat = None
    ui = None
    god_mode = False

    # Loot display temp state
    loot_item = None
    dungeon_sub = ""  # "loot", "rest", "complete", "death", "shop"

    running = True
    while running:
        dt_ms = clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
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
                        title_screen.confirm()
                    _trigger_title_burst(title_screen, event)

                # ── HUB ────────────────────────────────────────────
                elif state == GameState.HUB and hub_screen is not None:
                    sub = hub_screen.sub_state
                    if sub == HubSubState.MAIN:
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            hub_screen.move_left()
                        elif event.key in (pygame.K_RIGHT, pygame.K_d):
                            hub_screen.move_right()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            result = hub_screen.confirm()
                            if result == "battle":
                                pass  # handled in update
                        elif event.key == pygame.K_ESCAPE:
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
                            hub_screen.cancel()

                    elif sub == HubSubState.APOTHECARY:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            hub_screen.shop_move_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            hub_screen.shop_move_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            hub_screen.shop_buy()
                        elif event.key == pygame.K_ESCAPE:
                            hub_screen.cancel()

                    elif sub == HubSubState.RETURN_PROMPT:
                        if event.key == pygame.K_y:
                            result = hub_screen.confirm_return()
                            if result == "title":
                                title_screen.start_fade_in()
                                snd.play_title_music()
                                state = GameState.TITLE
                        elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                            hub_screen.decline_return()

                    elif sub == HubSubState.TOAST:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                            hub_screen.cancel()

                # ── DUNGEON (floor select) ────────────────────────
                elif state == GameState.DUNGEON:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        dungeon_run = DungeonRun(player)
                        dungeon_ui.set_run(dungeon_run)
                        dungeon_sub = ""
                        loot_item = None
                        state = GameState.DUNGEON_ROOM
                    elif event.key == pygame.K_ESCAPE:
                        state = GameState.HUB

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
                        result = _handle_room(player, dungeon_run, dungeon_ui, snd)
                        if result == "rest":
                            dungeon_sub = "rest"
                        elif result == "shop":
                            dungeon_sub = "shop"
                        elif result == "complete":
                            dungeon_sub = "complete"
                        elif isinstance(result, tuple) and result[0] == "battle":
                            combat = result[1]
                            combat.in_dungeon = True
                            ui = BattleUI(screen)
                            god_mode = False
                            dungeon_sub = ""
                            snd.start_battle_music()
                            state = GameState.BATTLE
                        elif isinstance(result, tuple) and result[0] == "loot":
                            loot_item = result[1]
                            dungeon_sub = "loot"
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
                                dungeon_ui.chest_opened = True
                                dungeon_ui.chest_anim_timer = 300
                                dungeon_ui._spawn_chest_sparks()
                                snd.play("loot_drop")
                            else:
                                # Take item and advance
                                if loot_item:
                                    if isinstance(loot_item, Consumable):
                                        merge_into_stack(player.consumables, loot_item)
                                    else:
                                        player.inventory.append(loot_item)
                                    loot_item = None
                                dungeon_run.mark_cleared()
                                dungeon_ui.reset_chest()
                                dungeon_sub = ""
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "rest":
                        # Advance past rest room
                        if dungeon_run.current and dungeon_run.current["cleared"]:
                            dungeon_sub = ""
                    elif event.key == pygame.K_ESCAPE and dungeon_sub == "complete":
                        pass
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "complete":
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        state = GameState.HUB
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and dungeon_sub == "death":
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
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
                                snd.play("victory")
                            else:
                                # No level-up, exit battle
                                snd.stop_battle_music()
                                if dungeon_run is not None:
                                    dungeon_run.enemies_defeated += 1
                                    dungeon_run.total_gold += combat._gold_dropped
                                    dungeon_run.mark_cleared()
                                    dungeon_sub = ""
                                    snd.play_hub_music()
                                    state = GameState.DUNGEON_ROOM
                                else:
                                    hub_screen.start_fade_in()
                                    snd.play_hub_music()
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
                            combat.cancel_sub_menu()

                    elif combat.state == TurnState.ITEM_SELECT:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            combat.move_sub_up()
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            combat.move_sub_down()
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            combat.confirm_sub_action()
                        elif event.key in (pygame.K_ESCAPE, pygame.K_b):
                            combat.cancel_sub_menu()

        # ── State updates ─────────────────────────────────────────
        if state == GameState.TITLE:
            title_screen.update(dt_ms)
            if title_screen.fade_done:
                player = Character("Hero", max_hp=100, atk=15, defn=5)
                hub_screen = HubScreen(screen, player)
                hub_screen.start_fade_in()
                snd.play_hub_music()
                state = GameState.HUB

        elif state == GameState.HUB and hub_screen is not None:
            hub_screen.update(dt_ms)
            if hub_screen.fade_done:
                state = GameState.DUNGEON

        elif state == GameState.DUNGEON:
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
                        hub_screen.start_fade_in()
                        snd.play_hub_music()
                        state = GameState.HUB

        elif state == GameState.BATTLE and combat is not None:
            if god_mode:
                player.current_hp = player.max_hp
            combat.update(dt_ms)

        # ── Rendering ─────────────────────────────────────────────
        if state == GameState.TITLE:
            title_screen.draw(dt_ms)

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
            elif dungeon_sub == "complete":
                dungeon_ui.draw_run_complete()
            elif dungeon_sub == "death":
                dungeon_ui.draw_death()
            else:
                dungeon_ui.draw_room()
                if dungeon_run.room_cleared:
                    dungeon_ui.draw_room_cleared()

        elif state == GameState.BATTLE and combat is not None and ui is not None:
            ui.draw(combat, dt_ms)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


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
