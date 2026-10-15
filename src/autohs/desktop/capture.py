"""Grab the frontmost screen. mss, pyautogui, and cv2 load when a function runs."""

import time

from autohs.constants import (
    COORDINATE_BATTLEFILED_RANGE_X,
    COORDINATE_BATTLEFILED_RANGE_Y,
)
from autohs.desktop.window_service import _darwin
from autohs.infrastructure.logging import logger


def take_snapshot():
    import cv2
    import numpy as np
    import pyautogui
    from autohs.desktop.screen import screen_size

    width, height = screen_size()
    if _darwin():
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = pyautogui.screenshot(
                region=(monitor["left"], monitor["top"], monitor["width"], monitor["height"])
            )
        image = np.array(screenshot)
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    from autohs.desktop.windows import desktop_snapshot

    return desktop_snapshot(width, height)


def wait_battlefield_stable(autohs_config, wait_count=3, max_try=40):
    import cv2
    from skimage.metrics import structural_similarity as ssim

    last_battlefield_snapshot = None
    stable_count = 0
    start_time = 0
    end_time = 0

    for _ in range(max_try):
        image = take_snapshot()
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        start_x = autohs_config.click_coordinates[COORDINATE_BATTLEFILED_RANGE_X][0]
        end_x = autohs_config.click_coordinates[COORDINATE_BATTLEFILED_RANGE_X][1]
        start_y = autohs_config.click_coordinates[COORDINATE_BATTLEFILED_RANGE_Y][0]
        end_y = autohs_config.click_coordinates[COORDINATE_BATTLEFILED_RANGE_Y][1]
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
        if end_time - start_time < 0.3:
            time.sleep(0.3 - (end_time - start_time))

    logger.warning("等待战场稳定超时")
