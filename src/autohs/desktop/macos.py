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

    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        if proc.info["name"] == app_name:
            return proc.info["pid"]
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

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    for window in windows:
        window_pid = int(window["kCGWindowOwnerPID"])
        if not window_pid == pid:
            continue
        bounds = window.get("kCGWindowBounds")
        left = bounds["X"]
        top = bounds["Y"]
        right = left + bounds["Width"]
        bottom = top + bounds["Height"]
        return left, top, right, bottom
