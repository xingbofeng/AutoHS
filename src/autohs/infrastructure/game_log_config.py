"""Windows log.config checks. Darwin returns true without reading the game log."""

from pathlib import Path

from autohs.desktop.window_service import _darwin
from autohs.infrastructure.logging import logger

_content = ""


def hearthstone_config_path():
    return Path.home() / "AppData" / "Local" / "Blizzard" / "Hearthstone" / "log.config"


def read_log_file():
    global _content
    log_path = hearthstone_config_path()
    if not log_path.exists():
        logger.error("炉石传说配置文件不存在，期望位置：%s", log_path)
        _content = "NOT_FOUND"
        return
    _content = log_path.read_text(encoding="utf-8")


def check_power_config():
    global _content
    if _darwin():
        return True
    if _content == "":
        read_log_file()
    return "Power" in _content


def check_loading_screen_config():
    global _content
    if _darwin():
        return True
    if _content == "":
        read_log_file()
    return "LoadingScreen" in _content
