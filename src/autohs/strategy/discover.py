"""Prefer discover results that the current runner can play."""

from autohs.behaviors.registry import ID2CARD_DICT
from autohs.catalog.lookup import query_json_get_dict


def choose_discover_index(log_state, choice):
    def score(entity_id):
        entity = log_state.entity_dict.get(entity_id)
        if entity is None or not entity.card_id:
            return -1,
        try:
            card = query_json_get_dict(entity.card_id)
        except KeyError:
            return -1,
        supported = entity.card_id in ID2CARD_DICT
        ordinary_minion = card.get("type") == "MINION" and "BATTLECRY" not in card.get("mechanics", [])
        playable = supported or ordinary_minion
        # Prefer supported results and cheap tempo; unknown gifts still get selected.
        return (int(playable), int(supported), -card.get("cost", 99))

    return max(range(len(choice["entities"])), key=lambda index: score(choice["entities"][index]))
