"""Eight screen templates. cv2.imread runs on the first images() call."""

from pathlib import Path

from autohs.paths.root import repo_root

_IMAGES = None
_NAMES = (
    "choose_card_2k",
    "choose_hero_2k",
    "matching_2k",
    "main_menu_2k",
    "choose_card_1080",
    "choose_hero_1080",
    "matching_1080",
    "main_menu_1080",
)


def template_dir():
    packaged = Path(__file__).resolve().parents[1] / "assets" / "templates"
    if (packaged / "main_menu_1080.png").is_file():
        return packaged
    return repo_root() / "figs"


def images():
    global _IMAGES
    if _IMAGES is None:
        import cv2

        folder = template_dir()
        _IMAGES = {name: cv2.imread(str(folder / f"{name}.png")) for name in _NAMES}
    return _IMAGES
