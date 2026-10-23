from types import SimpleNamespace

from autohs.behaviors.basic import Card, Location, SpellCard
from autohs.behaviors.registry import ID2CARD_DICT


def test_tavern_brawl_cards_have_strategy_behaviors():
    card_ids = [
        "GDB_473",
        "END_007",
        "GDB_119",
        "TLC_902",
        "FIR_902",
        "TIME_020t2",
        "VAC_929",
        "TIME_449",
    ]
    for card_id in card_ids:
        assert card_id in ID2CARD_DICT
        card = ID2CARD_DICT[card_id]
        assert issubclass(card, Card)
        if card_id == "VAC_929":
            assert issubclass(card, Location)
        else:
            assert issubclass(card, SpellCard)


def test_cliffside_waits_when_the_board_has_no_room_for_both_pirates():
    card = ID2CARD_DICT["VAC_929"]
    state = SimpleNamespace(my_minion_num=6, oppo_minions=[])
    assert card.location_trigger_h_and_arg(state, 0) == (0,)


def test_cliffside_triggers_and_clears_selection(monkeypatch):
    from autohs.behaviors import tavern_brawl

    events = []
    controls = SimpleNamespace(
        minion=SimpleNamespace(
            chooseMyMinion=lambda *args: events.append(("minion", *args)),
        ),
        game=SimpleNamespace(cancelClick=lambda: events.append(("cancel",))),
    )
    monkeypatch.setattr(tavern_brawl, "clicks", lambda: controls)
    monkeypatch.setattr(Card, "finish_action", classmethod(lambda cls: None))

    state = SimpleNamespace(my_minion_num=2)
    ID2CARD_DICT["VAC_929"].location_trigger(state, 1, [])

    assert events == [("minion", 1, 2), ("cancel",)]
