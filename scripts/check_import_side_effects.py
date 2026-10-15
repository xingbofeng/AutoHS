"""Import the config, coordinate, logger, and controller modules without side effects."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import autohs
import utils.autohs_logger
import constants.pixel_coordinate
import config
import controller
from constants.pixel_coordinate import COORDINATES_1920_1080
from constants.state_and_key import COORDINATE_MID_X


def fail(message):
    print(message)
    raise SystemExit(1)


banned = ("tkinter", "cv2", "AppKit", "Quartz", "pyautogui", "mss", "requests")
hits = sorted(name for name in sys.modules if name.split(".")[0] in banned)
if hits:
    fail("imported " + ",".join(hits))
if os.path.isdir(os.path.join(ROOT, "utils", "autohs_log")):
    fail("created utils/autohs_log")
if os.path.exists(os.path.join(ROOT, "utils", "cards.json")):
    fail("created utils/cards.json")
if config.autohs_config.click_coordinates is not None:
    fail("coordinates bound at import")
if "controller.base.game" in sys.modules or "utils.window_utils" in sys.modules:
    fail("controller import loaded desktop modules")

config.bind_screen(1920, 1080)
if config.live_click_coordinates[COORDINATE_MID_X] != COORDINATES_1920_1080[COORDINATE_MID_X]:
    fail("live coordinates mismatch")
config.bind_screen(3024, 1964)
if config.autohs_config.click_coordinates is not None:
    fail("unexpected coordinates")
try:
    config.live_click_coordinates[COORDINATE_MID_X]
except RuntimeError:
    pass
else:
    fail("unbound coordinates did not raise")

print("import_side_effects=ok")
print("autohs_file=" + autohs.__file__)
print("controller_type=" + type(controller.controller).__name__)
