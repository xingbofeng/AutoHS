import os
import plistlib

HEARTHSTONE_ROOT = "/Volumes/Jiahao-500G/games/Hearthstone"
BATTLENET_APP = "/Volumes/Jiahao-500G/games/Battle.net.app"


def hearthstone_app(root):
    return os.path.join(root, "Hearthstone.app")


def hearthstone_log_dir(root):
    return os.path.join(root, "Logs")


def darwin_install_root(path):
    return path or HEARTHSTONE_ROOT


def darwin_install_status(path):
    root = darwin_install_root(path)
    app = hearthstone_app(root)
    logs = hearthstone_log_dir(root)
    if not os.path.isdir(app):
        return False, f"未找到炉石传说应用程序包: {app}"
    if not os.path.isdir(logs):
        return False, f"未找到炉石传说日志文件夹: {logs}"
    return True, ""


def app_search_dirs():
    return [
        "/Applications",
        os.path.dirname(BATTLENET_APP),
        HEARTHSTONE_ROOT,
    ]


def bundle_name(app_path):
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(plist_path, "rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return ""
    return info.get("CFBundleName") or info.get("CFBundleDisplayName") or ""


def matching_app_paths(app_name):
    found = []
    for directory in app_search_dirs():
        if not os.path.isdir(directory):
            continue
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            if not name.endswith(".app"):
                continue
            full_path = os.path.join(directory, name)
            stem = name[:-4]
            if app_name == stem or app_name == bundle_name(full_path):
                found.append(full_path)
    return found
