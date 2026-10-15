"""Compare a snapshot with the menu templates."""

from autohs.constants import (
    FSM_BATTLING,
    FSM_CHOOSING_CARD,
    FSM_CHOOSING_HERO,
    FSM_LEAVE_HS,
    FSM_MAIN_MENU,
    FSM_MATCHING_OPPONENT,
)
from autohs.desktop.window_service import get_HS_hwnd
from autohs.infrastructure.logging import logger


def max_diff(img, pixel_list):
    answer = 0
    for pair in pixel_list:
        diff = abs(int(img[pair[0]][pair[1]][1]) - int(img[pair[0]][pair[1]][0]))
        answer = max(answer, diff)
    return answer


def get_state():
    import cv2
    from skimage.metrics import structural_similarity as ssim

    from autohs.desktop.capture import take_snapshot
    from autohs.desktop.screen import screen_size
    from autohs.vision.templates import images

    hwnd = get_HS_hwnd()
    if hwnd == 0:
        return FSM_LEAVE_HS

    image = take_snapshot()
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    templates = images()
    width, _height = screen_size()
    if width == 2560:
        parts = {
            "main_menu": (image[300:900, 980:1580], templates["main_menu_2k"]),
            "choose_hero": (image[1040:1340, 1710:2010], templates["choose_hero_2k"]),
            "matching": (image[400:1000, 980:1580], templates["matching_2k"]),
            "choose_card": (image[170:250, 1130:1430], templates["choose_card_2k"]),
        }
    elif width == 1920:
        parts = {
            "main_menu": (image[300:600, 810:1110], templates["main_menu_1080"]),
            "choose_hero": (image[800:980, 1310:1490], templates["choose_hero_1080"]),
            "matching": (image[300:700, 770:1170], templates["matching_1080"]),
            "choose_card": (image[130:190, 800:1120], templates["choose_card_1080"]),
        }
    else:
        logger.error("Unsupported resolution")
        return FSM_BATTLING

    scores = {
        name: ssim(crop, template, multichannel=True, channel_axis=2)
        for name, (crop, template) in parts.items()
    }
    logger.debug(
        "Similarity: main_menu: {main_menu}, choose_hero: {choose_hero}, matching: {matching}, choose_card: {choose_card}".format(
            **scores
        )
    )
    if scores["main_menu"] > 0.8:
        return FSM_MAIN_MENU
    if scores["choose_hero"] > 0.85:
        return FSM_CHOOSING_HERO
    if scores["matching"] > 0.75:
        return FSM_MATCHING_OPPONENT
    if scores["choose_card"] > 0.9:
        return FSM_CHOOSING_CARD
    return FSM_BATTLING
