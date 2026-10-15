"""旧导入路径。实现在 autohs.paths.install。"""

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from autohs.paths.install import (
    BATTLENET_APP,
    HEARTHSTONE_ROOT,
    app_search_dirs,
    bundle_name,
    darwin_install_root,
    darwin_install_status,
    hearthstone_app,
    hearthstone_log_dir,
    matching_app_paths,
)

__all__ = [
    "BATTLENET_APP",
    "HEARTHSTONE_ROOT",
    "app_search_dirs",
    "bundle_name",
    "darwin_install_root",
    "darwin_install_status",
    "hearthstone_app",
    "hearthstone_log_dir",
    "matching_app_paths",
]
