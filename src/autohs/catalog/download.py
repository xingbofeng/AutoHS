"""Explicit hearthstonejson download. Nothing imports this at startup."""

import requests

CARDS_URL = "https://api.hearthstonejson.com/v1/latest/zhCN/cards.json"


def download_cards_json(path):
    response = requests.get(CARDS_URL, timeout=60)
    response.raise_for_status()
    with open(path, "wb") as handle:
        handle.write(response.content)
