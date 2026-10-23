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


def _template_score(image, template):
    import cv2

    if template is None:
        return 0
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if template.ndim == 3:
        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    height, width = image.shape[:2]
    best = 0
    # The game window can be resized independently from the desktop resolution.
    for scale in (
        0.7, 0.72, 0.74, 0.76, 0.78, 0.8, 0.82, 0.84, 0.86, 0.88,
        0.885, 0.89, 0.9, 0.92, 0.94, 0.96, 0.98, 1.0, 1.05, 1.1,
        1.2, 1.3, 1.4,
    ):
        resized = cv2.resize(template, None, fx=scale, fy=scale)
        if resized.shape[0] > height or resized.shape[1] > width:
            continue
        result = cv2.matchTemplate(
            image,
            resized,
            cv2.TM_CCOEFF_NORMED,
        )
        best = max(best, float(result.max()))
    return best


def _choose_hero_score(image, templates):
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    best = 0
    for template in (
        templates.get("choose_hero_1080"),
        templates.get("choose_hero_macos_1080"),
    ):
        if template is None:
            continue
        if template.ndim == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        best = max(best, _template_score(gray, template))
    return best


def _crop(image, crop):
    if isinstance(crop, tuple) and len(crop) == 4:
        x1, x2, y1, y2 = crop
        return image[y1:y2, x1:x2]
    return crop


def _crop_score(image, crop, template):
    import cv2

    return float(cv2.matchTemplate(
        cv2.cvtColor(_crop(image, crop), cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(template, cv2.COLOR_BGR2GRAY),
        cv2.TM_CCOEFF_NORMED,
    ).max())


def get_state():
    import cv2

    from autohs.desktop.capture import GameWindowUnavailable, take_snapshot
    from autohs.desktop.screen import screen_size
    from autohs.vision.templates import images

    hwnd = get_HS_hwnd()
    if hwnd == 0:
        return FSM_LEAVE_HS

    try:
        image = take_snapshot()
    except GameWindowUnavailable:
        return FSM_LEAVE_HS
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    templates = images()
    width, height = screen_size()
    choose_hero_score = _choose_hero_score(image, templates)
    full_frame_image = image
    if image.shape[:2] != (height, width):
        scaled_width = round(image.shape[1] * height / image.shape[0])
        image = cv2.resize(image, (scaled_width, height))
        if scaled_width < width:
            left = (width - scaled_width) // 2
            image = cv2.copyMakeBorder(image, 0, 0, left, width - scaled_width - left,
                                       cv2.BORDER_CONSTANT, value=0)
        elif scaled_width > width:
            left = (scaled_width - width) // 2
            image = image[:, left:left + width]
    if width == 2560:
        parts = {
            "main_menu": ((980, 1580, 300, 900), templates["main_menu_2k"]),
            "choose_hero": ((1710, 2010, 1040, 1340), templates["choose_hero_2k"]),
            "matching": ((980, 1580, 400, 1000), templates["matching_2k"]),
            "choose_card": ((1130, 1430, 170, 250), templates["choose_card_2k"]),
        }
    elif width == 1920:
        parts = {
            "main_menu": ((820, 1100, 310, 590), templates["main_menu_1080"]),
            "choose_hero": ((1310, 1490, 800, 980), templates["choose_hero_1080"]),
            "matching": ((780, 1160, 310, 690), templates["matching_1080"]),
            "choose_card": ((810, 1110, 140, 180), templates["choose_card_1080"]),
        }
    else:
        # Window captures keep their own aspect ratio; do not use desktop
        # dimensions to decide whether the game is in combat.
        parts = {
            "main_menu": (image, templates["main_menu_1080"]),
            "choose_hero": (image, templates["choose_hero_1080"]),
            "matching": (image, templates["matching_1080"]),
            "choose_card": (image, templates["choose_card_1080"]),
        }

    scores = {
        name: _crop_score(image, crop, template)
        for name, (crop, template) in parts.items()
    }
    # A resized macOS window can move these UI elements outside the fixed
    # 1080p crops. Search the whole frame at several scales as a fallback.
    def best_template_score(template_names):
        return max(
            _template_score(full_frame_image, templates[name])
            for name in template_names
            if name in templates
        )

    full_frame_scores = {
        "main_menu": best_template_score(("main_menu_1080", "main_menu_2k")),
        "choose_hero": choose_hero_score,
        "matching": best_template_score(("matching_1080", "matching_2k")),
        "choose_card": best_template_score(("choose_card_1080", "choose_card_2k")),
    }
    scores = {
        name: max(scores[name], full_frame_scores[name])
        for name in scores
    }
    logger.debug(
        "Similarity: main_menu: {main_menu}, choose_hero: {choose_hero}, matching: {matching}, choose_card: {choose_card}".format(
            **scores
        )
    )
    if scores["main_menu"] > (
        0.65 if full_frame_image.shape[:2] != (height, width) else 0.8
    ):
        return FSM_MAIN_MENU
    if scores["choose_hero"] > 0.85:
        return FSM_CHOOSING_HERO
    if scores["matching"] > 0.75:
        return FSM_MATCHING_OPPONENT
    if scores["choose_card"] > 0.9:
        return FSM_CHOOSING_CARD
    return FSM_BATTLING
