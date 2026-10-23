from types import SimpleNamespace

import numpy as np
import Quartz

from autohs.desktop.macos import get_window_rect
from autohs.logs.reader import log_iter_func


def test_foreground_activates_the_running_game_before_mouse_input(monkeypatch):
    import AppKit

    from autohs.desktop import macos

    activations = []
    game = SimpleNamespace(
        activateWithOptions_=lambda flags: activations.append(flags) or True,
        bundleIdentifier=lambda: "test.game",
    )
    monkeypatch.setattr(macos, "find_running_application", lambda *args: game)
    monkeypatch.setattr(AppKit, "NSWorkspace", SimpleNamespace(sharedWorkspace=lambda: SimpleNamespace(
        URLForApplicationWithBundleIdentifier_=lambda identifier: None,
    )))

    assert macos.move_window_foreground(pid=123) is True
    assert activations == [AppKit.NSApplicationActivateIgnoringOtherApps]


def test_window_rect_ignores_small_overlay(monkeypatch):
    windows = [
        {"kCGWindowOwnerPID": 123, "kCGWindowLayer": 0,
         "kCGWindowBounds": {"X": 975, "Y": -960, "Width": 84, "Height": 77}},
        {"kCGWindowOwnerPID": 123, "kCGWindowLayer": 0,
         "kCGWindowName": "Hearthstone",
         "kCGWindowBounds": {"X": 971, "Y": -1080, "Width": 1920, "Height": 1080}},
    ]
    monkeypatch.setattr(Quartz, "CGWindowListCopyWindowInfo", lambda *args: windows)
    assert get_window_rect(123) == (971, -1080, 2891, 0)


def test_window_rect_falls_back_when_screen_listing_omits_visible_window(monkeypatch):
    windows = [
        {"kCGWindowOwnerPID": 123, "kCGWindowLayer": 0,
         "kCGWindowName": "Hearthstone", "kCGWindowAlpha": 1,
         "kCGWindowBounds": {"X": 0, "Y": 33, "Width": 1512, "Height": 949}},
    ]
    monkeypatch.setattr(
        Quartz, "CGWindowListCopyWindowInfo",
        lambda options, window_id: [] if options & Quartz.kCGWindowListOptionOnScreenOnly else windows,
    )
    assert get_window_rect(123) == (0, 33, 1512, 982)


def test_window_pid_survives_localized_process_name(monkeypatch):
    from autohs.desktop import macos

    windows = [
        {"kCGWindowOwnerPID": 55363, "kCGWindowOwnerName": "Hearthstone",
         "kCGWindowLayer": 0,
         "kCGWindowBounds": {"X": 0, "Y": 33, "Width": 1512, "Height": 949}},
    ]
    monkeypatch.setattr(Quartz, "CGWindowListCopyWindowInfo", lambda *args: windows)
    assert macos.hearthstone_window_pid() == 55363
    assert macos.find_running_application_pid("Hearthstone") == 55363


def test_log_iterator_recovers_when_first_match_creates_power_log(tmp_path):
    session = tmp_path / "Hearthstone_2026_10_22"
    session.mkdir()
    iterator = log_iter_func(str(tmp_path), "Power.log", lambda line: None)
    next(iterator)
    assert not (session / "Power.log").exists()
    (session / "Power.log").write_text("first match\n")
    assert next(iterator) is not None
    iterator.close()


def test_log_iterator_can_ignore_historical_lines_on_restart(tmp_path):
    session = tmp_path / "Hearthstone_2026_10_22"
    session.mkdir()
    log = session / "LoadingScreen.log"
    log.write_text("old scene\n")
    iterator = log_iter_func(
        str(tmp_path),
        "LoadingScreen.log",
        lambda line: line.strip(),
        start_at_end=True,
    )
    assert next(iterator).message_list == []
    with log.open("a") as handle:
        handle.write("live scene\n")
    assert next(iterator).message_list == ["live scene"]
    iterator.close()


def test_new_power_log_keeps_initial_entities_when_started_before_file_creation(tmp_path):
    session = tmp_path / "Hearthstone_new"
    session.mkdir()
    iterator = log_iter_func(str(tmp_path), "Power.log", lambda line: line.strip(), start_at_end=True)
    next(iterator)
    (session / "Power.log").write_text("CREATE_GAME\nFULL_ENTITY 39\n")
    assert next(iterator).message_list == ["CREATE_GAME", "FULL_ENTITY 39"]
    iterator.close()


def test_log_iterator_skips_historical_fatal_scene_on_restart(tmp_path):
    session = tmp_path / "Hearthstone_2026_10_22"
    session.mkdir()
    log = session / "LoadingScreen.log"
    log.write_text(
        "D 19:57:46.4289260 LoadingScreen.OnSceneLoaded() - "
        "prevMode=TOURNAMENT currMode=FATAL_ERROR\n"
    )
    iterator = log_iter_func(
        str(tmp_path),
        "LoadingScreen.log",
        lambda line: line.strip(),
        start_at_end=True,
    )
    assert next(iterator).message_list == []
    iterator.close()


def test_snapshot_captures_game_window_on_secondary_display(monkeypatch):
    import mss

    from autohs.config import autohs_config, bind_window
    from autohs.constants import COORDINATE_MID_X
    from autohs.desktop import capture, window_service

    grabbed = []
    class Screen:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def grab(self, bounds):
            grabbed.append(bounds)
            return np.zeros((2160, 3840, 4), dtype=np.uint8)

    monkeypatch.setattr(mss, "mss", Screen)
    monkeypatch.setattr(window_service, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(window_service, "get_window_pos", lambda pid: (971, -1080, 2891, 0))
    bind_window(0, 0, 1920, 1080)
    image = capture.take_snapshot()
    assert grabbed == [{"left": 971, "top": -1080, "width": 1920, "height": 1080}]
    assert image.shape == (1080, 1920, 3)
    assert autohs_config.click_coordinates[COORDINATE_MID_X] == 1931


def test_battlefield_crop_uses_window_relative_coordinates(monkeypatch):
    import skimage.metrics

    from autohs.constants import (
        COORDINATE_BATTLEFILED_RANGE_X,
        COORDINATE_BATTLEFILED_RANGE_Y,
    )
    from autohs.desktop import capture, window_service
    from autohs.desktop.coordinates import COORDINATES_1920_1080, scale_from_1920

    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    x1, x2 = COORDINATES_1920_1080[COORDINATE_BATTLEFILED_RANGE_X]
    y1, y2 = COORDINATES_1920_1080[COORDINATE_BATTLEFILED_RANGE_Y]
    image[y1:y2, x1:x2] = 255
    def compare(current, previous, **kwargs):
        assert np.all(current == 255)
        return 1

    monkeypatch.setattr(skimage.metrics, "structural_similarity", compare)
    monkeypatch.setattr(capture, "take_snapshot", lambda: image)
    monkeypatch.setattr(capture.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(window_service, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(window_service, "get_window_pos", lambda pid: (971, -1080, 2891, 0))
    config = SimpleNamespace(click_coordinates=scale_from_1920(0, 0, 1920, 1080))
    capture.wait_battlefield_stable(config, wait_count=1, max_try=2)


def test_hand_click_stays_inside_letterboxed_game_window(monkeypatch):
    from autohs.config import bind_window
    from autohs.execution.cards import CardsController

    points = []
    controller = CardsController()
    monkeypatch.setattr(controller, "mouseClickPosition", points.append)
    bind_window(0, 33, 1512, 982)

    controller.chooseHandCard(0, 8)

    rate = 1512 / 1920
    game_bottom = 33 + (949 + 1080 * rate) / 2
    assert len(points) == 1
    assert 0 <= points[0][0] <= 1512
    assert game_bottom - 90 <= points[0][1] <= game_bottom - 20


def test_mulligan_click_handles_four_visible_cards(monkeypatch):
    from autohs.config import bind_window
    from autohs.execution.cards import CardsController

    points = []
    controller = CardsController()
    monkeypatch.setattr(controller, "mouseClickPosition", points.append)
    bind_window(0, 0, 1920, 1080)

    controller.replaceStartingCard(3, 4)

    assert len(points) == 1


def test_match_end_uses_log_state_to_return_to_deck_selection(monkeypatch):
    from autohs.app import fsm

    monkeypatch.setattr(fsm, "get_state", lambda: fsm.FSM_CHOOSING_HERO)
    monkeypatch.setattr(fsm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(get_state=lambda: fsm.FSM_BATTLING))
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(game=SimpleNamespace(
        cancelClick=lambda: None, commitErrorReport=lambda: None,
    )))
    assert fsm.QuittingBattle() == fsm.FSM_CHOOSING_HERO


def test_menu_recognition_accepts_resized_game_window(monkeypatch):
    import cv2

    from autohs.desktop import capture, screen
    from autohs.vision import recognition, templates

    main_menu = np.random.default_rng(4).integers(
        0, 256, (300, 300, 3), dtype=np.uint8,
    )
    image = np.zeros((982, 1512, 3), dtype=np.uint8)
    image[323:589, 665:931] = cv2.resize(main_menu, (266, 266))
    monkeypatch.setattr(recognition, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(screen, "screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(capture, "take_snapshot", lambda: image)
    monkeypatch.setattr(templates, "images", lambda: {
        "main_menu_1080": main_menu,
        "choose_hero_1080": np.zeros((180, 180, 3), dtype=np.uint8),
        "matching_1080": np.zeros((400, 400, 3), dtype=np.uint8),
        "choose_card_1080": np.zeros((60, 320, 3), dtype=np.uint8),
    })
    assert recognition.get_state() == recognition.FSM_MAIN_MENU


def test_menu_recognition_finds_template_outside_fixed_crop(monkeypatch):
    import cv2

    from autohs.desktop import capture, screen
    from autohs.vision import recognition, templates

    main_menu = np.random.default_rng(3).integers(
        0, 256, (300, 300, 3), dtype=np.uint8,
    )
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    resized = cv2.resize(main_menu, (210, 210))
    image[100:310, 100:310] = resized
    monkeypatch.setattr(recognition, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(screen, "screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(capture, "take_snapshot", lambda: image)
    monkeypatch.setattr(templates, "images", lambda: {
        "main_menu_1080": main_menu,
        "main_menu_2k": np.zeros((600, 600, 3), dtype=np.uint8),
        "choose_hero_1080": np.zeros((180, 180, 3), dtype=np.uint8),
        "choose_hero_macos_1080": np.zeros((180, 180, 3), dtype=np.uint8),
        "choose_hero_2k": np.zeros((300, 300, 3), dtype=np.uint8),
        "matching_1080": np.zeros((400, 400, 3), dtype=np.uint8),
        "matching_2k": np.zeros((600, 600, 3), dtype=np.uint8),
        "choose_card_1080": np.zeros((60, 320, 3), dtype=np.uint8),
        "choose_card_2k": np.zeros((80, 300, 3), dtype=np.uint8),
    })
    assert recognition.get_state() == recognition.FSM_MAIN_MENU


def test_start_match_refreshes_coordinates_after_window_activation(monkeypatch):
    from autohs.app import fsm
    from autohs.config import autohs_config, bind_window
    from autohs.constants import (
        COORDINATE_MATCH_OPPONENT_X,
        COORDINATE_MATCH_OPPONENT_Y,
    )

    bind_window(0, 0, 1920, 1080)
    monkeypatch.setattr(autohs_config, "max_play_time", 0)
    monkeypatch.setattr(autohs_config, "max_win_count", 0)
    monkeypatch.setattr(fsm, "choose_hero_count", 0)
    monkeypatch.setattr(fsm, "PLATFORM", "Darwin")
    monkeypatch.setattr(fsm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        get_HS_hwnd=lambda: 123,
        get_window_pos=lambda pid: (300, 100, 2220, 1180),
    ))
    clicked = []
    def click_start():
        clicked.append((autohs_config.click_coordinates[COORDINATE_MATCH_OPPONENT_X],
                        autohs_config.click_coordinates[COORDINATE_MATCH_OPPONENT_Y]))
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(game=SimpleNamespace(
        enterHS=lambda: None, matchOpponent=click_start,
    )))
    assert fsm.ChoosingHeroAction() == fsm.FSM_MATCHING_OPPONENT
    assert clicked == [(1700, 1000)]


def test_menu_recognition_preserves_centered_board_when_aspect_ratio_changes(monkeypatch):
    import cv2

    from autohs.desktop import capture, screen
    from autohs.vision import recognition, templates

    canonical = np.random.default_rng(1).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    canonical[800:980, 1310:1490] = 255
    main_menu = np.random.default_rng(5).integers(
        0, 256, (300, 300, 3), dtype=np.uint8,
    )
    window_image = cv2.resize(canonical[:, 100:1820], (1512, 949))
    monkeypatch.setattr(recognition, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(screen, "screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(capture, "take_snapshot", lambda: window_image)
    monkeypatch.setattr(templates, "images", lambda: {
        "main_menu_1080": main_menu,
        "choose_hero_1080": np.full((180, 180, 3), 255, dtype=np.uint8),
        "matching_1080": np.full((400, 400, 3), 255, dtype=np.uint8),
        "choose_card_1080": np.full((60, 320, 3), 255, dtype=np.uint8),
    })
    assert recognition.get_state() == recognition.FSM_CHOOSING_HERO


def test_game_process_is_found_before_cocoa_registers_application(monkeypatch):
    from autohs.desktop import macos, window_service

    monkeypatch.setattr(macos, "hearthstone_window_pid", lambda: 0)
    monkeypatch.setattr(macos, "find_running_application", lambda **kwargs: None)
    monkeypatch.setattr(macos, "find_running_application_pid", lambda name: 123 if name == "Hearthstone" else 0)
    assert window_service.get_HS_hwnd() == 123


def test_game_window_pid_wins_when_process_name_is_localized(monkeypatch):
    from autohs.desktop import macos, window_service

    monkeypatch.setattr(macos, "hearthstone_window_pid", lambda: 456)
    monkeypatch.setattr(macos, "find_running_application_pid", lambda name: 0)
    monkeypatch.setattr(macos, "find_running_application", lambda **kwargs: None)
    assert window_service.get_HS_hwnd() == 456


def test_hidden_game_window_is_not_treated_as_a_capture_target(monkeypatch):
    from autohs.desktop import capture
    from autohs.vision import recognition

    def unavailable():
        raise capture.GameWindowUnavailable("Hearthstone window is unavailable")

    monkeypatch.setattr(recognition, "get_HS_hwnd", lambda: 456)
    monkeypatch.setattr(capture, "take_snapshot", unavailable)
    assert recognition.get_state() == recognition.FSM_LEAVE_HS


def test_animation_wait_does_not_consume_a_turn_when_capture_is_slow(monkeypatch):
    import skimage.metrics

    from autohs.desktop import capture
    from autohs.desktop.coordinates import scale_from_1920

    elapsed = [0]
    frames = []
    def snapshot():
        elapsed[0] += 2
        frames.append(elapsed[0])
        return np.zeros((1080, 1920, 3), dtype=np.uint8)

    monkeypatch.setattr(capture, "take_snapshot", snapshot)
    monkeypatch.setattr(capture.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(capture.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(skimage.metrics, "structural_similarity", lambda *args, **kwargs: 0)
    config = SimpleNamespace(click_coordinates=scale_from_1920(0, 0, 1920, 1080))
    capture.wait_battlefield_stable(config, max_try=40)
    assert len(frames) <= 5


def test_menu_recognition_accepts_current_start_button_style(monkeypatch):
    from autohs.desktop import capture, screen
    from autohs.vision import recognition, templates

    image = np.random.default_rng(2).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    image[800:980, 1310:1490] = 255
    main_menu = np.random.default_rng(6).integers(
        0, 256, (300, 300, 3), dtype=np.uint8,
    )
    monkeypatch.setattr(recognition, "get_HS_hwnd", lambda: 123)
    monkeypatch.setattr(screen, "screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(capture, "take_snapshot", lambda: image)
    monkeypatch.setattr(templates, "images", lambda: {
        "main_menu_1080": main_menu,
        "choose_hero_1080": np.zeros((180, 180, 3), dtype=np.uint8),
        "choose_hero_macos_1080": np.full((180, 180, 3), 255, dtype=np.uint8),
        "matching_1080": np.full((400, 400, 3), 255, dtype=np.uint8),
        "choose_card_1080": np.full((60, 320, 3), 255, dtype=np.uint8),
    })
    assert recognition.get_state() == recognition.FSM_CHOOSING_HERO


def test_click_is_visible_to_a_game_that_samples_input_on_each_frame(monkeypatch):
    import time

    import pyautogui

    from autohs.execution.mouse import MouseController

    pressed = [False]
    sampled = []
    monkeypatch.setattr(pyautogui, "moveTo", lambda *args, **kwargs: None)
    monkeypatch.setattr(pyautogui, "click", lambda *args, **kwargs: None)
    monkeypatch.setattr(pyautogui, "mouseDown", lambda *args, **kwargs: pressed.__setitem__(0, True))
    monkeypatch.setattr(pyautogui, "mouseUp", lambda *args, **kwargs: pressed.__setitem__(0, False))
    monkeypatch.setattr(time, "sleep", lambda seconds: sampled.append(pressed[0]) if seconds >= 1 / 60 else None)
    MouseController().mouseClickPosition((100, 200))
    assert any(sampled)
    assert not pressed[0]


def test_mouse_leaves_a_failsafe_corner_before_clicking(monkeypatch):
    import pyautogui

    from autohs.execution.mouse import MouseController

    moves = []
    monkeypatch.setattr(pyautogui, "FAILSAFE", True)
    monkeypatch.setattr(pyautogui, "position", lambda: (1511, 0))
    monkeypatch.setattr(pyautogui, "size", lambda: (1512, 982))
    def move(x, y=None, **kwargs):
        moves.append((x, y) if y is not None else tuple(x))

    monkeypatch.setattr(pyautogui, "moveTo", move)
    monkeypatch.setattr(pyautogui, "mouseDown", lambda *args, **kwargs: None)
    monkeypatch.setattr(pyautogui, "mouseUp", lambda *args, **kwargs: None)
    MouseController().mouseClickPosition((1292, 487))
    assert moves == [(756, 491), (1292, 487)]
    assert pyautogui.FAILSAFE is True


def test_mouse_drag_samples_a_stable_held_position_before_release(monkeypatch):
    import sys
    import time

    import pyautogui

    from autohs.execution.mouse import MouseController

    events = []
    pressed = [False]
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(pyautogui, "moveTo", lambda position, **kwargs: events.append(("move", tuple(position), pressed[0])))
    monkeypatch.setattr(pyautogui, "mouseDown", lambda *args, **kwargs: (pressed.__setitem__(0, True), events.append(("down", pressed[0]))))
    monkeypatch.setattr(pyautogui, "mouseUp", lambda *args, **kwargs: (events.append(("up", pressed[0])), pressed.__setitem__(0, False)))
    monkeypatch.setattr(time, "sleep", lambda seconds: events.append(("sleep", seconds, pressed[0])))

    MouseController().mouseDragToPosition((640, 480))

    assert [(event[0], event[1]) for event in events] == [
        ("down", True),
        ("move", (640, 480)),
        ("sleep", 0.12),
        ("up", True),
    ]


def test_untargeted_spell_is_cast_by_clicking_board_instead_of_dragging(monkeypatch):
    from autohs.config import bind_window
    from autohs.execution.cards import CardsController

    bind_window(0, 0, 1920, 1080)
    clicks = []
    controller = CardsController()
    monkeypatch.setattr(controller, "chooseHandCard", lambda *args: clicks.append(("select", args)))
    monkeypatch.setattr(controller, "mouseClickPosition", lambda point: clicks.append(("click", point)))
    monkeypatch.setattr(controller, "mouseDragToPosition", lambda point: clicks.append(("drag", point)))

    controller.selectAndUseHandCard(0, 10)

    assert clicks == [
        ("select", (0, 10)),
        ("click", [960, 500]),
    ]


def test_battle_does_not_play_a_card_after_game_ends_during_animation_wait(monkeypatch):
    from autohs.app import fsm

    state = SimpleNamespace(is_end=False, is_my_turn=True, game_num_turns_in_play=3, pending_choice=None,
                            my_entity=SimpleNamespace(query_tag=lambda tag: "LOST"))
    actions = []
    strategy = SimpleNamespace(
        debug_print_out=lambda: None,
        get_best_location_trigger=lambda: (-1, []),
        best_h_index_arg=lambda: (0, []),
        use_best_entity=lambda *args: actions.append(args),
    )
    monkeypatch.setattr(fsm, "log_state", state)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "update_log_state", lambda: True)
    monkeypatch.setattr(fsm, "StrategyState", lambda state: strategy)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        wait_battlefield_stable=lambda *args: setattr(state, "is_end", True),
    ))
    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert actions == []
