from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("action,index,args", [
    ("attack", -1, -1), ("card", 0, []), ("location", 0, []),
])
def test_battle_executes_the_ordered_strategy_action(monkeypatch, action, index, args):
    from autohs.app import fsm

    log = SimpleNamespace(
        is_end=False, is_my_turn=True, game_num_turns_in_play=3, pending_choice=None,
        my_entity=SimpleNamespace(query_tag=lambda tag: "LOST"),
    )
    executed = []

    def execute(*arguments):
        executed.append((action, *arguments))
        log.is_end = True

    strategy = SimpleNamespace(
        debug_print_out=lambda: None,
        next_battle_action=lambda: (action, index, args),
        use_best_entity=execute,
        my_entity_attack_oppo=execute,
        my_minions=[SimpleNamespace(detail_card=SimpleNamespace(
            location_trigger=lambda state, position, arguments: execute(position, arguments),
        ))],
    )
    monkeypatch.setattr(fsm, "log_state", log)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "StrategyState", lambda log: strategy)
    monkeypatch.setattr(fsm, "update_log_state", lambda: True)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(wait_battlefield_stable=lambda *a: None))
    monkeypatch.setattr(fsm.autohs_config, "give_up_with_dignity", False)
    monkeypatch.setattr(fsm.autohs_config, "emoj_ratio", 0)

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert executed == [(action, index, args)]


def test_resume_discards_the_interrupted_action_and_reads_the_screen_again(monkeypatch):
    from autohs.app import fsm, pause

    control = pause.PauseController()
    events = []
    reads = []
    monkeypatch.setattr(fsm, "pause_controller", control, raising=False)
    monkeypatch.setattr(control, "start", lambda: events.append("start"))
    monkeypatch.setattr(control, "stop", lambda: events.append("stop"))
    original_wait = control.wait

    def resume():
        control.toggle()
        return original_wait(timeout=0)

    def dispatch(scene):
        events.append(scene)
        if len(reads) == 1:
            control.toggle()
            control.checkpoint()
        fsm.quitting_flag = True
        return scene

    monkeypatch.setattr(control, "wait", resume)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "FSM_state", "")
    monkeypatch.setattr(fsm, "PLATFORM", "Darwin")
    monkeypatch.setattr(fsm, "get_state", lambda: (reads.append("read") or fsm.FSM_BATTLING))
    monkeypatch.setattr(fsm, "log_state", SimpleNamespace(available=True))
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(test_hs_available=lambda: False))
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(
        game=SimpleNamespace(cancelClick=lambda: events.append("cancel")),
    ))
    monkeypatch.setattr(fsm, "FSM_dispatch", dispatch)

    fsm.AutoHS_automata()

    assert reads == ["read", "read"]
    assert events == ["start", fsm.FSM_BATTLING, "cancel", fsm.FSM_BATTLING, "stop"]
    control.checkpoint()


def test_known_log_state_wins_over_a_stale_mulligan_screenshot(monkeypatch):
    from autohs.app import fsm

    reads = []
    monkeypatch.setattr(fsm, "log_state", SimpleNamespace(
        available=True, is_end=False, game_entity_id=1, game_num_turns_in_play=1,
        game_step="MAIN_READY",
    ))
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        get_state=lambda: reads.append("screen") or fsm.FSM_CHOOSING_CARD,
    ))
    monkeypatch.setattr(fsm.autohs_config, "has_loading_screen", False)

    assert fsm.get_state() == fsm.FSM_BATTLING
    assert reads == []


def test_mulligan_choice_keeps_the_log_state_before_the_first_turn(monkeypatch):
    from autohs.app import fsm

    monkeypatch.setattr(fsm, "log_state", SimpleNamespace(
        available=True, is_end=False, game_entity_id=1, game_num_turns_in_play=0,
        game_step="BEGIN_MULLIGAN",
    ))
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        get_state=lambda: fsm.FSM_CHOOSING_CARD,
    ))
    monkeypatch.setattr(fsm.autohs_config, "has_loading_screen", False)

    assert fsm.get_state() == fsm.FSM_CHOOSING_CARD


def test_new_game_without_a_step_waits_for_mulligan_instead_of_clicking(monkeypatch):
    from autohs.app import fsm

    monkeypatch.setattr(fsm, "log_state", SimpleNamespace(
        available=True, is_end=False, game_entity_id=1, game_num_turns_in_play=0, game_step="",
    ))
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        get_state=lambda: fsm.FSM_CHOOSING_CARD,
    ))
    monkeypatch.setattr(fsm.autohs_config, "has_loading_screen", False)

    assert fsm.get_state() == fsm.FSM_WAIT_MAIN_MENU


def test_finished_match_does_not_hide_the_deck_selection_screen(monkeypatch):
    from autohs.app import fsm
    from autohs.logs.state import GameEntity, LogState

    log = LogState()
    game = GameEntity()
    game.set_tag("STATE", "COMPLETE")
    game.set_tag("STEP", "FINAL_GAMEOVER")
    game.set_tag("NUM_TURNS_IN_PLAY", "12")
    log.set_game_entity("1", game)
    monkeypatch.setattr(fsm, "log_state", log)
    monkeypatch.setattr(fsm.autohs_config, "has_loading_screen", False)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        get_state=lambda: fsm.FSM_CHOOSING_HERO,
    ))

    assert fsm.get_state() == fsm.FSM_CHOOSING_HERO


def test_resume_activates_hearthstone_before_reading_and_clicking_again(monkeypatch):
    from autohs.app import fsm, pause

    control = pause.PauseController()
    events = []
    dispatched = []
    monkeypatch.setattr(fsm, "pause_controller", control)
    monkeypatch.setattr(control, "start", lambda: None)
    monkeypatch.setattr(control, "stop", lambda: None)
    original_wait = control.wait

    def resume():
        control.set_paused(False)
        return original_wait(timeout=0)

    def dispatch(scene):
        dispatched.append(scene)
        if len(dispatched) == 1:
            control.toggle()
            control.checkpoint()
        fsm.quitting_flag = True
        return scene

    monkeypatch.setattr(control, "wait", resume)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "FSM_state", "")
    monkeypatch.setattr(fsm, "PLATFORM", "Darwin")
    monkeypatch.setattr(fsm.time, "sleep", lambda duration: None)
    monkeypatch.setattr(fsm, "get_state", lambda: (events.append("read") or fsm.FSM_BATTLING))
    monkeypatch.setattr(fsm, "log_state", SimpleNamespace(available=True))
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(
        test_hs_available=lambda: True,
        get_HS_hwnd=lambda: 123,
        move_window_foreground=lambda pid: events.append("foreground"),
    ))
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(game=SimpleNamespace(
        cancelClick=lambda: events.append("cancel"),
    )))
    monkeypatch.setattr(fsm, "FSM_dispatch", dispatch)

    fsm.AutoHS_automata()

    assert events == ["foreground", "read", "foreground", "cancel", "read"]


def test_battle_does_not_end_a_productive_turn_after_twenty_actions(monkeypatch):
    from autohs.app import fsm

    log = SimpleNamespace(
        is_end=False, is_my_turn=True, game_num_turns_in_play=3, pending_choice=None,
        my_entity=SimpleNamespace(query_tag=lambda tag: "LOST"),
    )
    attacks = []
    ended = []

    def attack(index, target):
        attacks.append((index, target))
        log.is_end = len(attacks) == 22

    strategy = SimpleNamespace(
        debug_print_out=lambda: None,
        next_battle_action=lambda: ("attack", len(attacks) % 7, -1),
        my_entity_attack_oppo=attack,
    )
    monkeypatch.setattr(fsm, "log_state", log)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "update_log_state", lambda: True)
    monkeypatch.setattr(fsm, "StrategyState", lambda log: strategy)
    monkeypatch.setattr(fsm, "window_utils", SimpleNamespace(wait_battlefield_stable=lambda *a: None))
    monkeypatch.setattr(fsm, "controller", SimpleNamespace(game=SimpleNamespace(
        endTurn=lambda: ended.append(True), commitErrorReport=lambda: None, cancelClick=lambda: None,
    )))
    monkeypatch.setattr(fsm.time, "sleep", lambda duration: None)
    monkeypatch.setattr(fsm.autohs_config, "give_up_with_dignity", False)
    monkeypatch.setattr(fsm.autohs_config, "emoj_ratio", 0)

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(attacks) == 22
    assert ended == []


@pytest.fixture
def confirmed_battle(monkeypatch):
    from autohs.app import fsm, pause
    from autohs.logs.state import Entity, GameEntity, LogState, PlayerEntity

    log = LogState()
    game = GameEntity()
    game.tag_dict.update(STATE="RUNNING", NUM_TURNS_IN_PLAY="3")
    log.set_game_entity("1", game)
    player = PlayerEntity()
    player.tag_dict.update(CURRENT_PLAYER="1", PLAYSTATE="LOST")
    log.add_player_entity("2", "1", player)
    log.my_player_id = "1"
    actor = Entity()
    actor.tag_dict.update(
        CONTROLLER="1",
        CARDTYPE="MINION",
        ZONE="PLAY",
        ZONE_POSITION="1",
        NUM_ATTACKS_THIS_TURN="0",
        EXHAUSTED="0",
    )
    log.add_entity("10", actor)
    battle = SimpleNamespace(
        log=log,
        actor=actor,
        now=0.0,
        inputs=[],
        ends=[],
        cancels=[],
        reads=0,
        action=("attack", 0, -1),
        on_read=lambda: None,
        on_input=lambda: None,
    )

    def execute(index, args):
        battle.inputs.append((battle.now, index, args))
        battle.on_input()

    def strategy(state):
        return SimpleNamespace(
            debug_print_out=lambda: None,
            next_battle_action=lambda: battle.action,
            use_best_entity=execute,
            my_entity_attack_oppo=execute,
            my_minions=[
                SimpleNamespace(
                    detail_card=SimpleNamespace(
                        location_trigger=lambda state, index, args: execute(
                            index, args
                        ),
                    )
                )
                for entity in state.entity_dict.values()
                if entity.query_tag("ZONE") == "PLAY"
                and entity.query_tag("CARDTYPE") in ("MINION", "LOCATION")
            ],
        )

    def read():
        battle.reads += 1
        assert battle.reads < 500, "Confirmation or retry loop did not terminate"
        battle.on_read()
        return True

    def sleep(duration):
        assert duration > 0
        battle.now += duration

    monkeypatch.setattr(fsm, "log_state", log)
    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "pause_controller", pause.PauseController())
    monkeypatch.setattr(fsm, "StrategyState", strategy)
    monkeypatch.setattr(fsm, "update_log_state", read)
    monkeypatch.setattr(
        fsm, "window_utils", SimpleNamespace(wait_battlefield_stable=lambda *a: None)
    )
    monkeypatch.setattr(
        fsm,
        "controller",
        SimpleNamespace(
            game=SimpleNamespace(
                endTurn=lambda: battle.ends.append(True),
                giveUpRoutine=lambda: pytest.fail(
                    "An unconfirmed action must not concede"
                ),
                cancelClick=lambda: battle.cancels.append(battle.now),
            )
        ),
    )
    monkeypatch.setattr(fsm.time, "monotonic", lambda: battle.now)
    monkeypatch.setattr(fsm.time, "sleep", sleep)
    monkeypatch.setattr(
        fsm.time, "time", lambda: pytest.fail("Use a monotonic deadline")
    )
    monkeypatch.setattr(fsm.autohs_config, "give_up_with_dignity", False)
    monkeypatch.setattr(fsm.autohs_config, "emoj_ratio", 0)
    fsm.clear_decision()
    return battle


@pytest.mark.parametrize("action", ["attack", "card", "location"])
def test_unconfirmed_input_waits_then_pauses_without_ending_turn(
    confirmed_battle, action
):
    from autohs.app import fsm

    battle = confirmed_battle
    battle.action = (action, 0, -1 if action == "attack" else [])
    if action == "card":
        battle.actor.tag_dict["ZONE"] = "HAND"
    elif action == "location":
        battle.actor.tag_dict.update(CARDTYPE="LOCATION", HEALTH="3")

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert len(battle.inputs) == 3
    assert battle.now >= 2
    assert all(
        right[0] - left[0] >= 2 for left, right in zip(battle.inputs, battle.inputs[1:])
    )
    assert battle.cancels
    assert battle.ends == []


def test_delayed_attack_confirmation_does_not_click_again_during_animation(
    confirmed_battle,
):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if battle.inputs and battle.now >= 0.6:
            battle.actor.set_tag("NUM_ATTACKS_THIS_TURN", "1")
            battle.action = ("end", -1, [])

    battle.on_read = read
    battle.ends = []
    fsm.controller.game.endTurn = lambda: (
        battle.ends.append(True),
        battle.log.game_entity.set_tag("STATE", "COMPLETE"),
    )

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1
    assert battle.ends == [True]
    assert battle.now >= 0.6


def test_twenty_two_identical_card_decisions_on_different_entities_are_productive(
    confirmed_battle,
):
    from autohs.app import fsm
    from autohs.logs.state import Entity

    battle = confirmed_battle
    battle.action = ("card", 0, [])
    battle.actor.set_tag("ZONE", "HAND")

    def read():
        if not battle.inputs:
            return
        for entity in battle.log.entity_dict.values():
            if entity.query_tag("ZONE") == "HAND":
                entity.set_tag("ZONE", "GRAVEYARD")
        if len(battle.inputs) == 22:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")
        else:
            entity = Entity()
            entity.tag_dict.update(battle.actor.tag_dict, ZONE="HAND")
            battle.log.entity_dict[str(10 + len(battle.inputs))] = entity

    # Only acknowledge each input once, independently of the number of polls.
    acknowledged = []

    def acknowledge():
        if len(acknowledged) < len(battle.inputs):
            acknowledged.append(True)
            read()

    battle.on_read = acknowledge

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 22
    assert battle.ends == []


def test_unrelated_updates_do_not_reset_the_failure_budget(confirmed_battle):
    from autohs.app import fsm

    battle = confirmed_battle
    battle.on_read = lambda: battle.log.game_entity.set_tag(
        "DEBUG_SEQUENCE", str(battle.reads)
    )

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert len(battle.inputs) == 3
    assert battle.ends == []


@pytest.mark.parametrize("transition", ["turn", "game", "new_turn"])
def test_confirmation_stops_on_turn_or_game_transition(confirmed_battle, transition):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if not battle.inputs:
            return
        if transition == "game":
            battle.log.game_entity.set_tag("STATE", "COMPLETE")
        elif len(battle.inputs) == 1:
            battle.log.game_entity.set_tag("NUM_TURNS_IN_PLAY", "5")
            battle.log.my_entity.set_tag("CURRENT_PLAYER", "0")
            battle.action = ("end", -1, [])
            if transition == "new_turn":
                battle.log.my_entity.set_tag("CURRENT_PLAYER", "1")
        if battle.reads > 12:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read
    fsm.controller.game.endTurn = lambda: battle.log.game_entity.set_tag(
        "STATE", "COMPLETE"
    )

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1
    assert battle.cancels == []


def test_pause_during_confirmation_unwinds_before_any_retry(confirmed_battle):
    from autohs.app import fsm, pause

    battle = confirmed_battle

    def read():
        if battle.inputs:
            fsm.pause_controller.set_paused(True)

    battle.on_read = read
    with pytest.raises(pause.AutomationPaused):
        fsm.Battling()
    assert len(battle.inputs) == 1
    assert battle.ends == []


def test_retry_rebuilds_indices_from_the_current_entities(
    confirmed_battle, monkeypatch
):
    from autohs.app import fsm
    from autohs.logs.state import Entity

    battle = confirmed_battle
    other = Entity()
    other.tag_dict.update(battle.actor.tag_dict, ZONE_POSITION="2")
    battle.log.add_entity("11", other)
    old_cancel = fsm.controller.game.cancelClick

    def cancel():
        old_cancel()
        battle.actor.set_tag("ZONE_POSITION", "2")
        other.set_tag("ZONE_POSITION", "1")
        battle.action = ("attack", 1, -1)

    fsm.controller.game.cancelClick = cancel

    def read():
        if len(battle.inputs) == 2:
            battle.actor.set_tag("EXHAUSTED", "1")
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read
    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert [entry[1] for entry in battle.inputs] == [0, 1]
    assert len(battle.cancels) == 1


def test_late_confirmation_after_timeout_prevents_a_second_input(confirmed_battle):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if battle.cancels:
            battle.actor.set_tag("EXHAUSTED", "1")
            battle.action = ("end", -1, [])

    battle.on_read = read
    fsm.controller.game.endTurn = lambda: battle.log.game_entity.set_tag(
        "STATE", "COMPLETE"
    )

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1
    assert len(battle.cancels) == 1


def test_confirmation_failure_does_not_fall_through_to_end_turn(confirmed_battle):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if battle.cancels:
            battle.action = ("end", -1, [])

    battle.on_read = read
    fsm.controller.game.endTurn = lambda: (
        battle.ends.append(True),
        battle.log.game_entity.set_tag("STATE", "COMPLETE"),
    )

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert len(battle.inputs) == 1
    assert battle.ends == []


@pytest.mark.parametrize("stage", ["before_input", "confirmation"])
def test_failed_log_read_never_retries_or_ends_turn(
    confirmed_battle, monkeypatch, stage
):
    from autohs.app import fsm

    battle = confirmed_battle
    original_read = fsm.update_log_state

    def read():
        if stage == "before_input" and battle.reads >= 2:
            return False
        if stage == "confirmation" and battle.inputs:
            return False
        return original_read()

    monkeypatch.setattr(fsm, "update_log_state", read)
    assert fsm.Battling() == fsm.FSM_ERROR
    assert not fsm.pause_controller.paused
    assert len(battle.inputs) == (stage == "confirmation")
    assert battle.ends == []
    assert battle.cancels == []


def test_quit_arriving_during_pre_input_read_prevents_input(confirmed_battle):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if battle.reads == 3:
            fsm.quitting_flag = True

    battle.on_read = read
    assert fsm.Battling() is None
    assert battle.inputs == []


def test_pending_discover_yields_to_choice_and_then_confirms_the_original_action(
    confirmed_battle, monkeypatch
):
    from autohs.app import fsm

    battle = confirmed_battle
    battle.action = ("card", -1, [])
    battle.actor.tag_dict.update(CARDTYPE="HERO_POWER", EXHAUSTED="0")
    choices = []

    def read():
        if battle.inputs and not choices:
            battle.log.choices["5"] = {
                "choice_id": "5",
                "attempts": 0,
                "ready": True,
                "owner": "1",
                "kind": "GENERAL",
                "minimum": 1,
                "maximum": 1,
                "entities": ["20", "21"],
            }

    def choose(index, count):
        choices.append((index, count))
        battle.log.choices.clear()
        battle.actor.set_tag("EXHAUSTED", "1")
        battle.action = ("end", -1, [])

    battle.on_read = read
    monkeypatch.setattr(fsm, "choose_discover_index", lambda log, choice: 1)
    fsm.controller.cards = SimpleNamespace(chooseScreenCard=choose)
    fsm.controller.game.endTurn = lambda: battle.log.game_entity.set_tag(
        "STATE", "COMPLETE"
    )

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1
    assert choices == [(1, 2)]


def test_unconfirmed_discover_does_not_make_the_turn_look_complete(
    confirmed_battle, monkeypatch
):
    from autohs.app import fsm

    battle = confirmed_battle
    battle.action = ("card", -1, [])
    battle.actor.tag_dict.update(CARDTYPE="HERO_POWER", EXHAUSTED="0")
    choices = []

    def read():
        if battle.inputs and not choices:
            battle.log.choices["5"] = {
                "choice_id": "5",
                "attempts": 0,
                "ready": True,
                "owner": "1",
                "kind": "GENERAL",
                "minimum": 1,
                "maximum": 1,
                "entities": ["20", "21"],
            }

    def choose(index, count):
        choices.append((index, count))
        battle.log.choices.clear()
        battle.action = ("end", -1, [])

    battle.on_read = read
    monkeypatch.setattr(fsm, "choose_discover_index", lambda log, choice: 0)
    fsm.controller.cards = SimpleNamespace(chooseScreenCard=choose)
    fsm.controller.game.endTurn = lambda: (
        battle.ends.append(True),
        battle.log.game_entity.set_tag("STATE", "COMPLETE"),
    )

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert battle.ends == []


def test_stale_strategy_metadata_is_bounded_without_clicking(
    confirmed_battle, monkeypatch
):
    from autohs.app import fsm

    battle = confirmed_battle
    battle.action = ("card", 0, [])
    battle.actor.card_id = "NEW_CARD"
    battle.actor.set_tag("ZONE", "HAND")
    monkeypatch.setattr(
        fsm,
        "StrategyState",
        lambda log: SimpleNamespace(
            debug_print_out=lambda: None,
            next_battle_action=lambda: battle.action,
            my_hand_cards=[SimpleNamespace(card_id="OLD_CARD")],
            use_best_entity=lambda *args: pytest.fail("Must replan before clicking"),
        ),
    )
    assert fsm.Battling() == fsm.FSM_BATTLING
    assert not fsm.pause_controller.paused
    assert battle.inputs == []
    assert 3 <= battle.now <= 3.1
    assert 10 < battle.reads < 100
    assert battle.ends == []


@pytest.mark.parametrize("next_action", ["retry", "end"])
def test_other_successful_entities_do_not_erase_an_unconfirmed_action(
    confirmed_battle, next_action
):
    from autohs.app import fsm
    from autohs.logs.state import Entity

    battle = confirmed_battle
    other = Entity()
    other.tag_dict.update(battle.actor.tag_dict, ZONE_POSITION="2")
    battle.log.add_entity("11", other)
    old_cancel = fsm.controller.game.cancelClick

    def cancel():
        old_cancel()
        battle.action = ("attack", 1, -1)

    def read():
        if battle.inputs and battle.inputs[-1][1] == 1:
            successful = sum(index == 1 for _, index, _ in battle.inputs)
            other.set_tag("NUM_ATTACKS_THIS_TURN", str(successful))
            battle.action = (
                ("attack", 0, -1) if next_action == "retry" else ("end", -1, [])
            )
        if len(battle.inputs) >= 8:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read
    fsm.controller.game.cancelClick = cancel
    fsm.controller.game.endTurn = lambda: (
        battle.ends.append(True),
        battle.log.game_entity.set_tag("STATE", "COMPLETE"),
    )

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert sum(index == 0 for _, index, _ in battle.inputs) <= 3
    assert battle.ends == []


@pytest.mark.parametrize("miss_first_input", [False, True])
def test_confirmed_attacks_by_the_same_entity_can_continue_past_twenty_actions(
    confirmed_battle, miss_first_input
):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        successful = len(battle.inputs) - int(miss_first_input)
        if successful > 0:
            battle.actor.set_tag("NUM_ATTACKS_THIS_TURN", str(successful))
        if successful == 22:
            battle.action = ("end", -1, [])

    battle.on_read = read
    fsm.controller.game.endTurn = lambda: (
        battle.ends.append(True),
        battle.log.game_entity.set_tag("STATE", "COMPLETE"),
    )

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 22 + int(miss_first_input)
    assert battle.ends == [True]
    assert len(battle.cancels) == int(miss_first_input)


def test_pre_input_board_change_replans_instead_of_clicking_a_stale_index(
    confirmed_battle, monkeypatch
):
    from autohs.app import fsm
    from autohs.logs.state import Entity

    battle = confirmed_battle
    other = Entity()
    other.tag_dict.update(battle.actor.tag_dict, ZONE_POSITION="2")
    battle.log.add_entity("11", other)
    original_strategy = fsm.StrategyState

    def strategy(log):
        result = original_strategy(log)
        position = int(battle.actor.query_tag("ZONE_POSITION")) - 1
        result.next_battle_action = lambda: ("attack", position, -1)
        return result

    def read():
        if battle.reads == 3:
            battle.actor.set_tag("ZONE_POSITION", "2")
            other.set_tag("ZONE_POSITION", "1")
        if battle.inputs:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read
    monkeypatch.setattr(fsm, "StrategyState", strategy)
    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert [index for _, index, _ in battle.inputs] == [1]


@pytest.mark.parametrize("action", ["attack", "card", "location"])
def test_pre_input_target_combat_change_replans_before_clicking(
    confirmed_battle, monkeypatch, action
):
    from autohs.app import fsm
    from autohs.logs.state import Entity

    battle = confirmed_battle
    if action == "card":
        battle.actor.tag_dict.update(CARDTYPE="SPELL", ZONE="HAND")
    elif action == "location":
        battle.actor.set_tag("CARDTYPE", "LOCATION")
    target = Entity()
    target.tag_dict.update(
        CARDTYPE="MINION",
        CONTROLLER="2",
        ZONE="PLAY",
        ZONE_POSITION="1",
        TAUNT="0",
    )
    battle.log.add_entity("11", target)
    original_strategy = fsm.StrategyState
    decisions = []

    def strategy(log):
        result = original_strategy(log)
        target_index = 0 if target.query_tag("TAUNT") == "1" else -1
        args = target_index if action == "attack" else [target_index]

        def decide():
            decisions.append(args)
            return action, 0, args

        result.next_battle_action = decide
        return result

    def read():
        if battle.reads == 3:
            target.set_tag("TAUNT", "1")
        if battle.inputs:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read
    monkeypatch.setattr(fsm, "StrategyState", strategy)

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    expected = [-1, 0] if action == "attack" else [[-1], [0]]
    assert decisions == expected
    assert [args for _, _, args in battle.inputs] == [expected[-1]]
    assert battle.cancels == []


def test_actor_timestamps_changing_on_each_read_do_not_block_legitimate_input(
    confirmed_battle,
):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        battle.actor.set_tag("TIMESTAMP", str(battle.reads))
        if battle.inputs:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1


def test_successive_parsed_combat_updates_settle_before_input(confirmed_battle):
    from autohs.app import fsm
    from autohs.logs.power import parse_line
    from autohs.logs.state import Entity, update_state

    battle = confirmed_battle
    enemy = Entity()
    enemy.tag_dict.update(
        CARDTYPE="MINION",
        CONTROLLER="2",
        ZONE="PLAY",
        ZONE_POSITION="1",
        HEALTH="5",
    )
    battle.log.add_entity("11", enemy)

    def read():
        if battle.reads in (3, 5, 7):
            event = parse_line(
                "D 13:30:00.0000000 GameState.DebugPrintPower() - "
                f"TAG_CHANGE Entity=11 tag=DAMAGE value={(battle.reads - 1) // 2} "
            )
            assert event is not None
            update_state(battle.log, event)
        if battle.inputs:
            battle.log.game_entity.set_tag("STATE", "COMPLETE")

    battle.on_read = read

    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert enemy.query_tag("DAMAGE") == "3"
    assert len(battle.inputs) == 1
    assert 0 < battle.now < 3
    assert not fsm.pause_controller.paused
    assert battle.ends == []
    assert battle.cancels == []


def test_persistent_combat_updates_yield_a_fresh_snapshot_without_input(
    confirmed_battle,
):
    from autohs.app import fsm
    from autohs.logs.power import parse_line
    from autohs.logs.state import Entity, update_state

    battle = confirmed_battle
    enemy = Entity()
    enemy.tag_dict.update(
        CARDTYPE="MINION",
        CONTROLLER="2",
        ZONE="PLAY",
        ZONE_POSITION="1",
        HEALTH="500",
    )
    battle.log.add_entity("11", enemy)

    def read():
        event = parse_line(
            "D 13:30:00.0000000 GameState.DebugPrintPower() - "
            f"TAG_CHANGE Entity=11 tag=DAMAGE value={battle.reads} "
        )
        assert event is not None
        update_state(battle.log, event)

    battle.on_read = read

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert 3 <= battle.now <= 3.1
    assert not fsm.pause_controller.paused
    assert battle.inputs == []
    assert battle.ends == []
    assert battle.cancels == []

    # The caller can obtain a fresh strategy after the combat updates stop.
    battle.on_read = lambda: None
    battle.on_input = lambda: battle.log.game_entity.set_tag("STATE", "COMPLETE")
    assert fsm.Battling() == fsm.FSM_QUITTING_BATTLE
    assert len(battle.inputs) == 1


def test_unconfirmed_input_is_not_forgotten_when_later_snapshots_stay_stale(
    confirmed_battle,
):
    from autohs.app import fsm

    battle = confirmed_battle

    def read():
        if battle.cancels:
            battle.actor.set_tag("ATK", str(battle.reads))

    battle.on_read = read

    assert fsm.Battling() == fsm.FSM_BATTLING
    assert fsm.pause_controller.paused
    assert len(battle.inputs) == 1
    assert 6 <= battle.now <= 6.1
    assert battle.ends == []
