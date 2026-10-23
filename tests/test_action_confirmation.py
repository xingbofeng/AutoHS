from types import SimpleNamespace

import pytest

from autohs.app.action_confirmation import ActionConfirmation
from autohs.logs.state import Entity


@pytest.fixture
def capture():
    return ActionConfirmation.capture


def entity(**tags):
    result = Entity()
    result.tag_dict.update(CONTROLLER="1", ZONE="PLAY", ZONE_POSITION="1")
    result.tag_dict.update(tags)
    return result


@pytest.fixture
def log():
    return SimpleNamespace(
        entity_dict={},
        my_player_id="1",
        game_entity_id="1",
        game_num_turns_in_play=3,
        is_my_turn=True,
        is_end=False,
    )


@pytest.mark.parametrize("zone", ["PLAY", "GRAVEYARD", "SECRET", "DECK"])
def test_card_is_confirmed_only_when_the_original_entity_leaves_hand(
    capture, log, zone
):
    card = entity(CARDTYPE="SPELL")
    card.set_tag("ZONE", "HAND")
    log.entity_dict["10"] = card
    attempt = capture(log, SimpleNamespace(), "card", 0)
    assert attempt.entity_id == "10"
    assert not attempt.confirmed(log)
    card.set_tag("ZONE", zone)
    assert attempt.confirmed(log)


@pytest.mark.parametrize(
    "tag,value",
    [
        ("NUM_ATTACKS_THIS_TURN", "1"),
        ("EXHAUSTED", "1"),
    ],
)
@pytest.mark.parametrize("index,cardtype", [(0, "MINION"), (-1, "HERO")])
def test_attack_requires_the_attacker_to_attack_or_exhaust(
    capture, log, tag, value, index, cardtype
):
    actor = entity(CARDTYPE=cardtype, NUM_ATTACKS_THIS_TURN="0", EXHAUSTED="0")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", index)
    actor.set_tag(tag, value)
    assert attempt.confirmed(log)


@pytest.mark.parametrize(
    "tag,value",
    [
        ("HEALTH", "2"),
        ("DURABILITY", "2"),
        ("DAMAGE", "1"),
        ("EXHAUSTED", "1"),
        ("COOLDOWN", "2"),
        ("LOCATION_COOLDOWN", "2"),
    ],
)
def test_location_confirms_consumed_durability_or_cooldown(capture, log, tag, value):
    actor = entity(
        CARDTYPE="LOCATION", HEALTH="3", DURABILITY="3", DAMAGE="0", EXHAUSTED="0"
    )
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "location", 0)
    actor.set_tag(tag, value)
    assert attempt.confirmed(log)


def test_hero_power_uses_its_own_exhaustion(capture, log):
    actor = entity(CARDTYPE="HERO_POWER", EXHAUSTED="0")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "card", -1)
    actor.set_tag("EXHAUSTED", "1")
    assert attempt.confirmed(log)


@pytest.mark.parametrize(
    "action,cardtype,index",
    [
        ("card", "SPELL", 0),
        ("attack", "MINION", 0),
        ("attack", "HERO", -1),
        ("location", "LOCATION", 0),
        ("card", "HERO_POWER", -1),
    ],
)
def test_unrelated_updates_are_not_confirmation(capture, log, action, cardtype, index):
    actor = entity(CARDTYPE=cardtype, EXHAUSTED="0", NUM_ATTACKS_THIS_TURN="0")
    if action == "card" and index == 0:
        actor.set_tag("ZONE", "HAND")
    log.entity_dict["10"] = actor
    log.entity_dict["11"] = entity(CARDTYPE="MINION", ZONE_POSITION="2")
    attempt = capture(log, SimpleNamespace(), action, index)
    actor.set_tag("ATK", "99")
    actor.set_tag("ZONE_POSITION", "3")
    log.entity_dict["11"].set_tag("EXHAUSTED", "1")
    log.entity_dict["11"].set_tag("NUM_ATTACKS_THIS_TURN", "1")
    assert not attempt.confirmed(log)


def test_shifted_hand_indices_do_not_confirm_a_different_card(capture, log):
    first = entity(CARDTYPE="SPELL")
    first.set_tag("ZONE", "HAND")
    second = entity(CARDTYPE="SPELL")
    second.tag_dict.update(ZONE="HAND", ZONE_POSITION="2")
    log.entity_dict.update({"10": first, "11": second})
    attempt = capture(log, SimpleNamespace(), "card", 1)
    first.set_tag("ZONE", "GRAVEYARD")
    second.set_tag("ZONE_POSITION", "1")
    assert not attempt.confirmed(log)
    second.set_tag("ZONE", "GRAVEYARD")
    assert attempt.confirmed(log)


def test_removed_entity_is_not_evidence_of_execution(capture, log):
    actor = entity(CARDTYPE="MINION")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    del log.entity_dict["10"]
    assert not attempt.confirmed(log)


@pytest.mark.parametrize("change", ["turn", "opponent", "game", "log", "end"])
def test_changes_in_game_context_cannot_confirm_the_old_action(capture, log, change):
    actor = entity(CARDTYPE="MINION", EXHAUSTED="0")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    actor.set_tag("EXHAUSTED", "1")
    if change == "turn":
        log.game_num_turns_in_play += 2
    elif change == "opponent":
        log.is_my_turn = False
    elif change == "game":
        log.game_entity_id = "100"
    elif change == "end":
        log.is_end = True
    else:
        log = SimpleNamespace(**vars(log))
    assert not attempt.confirmed(log)


def test_missing_optional_tags_do_not_block_a_logged_attack(capture, log):
    actor = entity(CARDTYPE="MINION")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    actor.set_tag("NUM_ATTACKS_THIS_TURN", "1")
    assert attempt.confirmed(log)


@pytest.mark.parametrize("zone", ["HAND", "GRAVEYARD"])
def test_attack_is_confirmed_when_the_attacker_leaves_play(capture, log, zone):
    actor = entity(CARDTYPE="MINION", EXHAUSTED="0", NUM_ATTACKS_THIS_TURN="0")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", 0)

    actor.set_tag("ZONE", zone)

    assert attempt.confirmed(log)


def test_sorted_board_includes_locations_and_ignores_opponent_entities(capture, log):
    log.entity_dict["10"] = entity(CARDTYPE="MINION", CONTROLLER="2")
    log.entity_dict["11"] = entity(CARDTYPE="MINION", ZONE_POSITION="2")
    log.entity_dict["12"] = entity(CARDTYPE="LOCATION")
    attempt = capture(log, SimpleNamespace(), "attack", 1)
    assert attempt.entity_id == "11"


@pytest.mark.parametrize("index", [-2, 1, 99])
def test_invalid_indices_are_not_reinterpreted_as_another_actor(capture, log, index):
    log.entity_dict["10"] = entity(CARDTYPE="MINION")
    assert capture(log, SimpleNamespace(), "attack", index) is None


def test_strategy_metadata_detects_a_stale_hand_snapshot(capture, log):
    actor = entity(CARDTYPE="SPELL")
    actor.card_id = "NEW_CARD"
    actor.set_tag("ZONE", "HAND")
    log.entity_dict["10"] = actor
    strategy = SimpleNamespace(
        my_hand_cards=[SimpleNamespace(card_id="OLD_CARD", zone_pos=1)]
    )
    assert capture(log, strategy, "card", 0) is None


@pytest.mark.parametrize(
    "change", ["new_hand_card", "target_replaced", "board_reordered"]
)
def test_input_is_stale_when_card_or_target_geometry_changes(capture, log, change):
    log.entity_dict["10"] = entity(CARDTYPE="MINION")
    target = entity(CARDTYPE="MINION", CONTROLLER="2")
    log.entity_dict["11"] = target
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    assert attempt.current(log)
    if change == "new_hand_card":
        log.entity_dict["12"] = entity(CARDTYPE="SPELL", ZONE="HAND")
    elif change == "target_replaced":
        target.set_tag("ZONE", "GRAVEYARD")
        log.entity_dict["12"] = entity(CARDTYPE="MINION", CONTROLLER="2")
    else:
        target.set_tag("ZONE_POSITION", "2")
    assert not attempt.current(log)


def test_a_choice_opening_before_input_invalidates_the_battlefield_target(capture, log):
    log.entity_dict["10"] = entity(CARDTYPE="MINION")
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    log.pending_choice = {"choice_id": "5"}
    assert not attempt.current(log)


@pytest.mark.parametrize("action", ["attack", "card", "location"])
@pytest.mark.parametrize(
    "tag,value",
    [
        ("ATK", "4"),
        ("HEALTH", "5"),
        ("DAMAGE", "1"),
        ("TAUNT", "1"),
        ("IMMUNE", "1"),
        ("DIVINE_SHIELD", "1"),
        ("STEALTH", "1"),
        ("ARMOR", "4"),
        ("POISONOUS", "1"),
        ("SPELLPOWER", "2"),
        ("DORMANT", "1"),
        ("UNTOUCHABLE", "1"),
        ("CANT_BE_TARGETED_BY_SPELLS", "1"),
        ("CANT_BE_TARGETED_BY_HERO_POWERS", "1"),
    ],
)
def test_visible_combat_changes_invalidate_the_decision_without_confirming_it(
    capture, log, action, tag, value
):
    actor = entity(CARDTYPE="LOCATION" if action == "location" else "MINION")
    if action == "card":
        actor.tag_dict.update(CARDTYPE="SPELL", ZONE="HAND")
    target = entity(CARDTYPE="MINION", CONTROLLER="2", ATK="2", HEALTH="3")
    log.entity_dict.update({"10": actor, "11": target})
    attempt = capture(log, SimpleNamespace(), action, 0)
    assert attempt.current(log)

    target.set_tag(tag, value)

    assert not attempt.current(log)
    assert not attempt.confirmed(log)


@pytest.mark.parametrize("changed_entity", ["actor", "target"])
@pytest.mark.parametrize("tag", ["TIMESTAMP", "LAST_MODIFIED", "DEBUG_SEQUENCE"])
def test_unrelated_metadata_does_not_invalidate_or_confirm_a_decision(
    capture, log, changed_entity, tag
):
    actor = entity(CARDTYPE="MINION")
    target = entity(CARDTYPE="MINION", CONTROLLER="2")
    log.entity_dict.update({"10": actor, "11": target})
    attempt = capture(log, SimpleNamespace(), "attack", 0)

    changed = actor if changed_entity == "actor" else target
    changed.set_tag(tag, "2026-10-23T14:00:00")

    assert attempt.current(log)
    assert not attempt.confirmed(log)


@pytest.mark.parametrize(
    "zone,controller", [("DECK", "2"), ("GRAVEYARD", "1"), ("HAND", "2")]
)
def test_nonvisible_combat_changes_do_not_invalidate_a_decision(
    capture, log, zone, controller
):
    log.entity_dict["10"] = entity(CARDTYPE="MINION")
    hidden = entity(CARDTYPE="MINION", ZONE=zone, CONTROLLER=controller)
    log.entity_dict["11"] = hidden
    attempt = capture(log, SimpleNamespace(), "attack", 0)

    hidden.set_tag("ATK", "5")

    assert attempt.current(log)


def test_an_absent_combat_tag_becoming_explicitly_zero_is_not_a_change(capture, log):
    log.entity_dict["10"] = entity(CARDTYPE="MINION")
    attempt = capture(log, SimpleNamespace(), "attack", 0)

    log.entity_dict["10"].set_tag("TAUNT", "0")

    assert attempt.current(log)


@pytest.mark.parametrize(
    "tag,before,after",
    [
        ("NUM_ATTACKS_THIS_TURN", "2", "1"),
        ("EXHAUSTED", "1", "0"),
    ],
)
def test_attack_resets_do_not_confirm_an_action(capture, log, tag, before, after):
    actor = entity(CARDTYPE="MINION", **{tag: before})
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), "attack", 0)
    actor.set_tag(tag, after)
    assert not attempt.confirmed(log)


@pytest.mark.parametrize(
    "action,index,cardtype,tag,value",
    [
        ("card", 0, "SPELL", "ZONE", "GRAVEYARD"),
        ("attack", 0, "MINION", "NUM_ATTACKS_THIS_TURN", "1"),
        ("location", 0, "LOCATION", "DAMAGE", "1"),
        ("card", -1, "HERO_POWER", "EXHAUSTED", "1"),
    ],
)
def test_confirmation_accepts_real_parsed_power_tag_changes(
    capture, log, action, index, cardtype, tag, value
):
    from autohs.logs.power import parse_line
    from autohs.logs.state import update_state

    actor = entity(CARDTYPE=cardtype)
    if action == "card" and index == 0:
        actor.set_tag("ZONE", "HAND")
    log.entity_dict["10"] = actor
    attempt = capture(log, SimpleNamespace(), action, index)
    event = parse_line(
        "D 13:30:00.0000000 GameState.DebugPrintPower() - "
        f"TAG_CHANGE Entity=10 tag={tag} value={value} "
    )
    assert event is not None
    update_state(log, event)
    assert attempt.confirmed(log)


@pytest.mark.parametrize(
    "tag,value", [("RESOURCES", "2"), ("RESOURCES_USED", "1"), ("TEMP_RESOURCES", "1")]
)
def test_player_mana_changes_invalidate_a_card_decision(capture, log, tag, value):
    player = Entity()
    player.tag_dict.update(
        CARDTYPE="PLAYER", RESOURCES="3", RESOURCES_USED="0", TEMP_RESOURCES="0"
    )
    card = entity(CARDTYPE="SPELL", ZONE="HAND", COST="3")
    log.my_entity_id = "2"
    log.entity_dict.update({"2": player, "10": card})
    attempt = capture(log, SimpleNamespace(), "card", 0)
    assert attempt.current(log)
    player.set_tag(tag, value)
    assert not attempt.current(log)
    assert not attempt.confirmed(log)


def test_final_location_activation_is_confirmed_after_damage_resets(capture, log):
    from autohs.logs.power import parse_line

    card = entity(CARDTYPE='LOCATION', HEALTH='3', DAMAGE='2', EXHAUSTED='0',
                  LOCATION_ACTION_COOLDOWN='0')
    log.entity_dict['10'] = card
    attempt = capture(log, SimpleNamespace(), 'location', 0)
    for tag, value in [('DAMAGE','3'), ('ZONE_POSITION','0'), ('ZONE','GRAVEYARD'),
                       ('DAMAGE','0'), ('LOCATION_ACTION_COOLDOWN','1'), ('DAMAGE','1')]:
        event = parse_line(f'D 14:33:24.2944050 GameState.DebugPrintPower() - TAG_CHANGE Entity=10 tag={tag} value={value} ')
        card.set_tag(event.info_dict['tag'], event.info_dict['value'])
    assert attempt.confirmed(log)


def test_actual_location_cooldown_change_invalidates_a_pending_click(capture, log):
    card = entity(CARDTYPE='LOCATION', EXHAUSTED='0', LOCATION_ACTION_COOLDOWN='0')
    log.entity_dict['10'] = card
    attempt = capture(log, SimpleNamespace(), 'location', 0)
    card.set_tag('LOCATION_ACTION_COOLDOWN', '1')
    assert not attempt.current(log)
    assert attempt.confirmed(log)


def test_location_disappearance_alone_does_not_confirm_activation(capture, log):
    card = entity(CARDTYPE='LOCATION', HEALTH='3', DAMAGE='2', EXHAUSTED='0',
                  LOCATION_ACTION_COOLDOWN='0')
    log.entity_dict['10'] = card
    attempt = capture(log, SimpleNamespace(), 'location', 0)
    card.set_tag('ZONE', 'GRAVEYARD')
    card.set_tag('DAMAGE', '0')
    assert not attempt.confirmed(log)
