"""In-memory card catalog. The first lookup reads a local file and does not download."""

from datetime import datetime

from autohs.catalog.storage import default_catalog_path, read_catalog


class CardCatalog:
    """Names, races, and spell schools from hearthstonejson."""

    def __init__(self):
        self.cards = None
        self.last_modified = None
        self.path = None

    def load(self, path=None):
        self.path = path or default_catalog_path()
        self.cards, self.last_modified = read_catalog(self.path)
        return self.cards

    def download_and_load(self, path=None):
        from autohs.catalog.download import download_cards_json

        self.path = path or default_catalog_path()
        download_cards_json(self.path)
        return self.load(self.path)

    def _require(self):
        if self.cards is None:
            self.load()
        return self.cards

    def get(self, key):
        if key == "":
            return []
        cards = self._require()
        if key not in cards:
            raise KeyError(key)
        return cards[key]


catalog = CardCatalog()


def query_json_get_dict(key):
    return catalog.get(key)


def query_json_get_name(key):
    if key == "":
        return "Unknown"
    return catalog.get(key).get("name", "Unknown")


def query_json_get_races(key):
    return catalog.get(key).get("races", [])


def query_json_get_spell_school(key):
    return catalog.get(key).get("spellSchool", "None")


def catalog_last_modified():
    path = default_catalog_path()
    if not path.is_file():
        return "未加载"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
