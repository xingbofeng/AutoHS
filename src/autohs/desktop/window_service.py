"""Find Hearthstone and Battle.net, and move or stop those processes."""

import platform

from autohs.infrastructure.logging import logger


def _darwin():
    return platform.system() == "Darwin"


def get_HS_hwnd():
    app_names = ["Hearthstone", "炉石传说", "《爐石戰記》"]
    hwnd = 0
    if _darwin():
        from autohs.desktop import macos

        hwnd = macos.hearthstone_window_pid()
        if hwnd:
            return hwnd
        for app_name in app_names:
            hwnd = macos.find_running_application_pid(app_name)
            if hwnd:
                return hwnd
        for app_name in app_names:
            app = macos.find_running_application(app_name=app_name)
            if not app:
                continue
            hwnd = app.processIdentifier()
        return hwnd
    from autohs.desktop.windows import find_window

    for app_name in app_names:
        hwnd = find_window(app_name)
        if hwnd:
            break
    return hwnd


def get_battlenet_hwnd():
    if _darwin():
        from autohs.desktop import macos

        app = macos.find_running_application(app_name="战网")
        if not app:
            return 0
        return app.processIdentifier()
    from autohs.desktop.windows import find_window

    return find_window("战网") or 0


def test_hs_available():
    return get_HS_hwnd() != 0


def test_battlenet_available():
    return get_battlenet_hwnd() != 0


def move_window_foreground(hwnd, name=""):
    if _darwin():
        from autohs.desktop import macos

        macos.move_window_foreground(app_name=name, pid=hwnd)
        return
    from autohs.desktop.windows import bring_to_front

    try:
        bring_to_front(hwnd)
    except Exception as exc:
        if name != "":
            logger.warning(f"Open {name}: {exc}")
        else:
            logger.warning(exc)


def terminate_HS():
    hwnd = get_HS_hwnd()
    if hwnd == 0:
        return
    if _darwin():
        import os
        import signal

        try:
            os.kill(hwnd, signal.SIGTERM)
        except Exception as exc:
            logger.warning(f"终止炉石传说进程失败: {exc}")
        return
    from autohs.desktop.windows import terminate_process

    terminate_process(hwnd)


def get_window_pos(battlenet_hwnd):
    if _darwin():
        from autohs.desktop import macos

        return macos.get_window_rect(battlenet_hwnd)
    from autohs.desktop.windows import window_rect

    return window_rect(battlenet_hwnd)
