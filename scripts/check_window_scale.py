"""Check window scaling without reading the screen or clicking."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from autohs.constants import COORDINATE_END_TURN_X, COORDINATE_END_TURN_Y, COORDINATE_HALF_MINION_GAP_X
from autohs.desktop.coordinates import COORDINATES_1920_1080, point_inside, scale_from_1920


def fail(message):
    print(message)
    raise SystemExit(1)


same = scale_from_1920(0, 0, 1920, 1080)
if same != COORDINATES_1920_1080:
    fail("1920x1080 window at origin did not reproduce the base table")

wide = scale_from_1920(100, 40, 2000, 1000)
end_x = wide[COORDINATE_END_TURN_X]
end_y = wide[COORDINATE_END_TURN_Y]
if not point_inside(end_x, end_y, 100, 40, 2100, 1040):
    fail(f"end turn point {(end_x, end_y)} fell outside the window")
if wide[COORDINATE_HALF_MINION_GAP_X] != int(70 * 1000 / 1080):
    fail("minion gap was shifted instead of scaled")

banned = ("tkinter", "cv2", "AppKit", "Quartz", "pyautogui", "mss", "requests")
hits = sorted(name for name in sys.modules if name.split(".")[0] in banned)
if hits:
    fail("imported " + ",".join(hits))

print("window_scale=ok")
print(f"sample_end_turn={end_x},{end_y}")
