import copy

import pytest
from test_pirate_demon_hunter import minion, spell, state

from autohs.behaviors.registry import ID2CARD_DICT
from autohs.strategy.entities import StrategyLocation, StrategyWeapon


def enemy(card_id="UNG_205", attack=1, health=2, taunt=False):
    target = minion(card_id, attack=attack, health=health)
    target.is_mine = False
    target.taunt = taunt
    return target


def test_monkey_preattack_buff_makes_a_single_trade_survive():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.my_minions = [
        minion("VAC_938", ready=False),
        minion("VAC_926t", attack=1, health=1),
    ]
    board.oppo_minions = [enemy(attack=1, health=2)]
    assert board.get_best_attack_target() == (1, 0)
    assert (board.my_minions[1].attack, board.my_minions[1].health) == (1, 1)


def test_silenced_monkey_does_not_supply_a_preattack_buff():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    monkey = minion("VAC_938", ready=False)
    monkey.silenced = True
    board.my_minions = [monkey, minion("VAC_926t", attack=1, health=1)]
    board.oppo_minions = [enemy(attack=1, health=2)]
    assert board.get_best_attack_target() == (1, -1)


def test_aranna_attack_values_redirected_damage_in_addition_to_protection():
    board = state(mana=0)
    board.my_hero.attack = 1
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [enemy(attack=8, health=8), enemy(attack=1, health=8)]
    board.oppo_minions[1].zone_pos = 2
    assert board.get_best_attack_target() == (-1, 0)


def test_immunity_does_not_supply_aranna_redirect_damage():
    board = state(mana=0)
    board.my_hero.attack = 1
    board.my_hero.immune = 1
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [enemy(attack=8, health=8), enemy(attack=1, health=1)]
    board.oppo_minions[1].zone_pos = 2
    assert board.get_best_attack_target() == (-1, 1)


def test_aranna_hero_power_opens_a_safe_taunt_removal():
    board = state(mana=1)
    board.my_hero.damage = 29
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [enemy(attack=3, health=1, taunt=True)]
    assert board.next_battle_action() == ("card", -1, [])


@pytest.mark.parametrize("disabled", ["silenced", "dormant"])
def test_inactive_aranna_does_not_enable_a_suicidal_taunt_attack(disabled):
    board = state(mana=1)
    board.my_hero.damage = 29
    aranna = minion("VAC_501", ready=False)
    setattr(aranna, disabled, True)
    board.my_minions = [aranna]
    board.oppo_minions = [enemy(attack=3, health=1, taunt=True)]
    assert ID2CARD_DICT["HERO_10cbp"].best_h_and_arg(board, -1)[0] == 0


def test_aranna_face_retaliation_is_guaranteed_only_with_no_enemy_minions():
    board = state(mana=0, enemy_health=4)
    board.my_hero.attack = 1
    board.oppo_hero.attack = 3
    board.my_minions = [minion("VAC_501", ready=False)]
    assert board.guaranteed_face_damage == 4
    board.oppo_minions = [enemy(health=5)]
    assert board.guaranteed_face_damage == 1


def test_other_pirates_attack_before_a_fragile_attack_engine():
    board = state(mana=0, enemy_health=10)
    board.my_hero.attack = 1
    board.oppo_hero.attack = 2
    board.my_minions = [
        minion("VAC_927", attack=2, health=1),
        minion("VAC_926t", attack=2, health=3),
        minion("MIS_710", attack=2, health=3),
    ]
    assert board.get_best_attack_target() == (1, -1)


def test_gliding_wings_waits_until_three_or_fewer_cards():
    board = state(mana=3)
    board.my_hand_cards = [spell("VAC_928", 3)] + [spell("VAC_419") for _ in range(3)]
    assert ID2CARD_DICT["VAC_928"].best_h_and_arg(board, 0)[0] == 0


def test_gliding_wings_does_not_compete_with_a_playable_minion():
    board = state(mana=4)
    board.my_hand_cards = [spell("VAC_928", 3), minion("CFM_325", zone="HAND")]
    assert ID2CARD_DICT["VAC_928"].best_h_and_arg(board, 0)[0] == 0
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_gliding_wings_refills_when_the_only_minion_is_unaffordable():
    board = state(mana=3)
    body = minion("VAC_501", zone="HAND")
    body.current_cost = 5
    board.my_hand_cards = [spell("VAC_928", 3), body]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_gliding_wings_is_not_playable_with_less_than_three_mana():
    board = state(mana=2)
    board.my_hand_cards = [spell("VAC_928", 3)]
    assert ID2CARD_DICT["VAC_928"].best_h_and_arg(board, 0)[0] == 0


def test_gliding_wings_unlocks_outcast_with_a_useful_free_edge_spell():
    board = state(mana=3)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=2, health=3, ready=False)]
    board.oppo_minions = [enemy(attack=1, health=2)]
    board.my_hand_cards = [spell("JAM_017", 0), spell("VAC_928", 3), spell("VAC_419")]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_gliding_wings_does_not_unlock_outcast_by_wasting_needles():
    board = state(mana=4)
    board.my_hand_cards = [spell("VAC_419"), spell("VAC_928", 3), spell("VAC_419")]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_ready_lethal_still_precedes_refilling():
    board = state(mana=3, enemy_health=2)
    board.my_minions = [minion("VAC_926t", attack=2)]
    board.my_hand_cards = [spell("VAC_928", 3)]
    assert board.next_battle_action() == ("attack", 0, -1)


def test_hero_and_one_minion_can_plan_a_taunt_kill_together():
    board = state(mana=0)
    board.my_hero.attack = 2
    board.my_minions = [minion("VAC_926t", attack=1, health=1)]
    board.oppo_minions = [enemy(attack=4, health=3, taunt=True)]
    assert board.get_best_combined_trade() == (-1, 0)


def test_combined_trade_excludes_a_hero_that_would_die():
    board = state(mana=0)
    board.my_hero.attack = 2
    board.my_hero.damage = 28
    board.my_minions = [minion("VAC_926t", attack=1, health=1)]
    board.oppo_minions = [enemy(attack=4, health=3, taunt=True)]
    assert board.get_best_combined_trade() is None


def test_hero_combination_uses_pirate_attack_before_spending_hero_attack():
    board = state(mana=0)
    board.my_hero.attack = 1
    board.my_minions = [
        minion("VAC_927", attack=2, health=2, ready=False),
        minion("VAC_926t", attack=1, health=1),
    ]
    board.oppo_minions = [enemy(attack=3, health=3, taunt=True)]
    assert board.get_best_combined_trade() == (1, 0)


def test_hero_combination_does_not_pretend_a_shield_takes_damage():
    board = state(mana=0)
    board.my_hero.attack = 2
    board.my_minions = [minion("VAC_926t", attack=1, health=1)]
    target = enemy(attack=4, health=3, taunt=True)
    target.divine_shield = True
    board.oppo_minions = [target]
    assert board.get_best_combined_trade() is None


def test_cliffside_tokens_discount_zilliax_within_the_same_turn():
    board = state(mana=7)
    board.my_minions = [minion("VAC_926t", health=1), minion("VAC_926t", health=1)]
    zilliax = minion("TOY_330t5", attack=3, health=5, zone="HAND")
    zilliax.current_cost = 5
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [zilliax, cliff]
    assert board.next_battle_action()[0:2] == ("card", 1)
    assert zilliax.current_cost == 5
    assert len(board.my_minions) == 2


def test_zilliax_sequence_does_not_count_the_location_as_a_minion_discount():
    board = state(mana=6)
    board.my_minions = [minion("VAC_926t", health=1), minion("VAC_926t", health=1)]
    zilliax = minion("TOY_330t5", attack=3, health=5, zone="HAND")
    zilliax.current_cost = 5
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [zilliax, cliff]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_profitable_trade_opens_two_token_slots_before_filling_the_last_slot():
    board = state(mana=1)
    board.my_hero.exhausted = 1
    board.my_minions = [StrategyLocation("VAC_929", "PLAY", 1, 4, 0, True, False, 3, 0)]
    board.my_minions += [minion("VAC_926t", attack=1, health=1) for _ in range(5)]
    for pos, body in enumerate(board.my_minions, 1):
        body.zone_pos = pos
    board.oppo_minions = [enemy(attack=2, health=1)]
    board.my_hand_cards = [minion("CFM_325", zone="HAND")]
    assert board.next_battle_action() == ("attack", 1, 0)


def test_board_space_does_not_justify_throwing_away_a_large_attacker():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.my_minions = [StrategyLocation("VAC_929", "PLAY", 1, 4, 0, True, False, 3, 0)]
    board.my_minions += [minion("VAC_926t", attack=8, health=1) for _ in range(5)]
    for pos, body in enumerate(board.my_minions, 1):
        body.zone_pos = pos
    board.oppo_minions = [enemy(attack=2, health=1)]
    assert board.next_battle_action()[2] == -1


def test_cannon_damage_is_certain_when_the_enemy_hero_is_the_only_enemy():
    board = state(mana=0, enemy_health=2)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_532", ready=False), minion("VAC_926t", health=1)]
    assert board.guaranteed_face_damage == 2
    assert board.next_battle_action() == ("attack", 1, -1)


def test_cannon_damage_with_an_enemy_minion_is_only_expected_damage():
    board = state(mana=0, enemy_health=2)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_532", ready=False), minion("VAC_926t", health=1)]
    board.oppo_minions = [enemy(attack=0, health=8)]
    assert board.guaranteed_face_damage == 1


def test_charge_minion_is_placed_next_to_the_cannon_instead_of_a_sleeping_body():
    board = state(mana=1)
    board.my_minions = [
        minion("VAC_926t"),
        minion("VAC_532", ready=False),
        minion("VAC_926t", ready=False),
    ]
    charger = minion("VAC_926t", zone="HAND")
    charger.charge = 1
    board.my_hand_cards = [charger]
    assert board.best_h_index_arg() == (0, [2])


def test_cannon_expected_trigger_can_break_an_otherwise_equal_attack_tie():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.my_minions = [
        minion("VAC_926t", attack=2),
        minion("VAC_926t", attack=2),
        minion("VAC_532", ready=False),
    ]
    assert board.get_best_attack_target() == (1, -1)


def test_heart_accounts_for_the_puppet_and_hero_damage_together():
    board = state(mana=1, enemy_health=8)
    board.my_hero.attack = 0
    board.my_minions = [
        minion("MIS_710", attack=1, health=4),
        minion("VAC_926t", health=4, ready=False),
    ]
    board.oppo_minions = [enemy(attack=0, health=4)]
    board.my_hand_cards = [spell("DEEP_011")]
    assert board.next_battle_action()[0:2] == ("card", 0)
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] < 1000


def test_heart_claims_lethal_when_its_damage_removes_the_only_taunt():
    board = state(mana=1, enemy_health=3)
    board.oppo_minions = [enemy(attack=1, health=2, taunt=True)]
    board.my_minions = [minion("VAC_926t", attack=3)]
    board.my_hand_cards = [spell("DEEP_011")]
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] >= 1000


def test_nonfinale_rush_waits_if_it_cannot_enable_a_profitable_trade():
    board = state(mana=1)
    board.my_minions = [minion("VAC_926t", attack=1, health=1, ready=False)]
    board.oppo_minions = [enemy(attack=8, health=8)]
    board.my_hand_cards = [spell("JAM_017", 0)]
    assert ID2CARD_DICT["JAM_017"].best_h_and_arg(board, 0)[0] == 0


def test_rush_preserves_finale_until_a_useful_mana_spend_is_done():
    board = state(mana=1)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=1, health=1, ready=False)]
    board.oppo_minions = [enemy(attack=1, health=2)]
    board.my_hand_cards = [spell("JAM_017", 0), minion("VAC_933", zone="HAND")]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_combined_trade_spends_puppet_attack_before_the_last_weapon_durability():
    board = state(mana=0)
    board.my_hero.attack = 1
    board.my_weapon = StrategyWeapon("DEEP_014", "PLAY", 1, 2, 0, True, False, 1, 2)
    board.my_weapon.damage = 1
    board.my_minions = [minion("MIS_710", attack=2, health=3)]
    board.oppo_minions = [enemy(attack=1, health=3, taunt=True)]
    assert board.get_best_combined_trade() == (0, 0)


@pytest.mark.parametrize("disabled", ["silenced", "dormant", "untouchable"])
def test_inactive_cannon_never_contributes_guaranteed_damage(disabled):
    board = state(mana=0)
    board.my_hero.exhausted = 1
    cannon = minion("VAC_532", ready=False)
    setattr(cannon, disabled, True)
    board.my_minions = [cannon, minion("VAC_926t", health=1)]
    assert board.guaranteed_face_damage == 1


def test_face_projection_does_not_mutate_attack_buffs_or_shields():
    board = state(mana=0)
    board.my_hero.attack = 1
    board.oppo_hero.attack = 2
    board.my_minions = [
        minion("VAC_927", attack=2, health=3),
        minion("VAC_938", attack=2, health=4),
        minion("MIS_710", attack=2, health=2),
    ]
    board.my_minions[0].divine_shield = True
    before = copy.deepcopy(board)
    first = board.guaranteed_face_damage
    assert board.guaranteed_face_damage == first
    assert board.my_hero.__dict__ == before.my_hero.__dict__
    assert [m.__dict__ for m in board.my_minions] == [
        m.__dict__ for m in before.my_minions
    ]


def test_dying_captain_cannot_leave_an_aura_on_later_attacks():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.oppo_hero.attack = 5
    board.my_minions = [
        minion("CORE_NEW1_027", attack=3, health=1),
        minion("CORE_NEW1_027", attack=4, health=2),
    ]
    assert board.guaranteed_face_damage == 6


@pytest.mark.parametrize("hand_count", [4, 8, 9, 10])
def test_gliding_wings_never_refills_a_hand_above_the_agreed_threshold(hand_count):
    board = state(mana=10)
    board.my_hand_cards = [spell("VAC_928", 3)] + [
        spell("VAC_419") for _ in range(hand_count - 1)
    ]
    assert ID2CARD_DICT["VAC_928"].best_h_and_arg(board, 0)[0] == 0


def test_full_board_does_not_mistake_a_minion_for_a_playable_one_before_drawing():
    board = state(mana=3)
    board.my_minions = [minion("VAC_926t", ready=False) for _ in range(7)]
    board.my_hand_cards = [spell("VAC_928", 3), minion("CFM_325", zone="HAND")]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_gliding_wings_never_unlocks_outcast_with_a_fatal_needle():
    board = state(mana=4)
    board.my_hero.damage = 29
    board.my_hand_cards = [spell("VAC_419"), spell("VAC_928", 3), spell("VAC_419")]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_heart_does_not_claim_lethal_when_a_killed_taunt_has_a_deathrattle():
    board = state(mana=1, enemy_health=3)
    target = enemy("FP1_012", attack=1, health=2, taunt=True)
    board.oppo_minions = [target]
    board.my_minions = [minion("VAC_926t", attack=3)]
    board.my_hand_cards = [spell("DEEP_011")]
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] < 1000


def test_heart_does_not_count_hero_attack_twice_with_a_ready_puppet():
    board = state(mana=1, enemy_health=7)
    board.my_minions = [minion("MIS_710", attack=1, health=4)]
    board.oppo_minions = [enemy(attack=0, health=4)]
    board.my_hand_cards = [spell("DEEP_011")]
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] >= 1000


def test_rush_does_not_pretend_a_frozen_minion_can_attack():
    board = state(mana=1)
    body = minion("VAC_926t", attack=4, ready=False)
    body.frozen = True
    board.my_minions = [body]
    board.oppo_minions = [enemy(attack=1, health=2)]
    board.my_hand_cards = [spell("JAM_017", 0)]
    assert ID2CARD_DICT["JAM_017"].best_h_and_arg(board, 0)[0] == 0


def test_aranna_is_developed_before_a_cheaper_engine_when_it_enables_hero_removal():
    board = state(mana=5)
    board.my_hero.attack = 1
    board.my_hero.damage = 29
    board.oppo_minions = [enemy(attack=8, health=8)]
    aranna = minion("VAC_501", attack=5, health=6, zone="HAND")
    aranna.current_cost = 5
    support = minion("VAC_927", attack=2, health=2, zone="HAND")
    support.current_cost = 2
    board.my_hand_cards = [aranna, support]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_acupuncture_scores_the_redirect_without_claiming_random_lethal():
    board = state(mana=1, enemy_health=8)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [enemy(attack=8, health=4)]
    board.my_hand_cards = [spell("VAC_419")]
    score = ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0]
    assert 5 < score < 1000


def test_random_redirect_has_bounded_value_even_when_one_branch_would_be_lethal():
    from autohs.strategy.combat import redirected_value

    board = state(mana=0, enemy_health=1)
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [enemy(attack=0, health=2)]
    assert 0 < redirected_value(board, 4) < 10


def test_immune_enemy_is_not_counted_as_damage_for_random_redirect():
    from autohs.strategy.combat import redirected_value

    board = state(mana=0)
    board.my_minions = [minion("VAC_501", ready=False)]
    target = enemy(attack=0, health=2)
    target.immune = 1
    board.oppo_minions = [target]
    assert redirected_value(board, 2) == pytest.approx(0.6)


def test_full_board_takes_a_profitable_trade_before_refill_for_parachute_space():
    board = state(mana=3)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", health=1) for _ in range(7)]
    for pos, body in enumerate(board.my_minions, 1):
        body.zone_pos = pos
    board.oppo_minions = [enemy(attack=2, health=1)]
    board.my_hand_cards = [spell("VAC_928", 3)]
    assert board.next_battle_action() == ("attack", 0, 0)


def test_buff_enabling_lethal_is_played_before_a_noncontributing_dealer():
    board = state(mana=4, enemy_health=3)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=2, health=2)]
    dealer = minion("TOY_518", zone="HAND")
    captain = minion("CORE_NEW1_027", attack=3, health=3, zone="HAND")
    captain.current_cost = 3
    board.my_hand_cards = [dealer, captain]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_captain_lethal_takes_priority_over_patches_when_mana_cannot_pay_for_both():
    board = state(mana=3, enemy_health=6)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=2), minion("VAC_926t", attack=2)]
    captain = minion("CORE_NEW1_027", attack=3, health=3, zone="HAND")
    captain.current_cost = 3
    board.my_hand_cards = [minion("VAC_933", zone="HAND"), captain]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_new_monkey_can_enable_a_certain_lethal_before_patches():
    board = state(mana=3, enemy_health=6)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=2), minion("VAC_926t", attack=2)]
    monkey = minion("VAC_938", attack=2, health=4, zone="HAND")
    monkey.current_cost = 3
    board.my_hand_cards = [minion("VAC_933", zone="HAND"), monkey]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_new_cannon_certain_lethal_precedes_patches():
    board = state(mana=2, enemy_health=6)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=2), minion("VAC_926t", attack=2)]
    cannon = minion("VAC_532", attack=1, health=4, zone="HAND")
    cannon.current_cost = 2
    board.my_hand_cards = [minion("VAC_933", zone="HAND"), cannon]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_combined_trade_removes_auras_from_secondary_captain_deaths():
    from autohs.strategy.combat import combined_trade_gain

    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.my_minions = [
        minion("CORE_NEW1_027", attack=4, health=1),
        minion("CORE_NEW1_027", attack=4, health=1, ready=False),
        minion("VAC_926t", attack=3, health=2),
    ]
    board.oppo_minions = [enemy(attack=20, health=6, taunt=True)]
    assert combined_trade_gain(board, board.oppo_minions[0], (0, 2)) is None


def test_combined_trade_reorders_a_leftmost_puppet_after_the_pirate():
    board = state(mana=0)
    board.my_hero.exhausted = 1
    board.my_minions = [
        minion("MIS_710", attack=1, health=1),
        minion("VAC_927", attack=2, health=2, ready=False),
        minion("VAC_926t", attack=1, health=1),
    ]
    board.oppo_minions = [enemy(attack=6, health=3)]
    assert board.get_best_combined_trade() == (2, 0)


def test_cliffside_monkey_lethal_in_hand_precedes_patches():
    board = state(mana=4, enemy_health=4)
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_938", ready=False)]
    cliff = StrategyLocation("VAC_929", "HAND", 1, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [minion("VAC_933", zone="HAND"), cliff]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_cliffside_monkey_lethal_on_board_precedes_patches():
    board = state(mana=1, enemy_health=4)
    board.my_hero.exhausted = 1
    board.my_minions = [
        minion("VAC_938", ready=False),
        StrategyLocation("VAC_929", "PLAY", 2, 4, 0, True, False, 3, 0),
    ]
    board.my_hand_cards = [minion("VAC_933", zone="HAND")]
    assert board.next_battle_action() == ("location", 1, [])


def cliff_board(durability=1, bodies=5, enemy_health=30):
    board = state(mana=0, enemy_health=enemy_health)
    board.my_hero.exhausted = 1
    board.my_hero_power.exhausted = 1
    board.my_minions = [
        minion("VAC_926t", health=1, ready=False) for _ in range(bodies)
    ]
    board.my_minions.append(
        StrategyLocation(
            "VAC_929", "PLAY", bodies + 1, 4, 0, True, False, durability, 0
        )
    )
    return board


def test_last_durability_cliffside_supplies_its_own_second_token_slot():
    board = cliff_board()
    assert board.next_battle_action() == ("location", 5, [])


def test_nonfinal_cliffside_does_not_invent_a_second_token_slot():
    board = cliff_board(durability=2)
    assert board.get_best_location_trigger() == (-1, [])


def test_last_durability_cliffside_summons_two_chargers_and_disappears():
    from autohs.strategy.turn import trigger_cliffside

    board = cliff_board()
    simulated = trigger_cliffside(board, 5)
    assert len(simulated.my_minions) == 7
    assert all(body.card_id != "VAC_929" for body in simulated.my_minions)
    assert sum(body.can_beat_face for body in simulated.my_minions) == 2
    assert len(board.my_minions) == 6


def test_last_durability_cliffside_lethal_precedes_filling_the_last_slot():
    board = cliff_board(enemy_health=2)
    board.my_total_mana = 1
    board.my_hand_cards = [minion("VAC_933", zone="HAND")]
    assert board.next_battle_action() == ("location", 5, [])
    assert (
        board.my_minions[5].detail_card.location_trigger_h_and_arg(board, 5)[0] >= 1000
    )


def test_completely_full_board_last_cliffside_only_has_one_token_slot():
    from autohs.strategy.turn import trigger_cliffside

    board = cliff_board(bodies=6, enemy_health=2)
    simulated = trigger_cliffside(board, 6)
    assert len(simulated.my_minions) == 7
    assert sum(body.can_beat_face for body in simulated.my_minions) == 1
    assert (
        board.my_minions[6].detail_card.location_trigger_h_and_arg(board, 6)[0] < 1000
    )


def test_real_power_damage_tag_sets_remaining_location_durability():
    from autohs.logs.power import parse_line
    from autohs.logs.state import LogState, update_state
    from autohs.strategy.entities import generate_strategy_entity

    log = LogState()
    log.my_player_id = "1"
    messages = ["FULL_ENTITY - Creating ID=77 CardID=VAC_929"] + [
        f"tag={tag} value={value}"
        for tag, value in {
            "CARDTYPE": "LOCATION",
            "CONTROLLER": "1",
            "ZONE": "PLAY",
            "ZONE_POSITION": "6",
            "HEALTH": "3",
            "DAMAGE": "2",
            "EXHAUSTED": "0",
        }.items()
    ]
    for message in messages:
        event = parse_line(
            "D 01:00:00.0000000 GameState.DebugPrintPower() - " + message
        )
        update_state(log, event)
    location = generate_strategy_entity(log.entity_dict["77"], log)
    assert location.health == 1
    board = cliff_board()
    board.my_minions[5] = location
    assert board.next_battle_action() == ("location", 5, [])


@pytest.mark.parametrize("mana,can_refill", [(4, False), (5, True)])
def test_two_one_drops_are_played_before_deciding_whether_to_refill(mana, can_refill):
    board = state(mana=mana)
    board.my_hand_cards = [
        spell("VAC_928", 3),
        minion("CFM_325", zone="HAND"),
        minion("CFM_325", zone="HAND"),
    ]
    for _ in range(2):
        action, index, _args = board.next_battle_action()
        assert action == "card"
        assert board.my_hand_cards[index].card_id == "CFM_325"
        body = board.my_hand_cards.pop(index)
        board.my_used_mana += body.current_cost
        body.zone = "PLAY"
        body.exhausted = 1
        board.my_minions.append(body)
    decision = board.next_battle_action()
    if can_refill:
        assert decision[0:2] == ("card", 0)
    else:
        assert decision[0:2] != ("card", 0)
