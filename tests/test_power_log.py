from autohs.logs.power import parse_line
from autohs.logs.state import LogState, update_state


def feed(log, message):
    event = parse_line("D 13:30:00.0000000 " + message)
    assert event is not None, message
    update_state(log, event)


def test_full_entity_updating_creates_hidden_card_before_show_entity():
    log = LogState()

    feed(
        log,
        "GameState.DebugPrintPower() - FULL_ENTITY - Updating "
        "[entityName=UNKNOWN ENTITY [cardType=INVALID] id=43 zone=DECK "
        "zonePos=0 cardId= player=2] CardID=",
    )
    feed(
        log,
        "GameState.DebugPrintPower() - SHOW_ENTITY - Updating "
        "Entity=[entityName=UNKNOWN ENTITY [cardType=INVALID] id=43 zone=DECK "
        "zonePos=0 cardId= player=2] CardID=VAC_938",
    )

    assert log.entity_dict["43"].card_id == "VAC_938"


def test_full_entity_creating_still_creates_card():
    log = LogState()

    feed(
        log,
        "GameState.DebugPrintPower() - FULL_ENTITY - Creating ID=89 CardID=EX1_538t",
    )

    assert log.entity_dict["89"].card_id == "EX1_538t"


def test_show_entity_without_its_full_entity_does_not_abort_replay():
    log = LogState()

    feed(
        log,
        "GameState.DebugPrintPower() - SHOW_ENTITY - Updating "
        "Entity=[entityName=UNKNOWN ENTITY [cardType=INVALID] id=31 zone=DECK "
        "zonePos=0 cardId= player=1] CardID=VAC_933",
    )

    assert log.entity_dict["31"].card_id == "VAC_933"


def test_equipped_mining_axe_has_one_durability_after_its_first_attack():
    from autohs.logs.state import CardEntity
    from autohs.strategy.entities import generate_strategy_entity

    log = LogState()
    log.my_player_id = "1"
    weapon = CardEntity("DEEP_014")
    for tag, value in {
        "CARDTYPE": "WEAPON", "CONTROLLER": "1", "ZONE": "PLAY",
        "ATK": "1", "HEALTH": "2", "DAMAGE": "1",
    }.items():
        weapon.set_tag(tag, value)

    result = generate_strategy_entity(weapon, log)

    assert result.health == 1
    assert result.heuristic_val == 1


def test_legacy_weapon_durability_tag_still_works():
    from autohs.logs.state import CardEntity
    from autohs.strategy.entities import generate_strategy_entity

    log = LogState()
    weapon = CardEntity("DEEP_014")
    for tag, value in {"CARDTYPE": "WEAPON", "DURABILITY": "2", "DAMAGE": "1"}.items():
        weapon.set_tag(tag, value)

    assert generate_strategy_entity(weapon, log).health == 1
