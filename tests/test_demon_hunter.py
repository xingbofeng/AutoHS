from types import SimpleNamespace

from autohs.behaviors.registry import ID2CARD_DICT
from autohs.constants import CARD_MINION, CARD_SPELL
from autohs.strategy.entities import StrategyHeroPower
from autohs.strategy.state import StrategyState


def board(enemies=(), weapon=None):
    return SimpleNamespace(
        my_hero_power=SimpleNamespace(exhausted=False, current_cost=1),
        my_hero=SimpleNamespace(can_attack=False, exhausted=0, attack=0, health=30),
        my_weapon=weapon,
        my_minions=[],
        my_total_spell_power=0,
        oppo_minions=list(enemies),
        oppo_minion_num=len(enemies),
        oppo_hero=SimpleNamespace(
            health=30,
            armor=0,
            immune=False,
            can_be_pointed_by_spell=True,
            can_be_pointed_by_minion=True,
            delta_h_after_damage=lambda damage: min(damage, 30),
        ),
        oppo_has_taunt=False,
        my_remaining_mana=10,
        num_voidtouched_attendant_on_board=0,
    )


def enemy(health=4):
    return SimpleNamespace(
        health=health,
        attack=1,
        can_beat_face=False,
        divine_shield=False,
        immune=False,
        dormant=False,
        can_be_pointed_by_spell=True,
        delta_h_after_damage=lambda damage: health - max(0, health - damage),
    )


def behavior(card_id):
    result = ID2CARD_DICT.get(card_id)
    assert result is not None, f"Missing behavior for {card_id}"
    return result


def test_demon_hunter_deck_cards_have_behaviors():
    for card_id in (
        "HERO_10bp", "HERO_10bp2",
        "YOP_001", "CORE_YOP_001",
        "BT_491", "CORE_BT_491",
        "BT_035", "CORE_BT_035",
        "BT_801", "CORE_BT_801",
        "BT_921", "CORE_BT_921",
        "EX1_506", "CORE_EX1_506",
        "BT_416", "CORE_BT_416",
        "BT_480", "CORE_BT_480",
        "CATA_EVENT_000",
        "BT_187", "CORE_BT_187",
        "BT_351", "CORE_BT_351",
        "GIL_534", "CORE_GIL_534",
        "CS3_020",
        "CS2_200", "Core_CS2_200",
        "EX1_028", "CORE_EX1_028", "VAN_EX1_028",
    ):
        behavior(card_id)


def test_demon_hunter_hero_powers_are_recognized_by_id_and_name(monkeypatch):
    for card_id in ("HERO_10bp", "HERO_10bp2"):
        power = StrategyHeroPower(card_id, "PLAY", 0, 1, 0, True, False, 0)
        assert power.detail_hero_power is behavior(card_id)

    monkeypatch.setattr(
        StrategyHeroPower, "detail_hero_power",
        property(lambda self: behavior("HERO_10bp")),
    )
    power = StrategyHeroPower("HERO_10bp", "PLAY", 0, 1, 0, True, False, 0)
    assert power.detail_hero_power is behavior("HERO_10bp")


def test_eye_beam_waits_for_an_enemy_minion():
    card = behavior("BT_801")
    assert card.best_h_and_arg(board(), 0) == (0, -1)
    assert card.best_h_and_arg(board([enemy()]), 0) == (3, 0)


def test_aldrachi_warblades_does_not_replace_an_equipped_weapon():
    card = behavior("BT_921")
    assert card.best_h_and_arg(board(weapon=object()), 0)[0] == 0
    assert card.best_h_and_arg(board(), 0)[0] > 0


def test_gliding_wings_refills_a_small_hand():
    card = behavior("VAC_928")
    state = board()
    state.my_hand_card_num = 3
    assert card.best_h_and_arg(state, 0)[0] > 0
    state.my_hand_card_num = 10
    assert card.best_h_and_arg(state, 0)[0] == 0


def test_mining_axe_does_not_replace_an_equipped_weapon():
    card = behavior("DEEP_014")
    assert card.best_h_and_arg(board(weapon=object()), 0)[0] == 0
    assert card.best_h_and_arg(board(), 0)[0] > 0


def test_igneous_heart_targets_an_enemy_minion_for_damage():
    card = behavior("DEEP_011")
    state = board([enemy()])
    score, target = card.best_h_and_arg(state, 0)
    assert score > 0
    assert target == ("enemy", 0)


def test_igneous_heart_uses_an_own_minion_for_attack_bonus():
    card = behavior("DEEP_011")
    own = SimpleNamespace(
        health=3, attack=2, can_be_pointed_by_spell=True, can_beat_face=True,
        delta_h_after_damage=lambda damage: -0.1,
    )
    state = board()
    state.my_minions = [own]
    score, target = card.best_h_and_arg(state, 0)
    assert score > 0
    assert target == ("mine", 0)


def test_igneous_heart_waits_without_a_target():
    card = behavior("DEEP_011")
    state = board()
    assert card.best_h_and_arg(state, 0)[0] == 0


def test_rush_spell_waits_without_a_minion_target():
    card = behavior("JAM_017")
    state = board()
    assert card.best_h_and_arg(state, 0)[0] == 0


def test_rush_spell_uses_finale_for_a_ready_attacker():
    card = behavior("JAM_017")
    ready = SimpleNamespace(
        attack=4, exhausted=0, can_be_pointed_by_spell=True,
        can_attack_minion=True,
    )
    state = board()
    state.my_minions = [ready]
    state.my_remaining_mana = 0
    score, target = card.best_h_and_arg(state, 0)
    assert score > 0
    assert target == 0


def test_igneous_heart_targets_an_enemy_minion_with_actual_clicks(monkeypatch):
    from autohs.behaviors.basic import Card
    from autohs.behaviors import demon_hunter

    events = []
    controls = SimpleNamespace(
        cards=SimpleNamespace(chooseHandCard=lambda *a: events.append("card")),
        minion=SimpleNamespace(
            chooseMyMinion=lambda *a: events.append("mine"),
            chooseEnemyMinion=lambda *a: events.append("enemy"),
        ),
        game=SimpleNamespace(cancelClick=lambda: None),
    )
    monkeypatch.setattr(demon_hunter, "clicks", lambda: controls)
    monkeypatch.setattr(Card, "finish_action", classmethod(lambda cls: None))

    state = board([enemy()])
    state.my_hand_card_num = 1
    behavior("DEEP_011").use_with_arg(state, 0, ("enemy", 0))
    assert events == ["card", "enemy"]


def test_rush_spell_targets_a_friendly_minion_with_actual_clicks(monkeypatch):
    from autohs.behaviors.basic import Card
    from autohs.behaviors import demon_hunter

    events = []
    controls = SimpleNamespace(
        cards=SimpleNamespace(chooseHandCard=lambda *a: events.append("card")),
        minion=SimpleNamespace(chooseMyMinion=lambda *a: events.append("mine")),
        game=SimpleNamespace(cancelClick=lambda: None),
    )
    monkeypatch.setattr(demon_hunter, "clicks", lambda: controls)
    monkeypatch.setattr(Card, "finish_action", classmethod(lambda cls: None))

    state = board()
    state.my_hand_card_num = 1
    state.my_minion_num = 1
    behavior("JAM_017").use_with_arg(state, 0, 0)
    assert events == ["card", "mine"]


def test_hero_attacks_face_instead_of_a_minion_that_would_kill_it():
    state = object.__new__(StrategyState)
    state.my_minions = []
    state.my_weapon = None
    state.my_hero = SimpleNamespace(
        name="测试英雄", attack=2, health=2, can_attack=True,
        can_be_pointed_by_minion=True,
        delta_h_after_damage=lambda damage: 0,
    )
    state.oppo_hero = SimpleNamespace(
        name="敌方英雄", health=30, can_be_pointed_by_minion=True,
        delta_h_after_damage=lambda damage: 1,
    )
    state.oppo_minions = [SimpleNamespace(
        zone_pos=1, name="测试随从", attack=2, taunt=False,
        can_be_pointed_by_minion=True, can_be_attacked=True,
        delta_h_after_damage=lambda damage: 1,
    )]
    assert state.get_best_attack_target() == (-1, -1)


def test_illidari_inquisitor_is_not_penalized_as_an_unknown_card():
    card = behavior("CS3_020")
    assert card.value >= 5


def test_first_turn_prefers_a_playable_minion_over_a_higher_scored_spell():
    class SpellBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 10,

    class MinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 2, 0

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="测试法术",
            detail_card=SpellBehavior,
            cardtype=CARD_SPELL,
            battlecry=0,
        ),
        SimpleNamespace(
            current_cost=1,
            name="测试随从",
            detail_card=MinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=True, current_cost=1, name="测试技能", detail_hero_power=None,
    )

    assert state.best_h_index_arg() == (1, [0])


def test_first_turn_prefers_a_playable_minion_even_when_its_score_is_zero():
    class SpellBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 10,

    class MinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 0, 0

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="测试法术",
            detail_card=SpellBehavior,
            cardtype=CARD_SPELL,
            battlecry=0,
        ),
        SimpleNamespace(
            current_cost=1,
            name="测试随从",
            detail_card=MinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=True, current_cost=1, name="测试技能", detail_hero_power=None,
    )

    assert state.best_h_index_arg() == (1, [0])


def test_first_turn_picks_the_highest_scored_playable_minion():
    class FirstMinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 1, 0

    class SecondMinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 4, 1

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="低分随从",
            detail_card=FirstMinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
        SimpleNamespace(
            current_cost=1,
            name="高分随从",
            detail_card=SecondMinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=True, current_cost=1, name="测试技能", detail_hero_power=None,
    )

    assert state.best_h_index_arg() == (1, [1])


def test_first_turn_plays_a_minion_when_no_card_has_a_positive_score():
    class ZeroMinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 0, 0

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="零分随从",
            detail_card=ZeroMinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=True, current_cost=1, name="测试技能", detail_hero_power=None,
    )

    assert state.best_h_index_arg() == (0, [0])


def test_first_turn_does_not_prefer_a_minion_when_the_opponent_is_lethal():
    class LethalSpell:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 1000, -1

    class MinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 2, 0

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="斩杀法术",
            detail_card=LethalSpell,
            cardtype=CARD_SPELL,
            battlecry=0,
        ),
        SimpleNamespace(
            current_cost=1,
            name="测试随从",
            detail_card=MinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=True, current_cost=1, name="测试技能", detail_hero_power=None,
    )

    assert state.best_h_index_arg() == (0, [-1])


def test_first_turn_minion_preference_overrides_a_nonlethal_hero_power():
    class MinionBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 2, 0

    class HeroPowerBehavior:
        @classmethod
        def best_h_and_arg(cls, state, hand_card_index):
            return 6,

    state = object.__new__(StrategyState)
    state.my_minions = []
    state.oppo_minions = []
    state.my_hand_cards = [
        SimpleNamespace(
            current_cost=1,
            name="测试随从",
            detail_card=MinionBehavior,
            cardtype=CARD_MINION,
            battlecry=0,
        ),
    ]
    state.my_total_mana = 1
    state.my_used_mana = 0
    state.my_temp_mana = 0
    state.my_num_turns_in_play = 1
    state.my_hero_power = SimpleNamespace(
        exhausted=False, current_cost=1, name="测试技能",
        detail_hero_power=HeroPowerBehavior,
    )
    assert state.best_h_index_arg() == (0, [0])


def test_acupuncture_waits_without_alana_or_lethal():
    state = board()
    state.my_hero.health = 20
    state.my_remaining_mana = 1

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] == 0


def test_acupuncture_is_used_with_alana_on_board():
    state = board()
    state.my_hero.health = 20
    state.my_minions = [SimpleNamespace(card_id="VAC_501")]

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] >= 5


def test_acupuncture_uses_alana_damage_redirection_at_low_health():
    state = board()
    state.my_hero.health = 4
    state.my_minions = [SimpleNamespace(card_id="VAC_501")]

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] > 0


def test_acupuncture_can_be_lethal_without_alana():
    state = board()
    state.my_hero.health = 20
    state.oppo_hero.health = 4

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] >= 1000


def test_acupuncture_is_not_played_when_it_would_kill_the_hero():
    state = board()
    state.my_hero.health = 4

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] == 0


def test_acupuncture_claims_lethal_without_alana():
    state = board()
    state.my_hero.health = 20
    state.oppo_hero.health = 4

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] >= 1000


def test_acupuncture_does_not_kill_its_own_hero_without_alana():
    state = board()
    state.my_hero.health = 4
    state.oppo_hero.health = 4

    assert behavior("VAC_419").best_h_and_arg(state, 0)[0] == 0


def test_demon_hunter_hero_power_prioritizes_face_when_hero_can_attack():
    state = board()
    state.my_hero.attack = 0
    state.my_hero.exhausted = 0
    state.oppo_hero.health = 20

    assert behavior("HERO_10cbp").best_h_and_arg(state, -1)[0] >= 5


def test_demon_hunter_hero_power_waits_behind_taunt():
    state = board()
    state.my_hero.exhausted = 0
    state.oppo_has_taunt = True

    assert behavior("HERO_10cbp").best_h_and_arg(state, -1)[0] == 0


def test_hero_prefers_face_over_a_minion_trade_without_taunt():
    state = object.__new__(StrategyState)
    state.my_minions = []
    state.my_weapon = None
    state.my_hero = SimpleNamespace(
        name="测试英雄", attack=2, health=30, can_attack=True,
        can_be_pointed_by_minion=True, exhausted=0,
        delta_h_after_damage=lambda damage: 0,
    )
    state.oppo_hero = SimpleNamespace(
        name="敌方英雄", health=20, can_be_pointed_by_minion=True,
        delta_h_after_damage=lambda damage: 1.0,
    )
    state.oppo_minions = [SimpleNamespace(
        zone_pos=1, name="测试随从", attack=1, taunt=False,
        can_be_pointed_by_minion=True, can_be_attacked=True,
        delta_h_after_damage=lambda damage: 2.0,
    )]

    assert state.get_best_attack_target() == (-1, -1)
