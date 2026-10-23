from autohs.behaviors.registry import ID2CARD_DICT
from autohs.logs.power import parse_line
from autohs.logs.state import CardEntity, LogState, update_state
from autohs.strategy.entities import (
    StrategyHero,
    StrategyHeroPower,
    StrategyLocation,
    StrategyMinion,
    StrategySpell,
    StrategyWeapon,
    generate_strategy_entity,
)
from autohs.strategy.state import StrategyState


def minion(card_id, attack=1, health=3, ready=True, zone="PLAY",
           deathrattle=False, taunt=False):
    return StrategyMinion(card_id, zone, 1, 1, 0, True, False,
                          attack, health, deathrattle=int(deathrattle),
                          exhausted=int(not ready), taunt=int(taunt))


def spell(card_id, cost=1):
    return StrategySpell(card_id, "HAND", 1, cost, 0, True, False)


def state(mana=1, enemy_health=30):
    result = object.__new__(StrategyState)
    result.my_minions = []
    result.oppo_minions = []
    result.my_hand_cards = []
    result.my_weapon = None
    result.my_hero = StrategyHero("HERO_10", "PLAY", 0, 0, 0, True, False,
                                  30, exhausted=0)
    result.oppo_hero = StrategyHero("HERO_04", "PLAY", 0, 0, 0, False, False,
                                    enemy_health)
    result.my_hero_power = StrategyHeroPower("HERO_10cbp", "PLAY", 0, 1, 0,
                                             True, False, 0)
    result.my_total_mana = mana
    result.my_used_mana = 0
    result.my_temp_mana = 0
    result.my_num_turns_in_play = 3
    return result


def test_pilot_is_played_before_other_one_drops():
    board = state()
    board.my_hand_cards = [minion("TOY_518", zone="HAND"),
                           minion("VAC_933", zone="HAND")]
    assert board.best_h_index_arg()[0] == 1


def test_second_players_first_turn_uses_player_turn_tag():
    log = LogState()
    messages = [
        "GameEntity EntityID=1", "Player EntityID=2 PlayerID=1 GameAccountId=[hi=1 lo=1]",
        "Player EntityID=3 PlayerID=2 GameAccountId=[hi=2 lo=2]",
        "TAG_CHANGE Entity=2 tag=TURN value=1",
        "TAG_CHANGE Entity=2 tag=NUM_TURNS_IN_PLAY value=2",
        "TAG_CHANGE Entity=2 tag=RESOURCES value=1",
    ]
    for message in messages:
        event = parse_line("D 01:00:00.0000000 GameState.DebugPrintPower() - " + message + " ")
        assert event is not None
        update_state(log, event)
    log.my_player_id = "1"
    assert StrategyState(log).my_num_turns_in_play == 1


def test_ready_lethal_happens_before_drawing_or_playing_pilot():
    board = state(mana=10, enemy_health=3)
    board.my_minions = [minion("VAC_926t", attack=3)]
    board.my_hand_cards = [minion("VAC_933", zone="HAND"), spell("VAC_928", 3)]
    assert board.next_battle_action() == ("attack", 0, -1)


def test_low_enemy_health_prefers_face_over_a_profitable_trade():
    board = state(enemy_health=10)
    board.my_minions = [minion("VAC_926t", attack=3)]
    target = minion("VAC_927", attack=1, health=3)
    target.is_mine = False
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (0, -1)


def test_low_enemy_health_still_respects_taunt():
    board = state(enemy_health=10)
    board.my_minions = [minion("VAC_926t", attack=3)]
    target = minion("VAC_927", attack=1, health=3)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (0, 0)


def two_turn_pressure_board(enemy_health=13):
    board = state(mana=0, enemy_health=enemy_health)
    board.my_minions = [minion("VAC_926t", attack=5, health=5),
                        minion("VAC_926t", attack=3, health=4, ready=False)]
    board.my_minions[1].zone_pos = 2
    target = minion("UNG_205", attack=2, health=5)
    target.is_mine = False
    board.oppo_minions = [target]
    return board


def test_two_turn_finish_prefers_face_over_a_slightly_better_material_trade():
    board = two_turn_pressure_board()
    assert board.get_best_attack_target() == (0, -1)


def test_two_turn_pressure_also_weights_the_face_damage_forgone_by_combined_trades():
    board = state(enemy_health=17)
    board.my_minions = [minion("VAC_926t", attack=3, health=5),
                        minion("VAC_926t", attack=3, health=5),
                        minion("VAC_926t", attack=5, health=6, ready=False)]
    for index, attacker in enumerate(board.my_minions, 1):
        attacker.zone_pos = index
    target = minion("VAC_927", attack=1, health=6)
    target.is_mine = False
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (0, -1)


def test_two_turn_pressure_also_applies_to_hero_face_damage():
    board = state(enemy_health=13)
    board.my_hero.attack = 3
    board.my_hero.damage = 1
    board.my_minions = [minion("VAC_926t", attack=5, health=5, ready=False),
                        minion("VAC_926t", attack=5, health=5, ready=False)]
    board.my_minions[1].zone_pos = 2
    target = minion("UNG_205", attack=2, health=2)
    target.is_mine = False
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (-1, -1)


def test_low_enemy_health_does_not_force_face_when_a_dangerous_trade_wins():
    board = state(enemy_health=10)
    board.my_minions = [minion("VAC_926t", attack=1, health=3)]
    target = minion("UNG_205", attack=5, health=1)
    target.is_mine = False
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (0, 0)


def test_enemy_below_twenty_without_enough_damage_does_not_get_the_race_bonus():
    board = two_turn_pressure_board(enemy_health=19)
    assert board.face_pressure_multiplier == 1


def test_twenty_effective_health_does_not_get_the_race_bonus():
    board = two_turn_pressure_board(enemy_health=13)
    board.oppo_hero.armor = 7
    board.my_minions[1].attack = 20
    assert board.face_pressure_multiplier == 1


def test_two_turn_pressure_cannot_assume_a_taunt_will_disappear():
    board = two_turn_pressure_board()
    board.oppo_minions[0].taunt = True
    assert board.face_pressure_multiplier == 1


def test_two_turn_pressure_is_disabled_against_an_immune_hero():
    board = two_turn_pressure_board()
    board.oppo_hero.immune = True
    assert board.face_pressure_multiplier == 1


def test_visible_enemy_lethal_does_not_increase_the_face_weight():
    board = two_turn_pressure_board()
    board.my_hero.damage = 28
    assert board.face_pressure_multiplier == 1


def test_an_enemy_lifesteal_attacker_prevents_the_extra_race_bonus():
    board = two_turn_pressure_board()
    board.oppo_minions[0].life_steal = True
    assert board.face_pressure_multiplier == 1


def test_log_lifesteal_tag_reaches_the_strategy_snapshot():
    log = LogState()
    log.my_player_id = "1"
    source = CardEntity("UNG_205")
    for tag, value in {"CARDTYPE": "MINION", "ZONE": "PLAY", "CONTROLLER": "2",
                       "ZONE_POSITION": "1", "ATK": "2", "HEALTH": "5",
                       "LIFESTEAL": "1"}.items():
        source.set_tag(tag, value)
    target = generate_strategy_entity(source, log)
    assert target.life_steal


def test_log_deathrattle_tag_reaches_the_strategy_snapshot():
    log = LogState()
    log.my_player_id = "1"
    source = CardEntity("DINO_130")
    for tag, value in {"CARDTYPE": "MINION", "ZONE": "PLAY", "CONTROLLER": "2",
                       "ZONE_POSITION": "1", "ATK": "0", "HEALTH": "2",
                       "DEATHRATTLE": "1"}.items():
        source.set_tag(tag, value)
    target = generate_strategy_entity(source, log)
    assert target.deathrattle


def test_zero_attack_non_taunt_deathrattle_is_not_an_attack_target():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_926t", attack=2, health=3)]
    egg = minion("DINO_130", attack=0, health=2, deathrattle=True)
    egg.is_mine = False
    board.oppo_minions = [egg]
    assert egg not in board.touchable_oppo_minions
    assert board.get_best_attack_target() == (0, -1)


def test_zero_attack_deathrattle_taunt_still_blocks_and_can_be_attacked():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_926t", attack=2, health=3)]
    egg = minion("DINO_130", attack=0, health=2, deathrattle=True, taunt=True)
    egg.is_mine = False
    board.oppo_minions = [egg]
    assert egg in board.touchable_oppo_minions
    assert board.get_best_attack_target() == (0, 0)


def test_zero_attack_non_deathrattle_support_minion_is_still_a_target():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_926t", attack=2, health=3)]
    totem = minion("AT_052", attack=0, health=2)
    totem.is_mine = False
    board.oppo_minions = [totem]
    assert totem in board.touchable_oppo_minions


def test_positive_attack_deathrattle_keeps_normal_target_value():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_926t", attack=2, health=3)]
    target = minion("UNG_205", attack=2, health=2, deathrattle=True)
    target.is_mine = False
    board.oppo_minions = [target]
    assert target in board.touchable_oppo_minions


def test_igneous_heart_does_not_spend_damage_to_hatch_an_egg():
    board = state()
    egg = minion("DINO_130", attack=0, health=2, deathrattle=True)
    egg.is_mine = False
    board.oppo_minions = [egg]
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] == 0


def test_enemy_weapon_damage_can_remove_the_projected_next_turn_attackers():
    board = two_turn_pressure_board()
    board.oppo_weapon = StrategyWeapon("DEEP_014", "PLAY", 0, 0, 0, False, False,
                                       3, 2)
    assert board.face_pressure_multiplier == 1


def test_face_retaliation_reduces_the_projected_surviving_board():
    board = two_turn_pressure_board()
    board.oppo_hero.attack = 4
    assert board.face_pressure_multiplier == 1


def test_poisonous_enemy_attacks_are_not_treated_as_safe_chip_damage():
    board = two_turn_pressure_board()
    board.oppo_minions[0].attack = 1
    board.oppo_minions[0].poisonous = True
    assert board.face_pressure_multiplier == 1


def test_temporary_hero_attack_is_not_repeated_in_the_next_turn_projection():
    board = state(enemy_health=13)
    board.my_hero.attack = 7
    assert board.face_pressure_multiplier == 1


def test_puppet_does_not_keep_the_heros_temporary_attack_next_turn():
    board = state(enemy_health=13)
    board.my_hero.attack = 2
    board.my_minions = [minion("MIS_710", attack=6)]
    assert board.face_pressure_multiplier == 1


def test_next_turn_projection_does_not_rely_on_a_vulnerable_captains_aura():
    board = two_turn_pressure_board()
    captain = minion("CORE_NEW1_027", attack=2, health=2, ready=False)
    captain.zone_pos = 3
    board.my_minions.append(captain)
    assert board.face_pressure_multiplier == 1


def test_random_cannon_damage_is_not_used_to_predict_a_two_turn_finish():
    board = two_turn_pressure_board()
    board.my_minions[0].attack = 4
    board.my_minions[1] = minion("VAC_532", attack=1, health=4, ready=False)
    assert board.face_pressure_multiplier == 1


def hero_removal_board(enemy_health=30):
    board = state(mana=0, enemy_health=enemy_health)
    board.my_hero.attack = 1
    board.my_hero.damage = 1
    board.oppo_minions = [minion("UNG_205", attack=2, health=1)]
    board.oppo_minions[0].is_mine = False
    return board


def test_hero_removes_the_two_one_instead_of_poking_a_full_health_hero():
    board = hero_removal_board()
    cannon = minion("VAC_532", health=4, ready=False)
    puppet = minion("MIS_710", attack=3, ready=False)
    puppet.zone_pos = 2
    puppet.frozen = True
    board.my_minions = [cannon, puppet]
    board.oppo_minions.extend([minion("UNG_809", health=2),
                              minion("UNG_809", health=2)])
    for index, target in enumerate(board.oppo_minions, 1):
        target.is_mine = False
        target.zone_pos = index
    assert board.next_battle_action() == ("attack", -1, 0)


def test_low_enemy_health_does_not_force_a_cheap_hero_attack_to_face():
    board = hero_removal_board(enemy_health=10)
    assert board.get_best_attack_target() == (-1, 0)


def test_hero_removal_preserves_a_friendly_minion_that_would_die_trading():
    board = hero_removal_board()
    board.my_minions = [minion("VAC_926t", health=1)]
    assert board.get_best_attack_target() == (-1, 0)


def test_hero_does_not_remove_a_minion_at_the_cost_of_immediate_death():
    board = hero_removal_board()
    board.my_hero.damage = 28
    assert board.get_best_attack_target() == (-1, -1)


def test_hero_takes_lethal_instead_of_an_efficient_removal():
    board = hero_removal_board(enemy_health=1)
    assert board.get_best_attack_target() == (-1, -1)


def test_hero_does_not_chip_a_surviving_minion_when_face_is_better():
    board = hero_removal_board()
    board.oppo_minions[0].max_health = 3
    assert board.get_best_attack_target() == (-1, -1)


def test_hero_cannot_remove_the_two_one_behind_another_minions_taunt():
    board = hero_removal_board()
    taunt = minion("UNG_809", health=2)
    taunt.taunt = True
    taunt.zone_pos = 2
    taunt.is_mine = False
    board.oppo_minions.append(taunt)
    assert board.get_best_attack_target() == (-1, 1)


def test_aranna_allows_removal_without_paying_retaliation_health():
    board = hero_removal_board()
    board.my_hero.damage = 29
    board.my_minions = [minion("VAC_501", ready=False)]
    assert board.get_best_attack_target() == (-1, 0)


def test_kayn_allows_lethal_through_taunt():
    board = state(enemy_health=3)
    board.my_minions = [minion("BT_187", attack=3)]
    target = minion("VAC_927")
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (0, -1)


def test_pirates_attack_before_hero_to_gain_pufferfist_attack():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_927", ready=False), minion("VAC_926t")]
    board.my_minions[1].zone_pos = 2
    board.my_hero.attack = 2
    assert board.get_best_attack_target() == (1, -1)


def test_puppet_waits_for_pirates_to_increase_hero_attack():
    board = state(enemy_health=10)
    board.my_minions = [minion("MIS_710"), minion("VAC_927", ready=False),
                        minion("VAC_926t")]
    board.my_hero.attack = 1
    assert board.get_best_attack_target() == (2, -1)


def pufferfist_board(enemy_health=30):
    board = state(enemy_health=enemy_health)
    board.my_hero.attack = 5
    board.my_minions = [minion("VAC_927", attack=2, health=2, ready=False),
                        minion("VAC_926t", attack=2, health=2)]
    board.my_minions[1].zone_pos = 2
    return board


def test_a_ready_pirate_attacks_before_the_hero_so_pufferfist_buffs_face_damage():
    board = pufferfist_board()
    assert board.get_best_attack_target() == (1, -1)


def test_pufferfist_pirate_ordering_does_not_replace_a_guaranteed_lethal():
    board = pufferfist_board(enemy_health=5)
    assert board.get_best_attack_target() == (1, -1)


def test_no_ready_pirate_leaves_hero_face_attack_legal():
    board = pufferfist_board()
    board.my_minions[1].exhausted = 1
    assert board.get_best_attack_target() == (-1, -1)


def test_wasted_pufferfist_trigger_does_not_block_face_attack_after_the_hero_attacked():
    board = state(enemy_health=30)
    board.my_hero.exhausted = 1
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_927", attack=2, health=2, ready=False),
                        minion("VAC_926t", attack=2, health=2)]
    assert board.get_best_attack_target() == (1, -1)


def test_combined_trade_does_not_spend_hero_attack_before_a_pirate_buff():
    board = state(mana=0, enemy_health=30)
    board.my_hero.attack = 3
    board.my_minions = [minion("VAC_927", attack=2, health=5, ready=False),
                        minion("VAC_926t", attack=1, health=5)]
    board.my_minions[1].zone_pos = 2
    target = minion("UNG_205", attack=2, health=5)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert board.get_best_combined_trade() == (1, 0)


def test_multi_attack_setup_still_spends_pirate_attack_before_the_hero():
    board = state(mana=0, enemy_health=30)
    board.my_hero.attack = 3
    board.my_minions = [minion("VAC_927", attack=2, health=5, ready=False),
                        minion("VAC_926t", attack=2, health=5),
                        minion("VAC_926t", attack=1, health=5)]
    for pos, body in enumerate(board.my_minions, 1):
        body.zone_pos = pos
    target = minion("UNG_205", attack=2, health=7)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert board.get_best_combined_trade() == (1, 0)


def test_equal_combined_trades_keep_the_pirate_before_the_hero():
    board = state(mana=0, enemy_health=30)
    board.my_hero.attack = 3
    board.my_minions = [minion("VAC_927", attack=2, health=5, ready=False),
                        minion("VAC_926t", attack=1, health=5)]
    board.my_minions[1].zone_pos = 2
    target = minion("UNG_205", attack=2, health=4)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert board.get_best_combined_trade() == (1, 0)


def test_pirate_first_keeps_the_pufferfist_bonus_on_a_lethal_hero_attack():
    from autohs.strategy.combat import combined_trade_gain

    board = state(mana=0, enemy_health=30)
    board.my_hero.attack = 1
    board.my_minions = [minion("VAC_927", attack=2, health=5, ready=False),
                        minion("VAC_926t", attack=2, health=5)]
    board.my_minions[1].zone_pos = 2
    target = minion("UNG_205", attack=2, health=2)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert combined_trade_gain(board, target, (1, -1)) == 2.5
    assert combined_trade_gain(board, target, (-1, 1)) < 2.5
    assert board.get_best_combined_trade() == (1, 0)


def test_pirate_first_order_is_worth_more_than_spending_hero_attack_first():
    from autohs.strategy.combat import combined_trade_gain

    board = state(mana=0, enemy_health=30)
    board.my_hero.attack = 3
    board.my_minions = [minion("VAC_927", attack=2, health=5, ready=False),
                        minion("VAC_926t", attack=2, health=5),
                        minion("VAC_926t", attack=1, health=5)]
    for pos, body in enumerate(board.my_minions, 1):
        body.zone_pos = pos
    target = minion("UNG_205", attack=2, health=8)
    target.is_mine = False
    target.taunt = True
    board.oppo_minions = [target]
    assert combined_trade_gain(board, target, (1, 2, -1)) is not None
    assert combined_trade_gain(board, target, (-1, 1, 2)) is None


def test_wasted_pufferfist_trigger_does_not_block_a_profitable_trade():
    board = state(enemy_health=30)
    board.my_hero.exhausted = 1
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_927", attack=2, health=2, ready=False),
                        minion("VAC_926t", attack=3, health=4)]
    target = minion("UNG_205", attack=2, health=3)
    target.is_mine = False
    board.oppo_minions = [target]
    assert board.get_best_attack_target() == (1, 0)


def test_monkey_attack_trigger_is_counted_as_guaranteed_lethal():
    board = state(enemy_health=3)
    board.my_minions = [minion("VAC_938", ready=False), minion("VAC_926t", attack=2)]
    assert board.guaranteed_face_damage == 3


def test_acupuncture_combines_with_ready_attacks_for_lethal():
    board = state(enemy_health=7)
    board.my_minions = [minion("VAC_926t", attack=3)]
    board.my_hand_cards = [spell("VAC_419")]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] >= 1000


def test_acupuncture_does_not_double_count_enemy_armor():
    board = state(enemy_health=3)
    board.oppo_hero.armor = 1
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] >= 1000


def test_two_acupunctures_can_form_a_mana_affordable_lethal():
    board = state(mana=2, enemy_health=8)
    board.my_hero.exhausted = 1
    board.my_hand_cards = [spell("VAC_419"), spell("VAC_419")]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] >= 1000


def test_two_acupunctures_do_not_claim_lethal_without_enough_mana():
    board = state(mana=1, enemy_health=8)
    board.my_hand_cards = [spell("VAC_419"), spell("VAC_419")]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] == 0


def test_alanna_needle_random_damage_is_not_guaranteed_to_hit_face():
    board = state(mana=1, enemy_health=8)
    board.my_minions = [minion("VAC_501", ready=False)]
    board.oppo_minions = [minion("VAC_532", ready=False)]
    board.my_hand_cards = [spell("VAC_419")]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] < 1000


def test_setup_does_not_claim_lethal_when_enemy_hero_retaliation_is_fatal():
    board = state(mana=1, enemy_health=1)
    board.my_hero.damage = 29
    board.oppo_hero.attack = 3
    assert ID2CARD_DICT["HERO_10cbp"].best_h_and_arg(board, -1)[0] < 1000


def test_silenced_alanna_does_not_allow_suicidal_acupuncture():
    board = state()
    board.my_hero.damage = 29
    alanna = minion("VAC_501")
    alanna.silenced = True
    board.my_minions = [alanna]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] == 0


def test_igneous_heart_does_not_spend_a_friendly_body_after_hero_attacked():
    board = state()
    board.my_hero.exhausted = 1
    board.my_minions = [minion("VAC_926t", attack=3, health=1)]
    assert ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)[0] == 0


def test_igneous_heart_prefers_a_surviving_enemy_for_hero_attack():
    board = state()
    target = minion("VAC_532", health=4)
    target.is_mine = False
    board.oppo_minions = [target]
    board.my_minions = [minion("VAC_532", health=4)]
    score, args = ID2CARD_DICT["DEEP_011"].best_h_and_arg(board, 0)
    assert score > 0
    assert args == ("enemy", 0)


def test_nonfinale_rush_does_not_buff_an_already_ready_attacker():
    board = state(mana=1)
    board.my_minions = [minion("VAC_926t", attack=3)]
    assert ID2CARD_DICT["JAM_017"].best_h_and_arg(board, 0)[0] == 0


def test_finale_rush_buffs_a_ready_attacker_before_face():
    board = state(mana=0, enemy_health=4)
    board.my_minions = [minion("VAC_926t", attack=3)]
    assert ID2CARD_DICT["JAM_017"].best_h_and_arg(board, 0)[0] >= 1000


def test_hero_attack_reopened_location_is_selected_again():
    board = state(mana=0)
    board.my_hero_power.exhausted = 1
    cliff = StrategyLocation("VAC_929", "PLAY", 1, 4, 0, True, False, 3, 1)
    board.my_minions = [cliff]
    assert board.get_best_location_trigger() == (-1, [])
    cliff.exhausted = 0
    assert board.next_battle_action() == ("location", 0, [])


def test_summon_buffer_is_played_before_activating_cliffside():
    board = state()
    board.my_minions = [StrategyLocation("VAC_929", "PLAY", 1, 4, 0, True, False, 3, 0)]
    board.my_hand_cards = [minion("TOY_518", zone="HAND")]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_weapon_is_equipped_before_small_time_buccaneer_attacks():
    board = state(mana=2)
    board.my_minions = [minion("CFM_325", attack=1)]
    board.my_hand_cards = [StrategyWeapon("DEEP_014", "HAND", 1, 2, 0,
                                         True, False, 1, 2)]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_frozen_hero_does_not_spend_mana_on_attack_power():
    board = state()
    board.my_hero.frozen = 1
    assert ID2CARD_DICT["HERO_10cbp"].best_h_and_arg(board, -1)[0] == 0


def test_cheap_power_count_zilliax_is_played_before_ready_attackers():
    board = state(mana=1, enemy_health=15)
    board.my_minions = [minion("VAC_926t", attack=3), minion("VAC_926t", attack=2)]
    board.my_hand_cards = [minion("TOY_330t5", zone="HAND")]
    assert board.best_h_index_arg()[0] == 0


def test_hero_power_does_not_spend_mana_needed_for_a_minion():
    board = state(mana=2)
    body = minion("CFM_325", zone="HAND")
    body.current_cost = 2
    board.my_hand_cards = [body]
    assert board.best_h_index_arg()[0] == 0


def test_hero_power_does_not_spend_mana_needed_for_mining_axe():
    board = state(mana=2)
    board.my_hand_cards = [StrategyWeapon("DEEP_014", "HAND", 1, 2, 0,
                                         True, False, 1, 2)]
    assert board.best_h_index_arg()[0] == 0


def test_mining_axe_still_yields_to_lethal_hero_power():
    board = state(mana=2, enemy_health=1)
    board.my_hand_cards = [StrategyWeapon("DEEP_014", "HAND", 1, 2, 0,
                                         True, False, 1, 2)]
    assert board.best_h_index_arg()[0] == -1


def test_puppet_waits_for_pirate_buffs_even_before_the_low_health_threshold():
    board = state(mana=0, enemy_health=30)
    board.my_minions = [minion("MIS_710", attack=3), minion("VAC_927", ready=False),
                        minion("VAC_926t", attack=1)]
    assert board.get_best_attack_target() == (2, -1)


def test_pilot_is_not_blocked_by_a_location_filling_the_last_two_slots():
    board = state()
    board.my_minions = [minion("VAC_926t", ready=False) for _ in range(4)]
    board.my_minions.append(StrategyLocation("VAC_929", "PLAY", 5, 4, 0, True, False, 3, 0))
    board.my_hand_cards = [minion("VAC_933", zone="HAND")]
    assert board.next_battle_action()[0:2] == ("card", 0)


def test_cliffside_lethal_takes_priority_over_playing_pilot():
    board = state(enemy_health=2)
    board.my_minions = [StrategyLocation("VAC_929", "PLAY", 1, 4, 0, True, False, 3, 0)]
    board.my_hand_cards = [minion("VAC_933", zone="HAND")]
    assert board.next_battle_action() == ("location", 0, [])


def test_cliffside_uses_one_free_slot_for_lethal():
    board = state(mana=0, enemy_health=1)
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_926t", ready=False) for _ in range(5)]
    board.my_minions.append(StrategyLocation("VAC_929", "PLAY", 6, 4, 0, True, False, 3, 0))
    assert board.next_battle_action() == ("location", 5, [])


def test_cliffside_uses_one_free_slot_during_the_low_health_race():
    board = state(mana=0, enemy_health=10)
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_926t", ready=False) for _ in range(5)]
    board.my_minions.append(StrategyLocation("VAC_929", "PLAY", 6, 4, 0, True, False, 3, 0))
    assert board.next_battle_action() == ("location", 5, [])


def test_aranna_does_not_redirect_damage_prevented_by_immunity():
    board = state(enemy_health=8)
    board.my_hero.immune = 1
    board.my_minions = [minion("VAC_501", ready=False)]
    board.my_hand_cards = [spell("VAC_419")]
    assert ID2CARD_DICT["VAC_419"].best_h_and_arg(board, 0)[0] < 1000


def test_kayn_does_not_claim_lethal_against_an_immune_hero():
    board = state(mana=4, enemy_health=1)
    board.oppo_hero.immune = 1
    board.oppo_minions = [minion("VAC_927")]
    board.oppo_minions[0].taunt = True
    kayn = minion("BT_187", attack=3, zone="HAND")
    kayn.current_cost = 4
    board.my_hand_cards = [kayn]
    assert ID2CARD_DICT["BT_187"].best_h_and_arg(board, 0)[0] < 1000


def test_a_pirate_that_dies_to_retaliation_still_triggers_pufferfist():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_927", ready=False), minion("VAC_926t", health=1)]
    board.oppo_hero.attack = 2
    assert board.guaranteed_face_damage == 2


def test_a_dying_attack_buffer_is_not_counted_for_later_pirates():
    board = state(enemy_health=30)
    board.my_minions = [minion("VAC_927", health=1), minion("VAC_926t", health=1)]
    board.oppo_hero.attack = 2
    assert board.guaranteed_face_damage <= 3


def test_a_nonfinale_rush_can_still_enable_a_new_pirate_trade():
    board = state(mana=1)
    board.my_minions = [minion("VAC_926t", attack=3, ready=False)]
    board.oppo_minions = [minion("VAC_927", attack=2)]
    assert ID2CARD_DICT["JAM_017"].best_h_and_arg(board, 0)[0] > 0


def test_four_mana_cliffside_is_not_displaced_by_cannon_and_hero_power():
    board = state(mana=4)
    board.my_minions = [minion("VAC_532"), minion("CORE_NEW1_027", attack=3)]
    cannon = minion("VAC_532", zone="HAND")
    cannon.current_cost = 2
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [cannon, cliff]
    assert board.best_h_index_arg()[0] == 1


def test_cliffside_outweighs_aura_body_with_two_cannons_already_in_play():
    board = state(mana=5)
    board.my_minions = [minion("VAC_532"), minion("VAC_532")]
    zilliax = minion("TOY_330t5", zone="HAND")
    zilliax.current_cost = 5
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [zilliax, cliff]
    assert board.best_h_index_arg()[0] == 1


def test_cliffside_is_not_developed_into_the_last_free_board_slot():
    board = state(mana=4)
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_926t", ready=False) for _ in range(6)]
    board.my_hand_cards = [StrategyLocation("VAC_929", "HAND", 1, 4, 0, True, False, 3, 1)]
    assert board.best_h_index_arg()[0] == -2


def test_dealer_precedes_cliffside_when_five_mana_pays_for_both():
    board = state(mana=5)
    dealer = minion("TOY_518", zone="HAND")
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [cliff, dealer]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_dealer_does_not_use_the_four_mana_needed_for_cliffside():
    board = state(mana=4)
    dealer = minion("TOY_518", zone="HAND")
    cliff = StrategyLocation("VAC_929", "HAND", 2, 4, 0, True, False, 3, 1)
    board.my_hand_cards = [dealer, cliff]
    assert board.next_battle_action()[0:2] == ("card", 1)


def test_mulligan_replaces_expensive_combo_cards_and_needles():
    board = state()
    for cid in ["VAC_419", "VAC_929", "BT_187", "VAC_928", "VAC_501", "TOY_330t5"]:
        assert not ID2CARD_DICT[cid].keep_in_hand(board, 0), cid


def test_mulligan_two_drop_needs_a_one_drop_to_support_the_curve():
    board = state()
    two_drop = minion("VAC_927", zone="HAND")
    two_drop.current_cost = 2
    board.my_hand_cards = [two_drop]
    assert not ID2CARD_DICT["VAC_927"].keep_in_hand(board, 0)
    board.my_hand_cards.append(minion("VAC_933", zone="HAND"))
    assert ID2CARD_DICT["VAC_927"].keep_in_hand(board, 0)


def captain_board(enemy_health=27):
    board = state(mana=0, enemy_health=enemy_health)
    board.my_hero_power.exhausted = 1
    board.my_minions = [minion("VAC_926t", health=1), minion("VAC_926t", health=1)]
    board.my_minions[1].zone_pos = 2
    board.oppo_minions = [minion("CORE_NEW1_027", attack=4, health=2),
                          minion("CORE_NEW1_027", attack=4, health=4),
                          minion("KAR_069", attack=3, health=3)]
    for index, target in enumerate(board.oppo_minions, 1):
        target.zone_pos = index
        target.is_mine = False
    return board


def test_two_small_pirates_combine_to_remove_the_damaged_enemy_captain():
    board = captain_board()
    assert board.get_best_attack_target() == (0, 0)


def test_the_second_small_pirate_finishes_the_captain_instead_of_switching_to_face():
    board = captain_board()
    board.my_minions = board.my_minions[1:]
    board.my_minions[0].zone_pos = 1
    board.oppo_minions[0].damage = 1
    assert board.get_best_attack_target() == (0, 0)


def test_combined_trade_does_not_replace_a_guaranteed_face_lethal():
    board = captain_board(enemy_health=2)
    assert board.get_best_attack_target() == (0, -1)


def test_combined_trade_does_not_start_when_the_available_damage_cannot_kill():
    board = captain_board()
    board.oppo_minions[0].max_health = 4
    assert board.get_best_attack_target() == (0, -1)


def test_combined_trade_does_not_bypass_a_different_minions_taunt():
    board = captain_board()
    board.oppo_minions[2].taunt = True
    board.oppo_minions[2].max_health = 20
    assert board.get_best_attack_target()[1] == 2
