"""Print the Darwin install paths without starting Hearthstone or tailing logs."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from autohs.paths.install import (
    BATTLENET_APP,
    HEARTHSTONE_ROOT,
    darwin_install_status,
    hearthstone_app,
    hearthstone_log_dir,
    matching_app_paths,
)


def main():
    log_dir = hearthstone_log_dir(HEARTHSTONE_ROOT)
    app = hearthstone_app(HEARTHSTONE_ROOT)
    ok, message = darwin_install_status(HEARTHSTONE_ROOT)
    hearthstone_matches = matching_app_paths("Hearthstone")
    battlenet_matches = matching_app_paths("Battle.net")
    print(f"log_dir={log_dir}")
    print(f"app={app}")
    print(f"app_exists={os.path.isdir(app)}")
    print(f"logs_exists={os.path.isdir(log_dir)}")
    print(f"darwin_ok={ok}")
    if message:
        print(f"message={message}")
    print("hearthstone_matches=" + ",".join(hearthstone_matches))
    print("battlenet_matches=" + ",".join(battlenet_matches))
    print(f"battlenet_app={BATTLENET_APP}")
    if not ok:
        return 1
    if not hearthstone_matches or HEARTHSTONE_ROOT not in hearthstone_matches[0]:
        return 1
    if BATTLENET_APP not in battlenet_matches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
