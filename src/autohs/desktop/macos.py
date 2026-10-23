"""Darwin window helpers. AppKit, Quartz, and psutil load inside each function."""

from autohs.paths.install import matching_app_paths


def get_installed_application(app_name):
    import AppKit

    for full_path in matching_app_paths(app_name):
        bundle = AppKit.NSBundle.bundleWithPath_(full_path)
        if not bundle:
            continue
        return bundle
    return None


def find_running_application_pid(app_name=None, pid=None):
    import psutil

    if app_name == "Hearthstone":
        window_pid = hearthstone_window_pid()
        if window_pid:
            return window_pid

    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == app_name:
            return proc.info["pid"]
    return 0


def hearthstone_window_pid():
    """Use the game's visible window when process names are localized."""
    import Quartz

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    for window in windows:
        bounds = window.get("kCGWindowBounds", {})
        if window.get("kCGWindowLayer", 0) != 0:
            continue
        if bounds.get("Width", 0) < 640 or bounds.get("Height", 0) < 480:
            continue
        owner = str(window.get("kCGWindowOwnerName", "")).lower()
        title = str(window.get("kCGWindowName", "")).lower()
        if "hearthstone" in owner or "hearthstone" in title:
            return int(window["kCGWindowOwnerPID"])
    return 0


def run_event_loop_briefly(duration=0.01, iterations=5):
    import CoreFoundation

    for _ in range(iterations):
        CoreFoundation.CFRunLoopRunInMode(
            CoreFoundation.kCFRunLoopDefaultMode,
            duration,
            False,
        )


def find_running_application(app_name=None, pid=None):
    import AppKit
    import Quartz

    workspace = Quartz.NSWorkspace.sharedWorkspace()
    run_event_loop_briefly()

    for app in workspace.runningApplications():
        if pid and app.processIdentifier() == pid:
            return app
        if app_name and app.localizedName() == app_name:
            return app
        try:
            bundle_url = app.bundleURL()
            if bundle_url:
                bundle_path = bundle_url.path()
                bundle = AppKit.NSBundle.bundleWithPath_(bundle_path)
                if bundle:
                    bundle_name = bundle.infoDictionary().get("CFBundleName", "")
                    if app_name and bundle_name == app_name:
                        return app
        except Exception as exc:
            print(f"Error accessing bundle info for {app.localizedName()}: {exc}")
            continue
    return None


def move_window_foreground(app_name=None, pid=None):
    import AppKit

    if app_name in ["战网"]:
        app_name = "Battle.net"
    elif app_name in ["炉石传说"]:
        app_name = "Hearthstone"
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    application = find_running_application(app_name, pid)
    if application and application.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps):
        return True
    if not application:
        application = get_installed_application(app_name)
    bundle_identifier = application.bundleIdentifier()
    url = workspace.URLForApplicationWithBundleIdentifier_(bundle_identifier)

    if url:
        workspace.openURLs_withAppBundleIdentifier_options_additionalEventParamDescriptor_launchIdentifiers_(
            [url], bundle_identifier, 0, None, None
        )


def get_window_rect(pid):
    import Quartz

    if not pid:
        return None
    candidates = []
    for options in (
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGWindowListOptionAll,
    ):
        windows = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
        candidates = [
            window for window in windows
            if int(window["kCGWindowOwnerPID"]) == pid
            and window.get("kCGWindowLayer", 0) == 0
            and window.get("kCGWindowIsOnscreen") is not False
            and window.get("kCGWindowAlpha", 1) > 0
            and window.get("kCGWindowBounds", {}).get("Width", 0) >= 640
            and window.get("kCGWindowBounds", {}).get("Height", 0) >= 480
        ]
        if candidates:
            break
    if not candidates:
        return None
    window = max(candidates, key=lambda item: (
        item.get("kCGWindowName") == "Hearthstone",
        item["kCGWindowBounds"]["Width"] * item["kCGWindowBounds"]["Height"],
    ))
    bounds = window["kCGWindowBounds"]
    left, top = bounds["X"], bounds["Y"]
    return left, top, left + bounds["Width"], top + bounds["Height"]
