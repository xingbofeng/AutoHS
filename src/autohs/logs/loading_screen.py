import re

from autohs.constants import *
from autohs.logs.events import LineInfoContainer

# D 18:45:52.0292623 LoadingScreen.OnSceneLoaded() - prevMode=COLLECTIONMANAGER currMode=HUB
MODE_CHANGE_PATTERN = re.compile(r"D [\d]{2}:[\d]{2}:[\d]{2}.[\d]{7} LoadingScreen.OnSceneLoaded\(\) - prevMode=(.*) currMode=(.*)")

def parse_line_loading_screen(line_str):
    match_obj = MODE_CHANGE_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_MODE_CHANGE,
            prev_mode=match_obj.group(1),
            curr_mode=match_obj.group(2)
        )

    return None
