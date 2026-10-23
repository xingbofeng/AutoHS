"""Capture Hearthstone and wait for its battlefield animations to settle."""

import time

from autohs.constants import (
    COORDINATE_BATTLEFILED_RANGE_X,
    COORDINATE_BATTLEFILED_RANGE_Y,
)
from autohs.config import BATTLEFIELD_STABLE_INTERVAL
from autohs.desktop.window_service import _darwin
from autohs.infrastructure.logging import logger


class GameWindowUnavailable(RuntimeError):
    """Hearthstone has no visible window to capture or click."""


def take_snapshot():
    import cv2
    import numpy as np

    from autohs.desktop.screen import screen_size

    width, height = screen_size()
    if _darwin():
        import mss

        from autohs.config import bind_window
        from autohs.desktop.window_service import get_HS_hwnd, get_window_pos

        rect = get_window_pos(get_HS_hwnd())
        if rect is None:
            raise GameWindowUnavailable("Hearthstone window is unavailable")
        left, top, right, bottom = map(int, rect)
        bind_window(left, top, right, bottom)
        bounds = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        with mss.mss() as sct:
            image = np.array(sct.grab(bounds))
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return cv2.resize(image, (bounds["width"], bounds["height"]))

    from autohs.desktop.windows import desktop_snapshot

    return desktop_snapshot(width, height)


def wait_battlefield_stable(autohs_config, wait_count=3, max_try=40):
    import cv2
    from skimage.metrics import structural_similarity as ssim

    last_battlefield_snapshot = None
    stable_count = 0
    start_time = 0
    end_time = 0
    deadline = time.monotonic() + 10

    for _ in range(max_try):
        if time.monotonic() >= deadline:
            break
        image = take_snapshot()
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        coordinates = autohs_config.click_coordinates
        if _darwin():
            from autohs.desktop.coordinates import scale_from_1920

            coordinates = scale_from_1920(0, 0, image.shape[1], image.shape[0])
        start_x, end_x = coordinates[COORDINATE_BATTLEFILED_RANGE_X]
        start_y, end_y = coordinates[COORDINATE_BATTLEFILED_RANGE_Y]
        current = image[start_y:end_y, start_x:end_x]
        current = cv2.resize(current, ((end_x - start_x) // 2, (end_y - start_y) // 2))

        if last_battlefield_snapshot is not None:
            start_time = time.time()
            score = ssim(current, last_battlefield_snapshot, multichannel=True, channel_axis=2)
            end_time = time.time()
            logger.debug(f"Similarity: {score}")
            if score > 0.95:
                stable_count += 1
                if stable_count >= wait_count:
                    return
            else:
                stable_count = 0

        last_battlefield_snapshot = current
        elapsed = end_time - start_time
        if elapsed < BATTLEFIELD_STABLE_INTERVAL:
            time.sleep(BATTLEFIELD_STABLE_INTERVAL - elapsed)

    logger.warning("等待战场稳定超时")
