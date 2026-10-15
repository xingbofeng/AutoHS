"""Read a local hearthstonejson cards file. Import does not download."""

import json
from datetime import datetime
from pathlib import Path

from autohs.paths.root import repo_root


def default_catalog_path():
    root = repo_root()
    preferred = root / "cards.json"
    legacy = root / "utils" / "cards.json"
    if preferred.is_file():
        return preferred
    if legacy.is_file():
        return legacy
    return preferred


def read_catalog(path):
    path = Path(path)
    with path.open("r", encoding="utf8") as handle:
        payload = json.load(handle)
    cards = {item["id"]: item for item in payload}
    modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return cards, modified
