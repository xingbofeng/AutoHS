from types import SimpleNamespace

import pytest

from autohs.behaviors.registry import ID2CARD_DICT
from autohs.logs.power import parse_line
from autohs.logs.state import CardEntity, LogState, PlayerEntity, update_state
from autohs.strategy.entities import StrategyHeroPower, StrategyMinion
from autohs.strategy.state import StrategyState


def minion(card_id="FP1_001", attack=2, exhausted=0, **kwargs):
    return StrategyMinion(card_id, "PLAY", 1, 1, 0, True, False,
                          attack, 3, exhausted=exhausted, **kwargs)


def board(minions=(), enemies=(), hand=(), corpses=0):
    return SimpleNamespace(
        my_minions=list(minions), oppo_minions=list(enemies),
        my_minion_num=len(minions), oppo_minion_num=len(enemies),
        my_hand_cards=list(hand), my_hand_card_num=len(hand),
        my_corpses=corpses, my_remaining_mana=7,
        my_hero_power=SimpleNamespace(exhausted=False),
        my_hero=SimpleNamespace(health=30),
        oppo_hero=SimpleNamespace(health=30, armor=0, immune=False), oppo_has_taunt=False,
    )


def behavior(card_id):
    result = ID2CARD_DICT.get(card_id)
    assert result is not None, f"Missing behavior for {card_id}"
    return result


def test_deck_has_behavior_for_every_battlecry_and_spell():
    for card_id in ("HERO_11bp", "EDR_811", "RLK_958", "CORE_RLK_116",
                    "TTN_454", "DEEP_017", "RLK_708", "CORE_RLK_087",
                    "RLK_707", "LOE_047", "END_004", "GVG_110"):
        behavior(card_id)


def test_death_knight_hero_power_is_recognized():
    power = StrategyHeroPower("HERO_11bp", "PLAY", 0, 2, 0, True, False, 0)
    assert power.detail_hero_power is not None


def test_ghoul_power_does_not_summon_into_full_board():
    power = behavior("HERO_11bp")
    assert power.best_h_and_arg(board([minion()] * 7), -1)[0] == 0
    assert power.best_h_and_arg(board(), -1)[0] > 0


def test_skeletal_sidekick_targets_ready_undead_not_beast():
    hand = [minion("RLK_958")]
    state = board([minion("LOOT_413", attack=9), minion(exhausted=1), minion()], hand=hand)
    score, gap, target = behavior("RLK_958").best_h_and_arg(state, 0)
    assert score > 0
    assert (gap, target) == (3, 2)


def test_skeletal_sidekick_without_undead_can_play_without_target(monkeypatch):
    from autohs.behaviors import death_knight

    events = []
    controls = SimpleNamespace(
        cards=SimpleNamespace(putMinionOnBattleGround=lambda *a: events.append("play")),
        minion=SimpleNamespace(chooseMyMinion=lambda *a: events.append("target")),
        game=SimpleNamespace(cancelClick=lambda: None),
    )
    monkeypatch.setattr(death_knight, "clicks", lambda: controls)
    monkeypatch.setattr(death_knight.time, "sleep", lambda _: None)
    card = behavior("RLK_958")
    state = board([minion("LOOT_413")], hand=[minion("RLK_958")])
    score, *args = card.best_h_and_arg(state, 0)
    assert score > 0
    card.use_with_arg(state, 0, *args)
    assert events == ["play"]


def test_grave_strength_waits_for_ready_attackers():
    card = behavior("RLK_707")
    assert card.best_h_and_arg(board([minion(exhausted=1)] * 4, corpses=5), 0)[0] == 0
    assert card.best_h_and_arg(board(), 0)[0] == 0


def test_grave_strength_spends_corpses_for_lethal_with_one_attacker():
    card = behavior("RLK_707")
    state = board([minion(attack=2)], corpses=5)
    state.oppo_hero.health = 5
    assert card.best_h_and_arg(state, 0)[0] >= 1000
    state.my_corpses = 4
    assert card.best_h_and_arg(state, 0)[0] < 1000


def test_mining_casualties_is_not_played_into_full_board():
    card = behavior("DEEP_017")
    assert card.best_h_and_arg(board([minion()] * 7), 0)[0] == 0
    assert card.best_h_and_arg(board([minion()] * 5), 0)[0] > 0


def test_asphyxiate_waits_for_enemy_minion():
    card = behavior("CORE_RLK_087")
    assert card.best_h_and_arg(board(), 0)[0] == 0
    assert card.best_h_and_arg(board(enemies=[minion(attack=8)]), 0)[0] > 0


def test_down_with_the_ship_can_target_enemy_hero_for_lethal():
    state = board()
    state.oppo_hero.health = 3
    score, target = behavior("TTN_454").best_h_and_arg(state, 0)
    assert score >= 1000
    assert target == -1


def test_damage_spell_does_not_claim_lethal_through_armor():
    state = board()
    state.oppo_hero.health = 3
    state.oppo_hero.armor = 10
    assert behavior("TTN_454").best_h_and_arg(state, 0)[0] < 1000


def test_damage_spell_does_not_target_immune_hero_without_other_targets():
    state = board()
    state.oppo_hero.immune = True
    assert behavior("TTN_454").best_h_and_arg(state, 0)[0] == 0


def test_grave_strength_does_not_claim_lethal_through_armor():
    state = board([minion(attack=2)], corpses=5)
    state.oppo_hero.health = 5
    state.oppo_hero.armor = 10
    assert behavior("RLK_707").best_h_and_arg(state, 0)[0] < 1000


def test_strategy_reads_current_corpses_instead_of_graveyard_size():
    log = LogState()
    log.my_player_id = "1"
    player = PlayerEntity()
    player.set_tag("CORPSES", "5")
    log.add_player_entity("2", "1", player)
    assert StrategyState(log).my_corpses == 5


def feed(log, message):
    event = parse_line("D 13:30:00.0000000 " + message)
    assert event is not None, message
    update_state(log, event)


def choice_log():
    log = LogState()
    log.my_player_id = "1"
    source = CardEntity("EDR_811")
    source.set_tag("CONTROLLER", "1")
    log.add_entity("10", source)
    return log


def announce_choice(log, choice_id=3, owner=1):
    feed(log, f"GameState.DebugPrintEntityChoices() - id={choice_id} Player=Player TaskList=205 ChoiceType=GENERAL CountMin=1 CountMax=1")
    feed(log, f"GameState.DebugPrintEntityChoices() -   Source=[entityName=Card id=10 zone=PLAY zonePos=0 cardId=EDR_811 player={owner}]")
    for index in range(3):
        feed(log, f"GameState.DebugPrintEntityChoices() -   Entities[{index}]=[entityName=Card id={90+index} zone=SETASIDE zonePos=0 cardId=FP1_001 player={owner}]")


def test_discover_waits_for_visible_choices_then_clears_after_selection():
    log = choice_log()
    announce_choice(log)
    assert log.pending_choice is None
    feed(log, "ChoiceCardMgr.WaitThenShowChoices() - id=3 BEGIN")
    assert log.pending_choice["entities"] == ["90", "91", "92"]
    feed(log, "GameState.DebugPrintEntitiesChosen() - id=3 Player=Player EntitiesCount=1")
    assert log.pending_choice is None


def test_opponent_discover_is_never_clicked():
    log = choice_log()
    announce_choice(log, owner=2)
    feed(log, "ChoiceCardMgr.WaitThenShowChoices() - id=3 BEGIN")
    assert log.pending_choice is None


def test_discover_prefers_playable_minion_to_unsupported_spell():
    from autohs.strategy.discover import choose_discover_index

    log = choice_log()
    for entity_id, card_id in (("90", "CS2_029"), ("91", "FP1_001"), ("92", "RLK_958")):
        log.add_entity(entity_id, CardEntity(card_id))
    assert choose_discover_index(log, {"entities": ["90", "91", "92"]}) == 2


def test_battle_resolves_discover_before_playing_or_attacking(monkeypatch):
    from autohs.app import fsm

    log = choice_log()
    announce_choice(log)
    feed(log, "ChoiceCardMgr.WaitThenShowChoices() - id=3 BEGIN")
    # Real LogState with only the lifecycle properties needed by this FSM branch.
    from autohs.logs.state import GameEntity

    game = GameEntity()
    game.set_tag("STATE", "RUNNING")
    log.set_game_entity("1", game)
    player = PlayerEntity()
    player.set_tag("CURRENT_PLAYER", "1")
    log.add_player_entity("2", "1", player)
    actions = []
    def select(index, count):
        actions.append((index, count))
        monkeypatch.setattr(fsm, "quitting_flag", True)
    monkeypatch.setattr(fsm, "log_state", log)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "update_log_state", lambda: True)
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(cards=SimpleNamespace(chooseScreenCard=select)))
    monkeypatch.setattr(fsm.time, "sleep", lambda _: None)
    fsm.Battling()
    assert actions == [(0, 3)]


@pytest.mark.parametrize("count", [2, 3, 4])
def test_discover_click_positions_respect_window_binding(monkeypatch, count):
    from autohs.config import bind_window
    from autohs.execution.cards import CardsController

    points = []
    controller = CardsController()
    monkeypatch.setattr(controller, "mouseClickPosition", points.append)
    bind_window(971, -1080, 2891, 0)
    controller.chooseScreenCard(0, count)
    assert len(points) == 1
    assert 971 < points[0][0] < 2891
    assert -1080 < points[0][1] < 0
