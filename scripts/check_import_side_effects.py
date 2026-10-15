"""Import the reorganized package without downloading cards or touching the game."""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import autohs
import autohs.app.bootstrap
import autohs.app.fsm
import autohs.behaviors.registry
import autohs.catalog.lookup
import autohs.desktop.capture
import autohs.desktop.macos
import autohs.desktop.window_service
import autohs.execution.controller as execution_controller
import autohs.logs.loading_screen
import autohs.logs.power
import autohs.logs.reader
import autohs.logs.state
import autohs.strategy.state
import autohs.vision.recognition
import autohs.vision.templates
from autohs.behaviors.registry import ID2CARD_DICT
from autohs.config import autohs_config, bind_screen, live_click_coordinates
from autohs.constants import COORDINATE_MID_X, LOG_CONTAINER_ERROR, LOG_LINE_CREATE_GAME, LOG_LINE_MODE_CHANGE
from autohs.desktop.coordinates import COORDINATES_1920_1080
from autohs.logs.loading_screen import parse_line_loading_screen
from autohs.logs.power import parse_line
from autohs.logs.reader import log_iter_func


def fail(message):
    print(message)
    raise SystemExit(1)


banned = ("tkinter", "cv2", "AppKit", "Quartz", "pyautogui", "mss", "requests", "psutil", "win32gui")
hits = sorted(name for name in sys.modules if name.split(".")[0] in banned)
if hits:
    fail("imported " + ",".join(hits))
if "autohs.catalog.download" in sys.modules:
    fail("catalog download module loaded")
if os.path.isdir(os.path.join(ROOT, "autohs_log")) or os.path.isdir(os.path.join(ROOT, "utils", "autohs_log")):
    fail("created autohs_log")
for relative in ("cards.json", "utils/cards.json", "src/autohs/catalog/cards.json"):
    if os.path.exists(os.path.join(ROOT, relative)):
        fail("created " + relative)
if autohs_config.click_coordinates is not None:
    fail("coordinates bound at import")
if len(ID2CARD_DICT) != 69:
    fail("ID2CARD_DICT has " + str(len(ID2CARD_DICT)) + " keys")

created = parse_line("D 04:23:18.0000001 GameState.DebugPrintPower() - CREATE_GAME")
if created is None or created.line_type != LOG_LINE_CREATE_GAME:
    fail("parse_line missed CREATE_GAME")
mode = parse_line_loading_screen(
    "D 18:45:52.0292623 LoadingScreen.OnSceneLoaded() - prevMode=HUB currMode=GAMEPLAY"
)
if mode is None or mode.line_type != LOG_LINE_MODE_CHANGE or mode.info_dict.get("curr_mode") != "GAMEPLAY":
    fail("parse_line_loading_screen missed mode change")

missing = next(log_iter_func(os.path.join(ROOT, "missing-hearthstone-logs"), "Power.log", parse_line))
if missing.log_type != LOG_CONTAINER_ERROR:
    fail("missing log directory was not reported")
if os.path.exists(os.path.join(ROOT, "missing-hearthstone-logs")):
    fail("log reader created a directory")

with tempfile.TemporaryDirectory() as temp_dir:
    session = os.path.join(temp_dir, "Hearthstone_2026_10_16_00_00_00")
    os.makedirs(session)
    empty = next(log_iter_func(temp_dir, "Power.log", parse_line))
    if empty.log_type != LOG_CONTAINER_ERROR:
        fail("missing Power.log was not reported")
    if os.path.exists(os.path.join(session, "Power.log")):
        fail("log reader created an empty Power.log")

bind_screen(1920, 1080)
if live_click_coordinates[COORDINATE_MID_X] != COORDINATES_1920_1080[COORDINATE_MID_X]:
    fail("live coordinates mismatch")
bind_screen(3024, 1964)
if autohs_config.click_coordinates is not None:
    fail("unexpected coordinates")
try:
    live_click_coordinates[COORDINATE_MID_X]
except RuntimeError:
    pass
else:
    fail("unbound coordinates did not raise")

print("import_side_effects=ok")
print("autohs_file=" + autohs.__file__)
print("controller_type=" + type(execution_controller.controller).__name__)
print("handwritten_keys=" + str(len(ID2CARD_DICT)))
print("fsm_module=" + autohs.app.fsm.__name__)
