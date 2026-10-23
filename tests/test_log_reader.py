from autohs.logs.reader import log_iter_func


def test_restart_boundary_does_not_skip_a_match_created_before_first_read(tmp_path):
    log = tmp_path / "Power.log"
    log.write_text("finished match\n")
    iterator = log_iter_func(str(log), "Power.log", str.strip, start_at_end=True)
    with log.open("a") as handle:
        handle.write("CREATE_GAME\nGameEntity EntityID=1\n")

    try:
        assert next(iterator).message_list == ["CREATE_GAME", "GameEntity EntityID=1"]
    finally:
        iterator.close()


def test_file_created_before_first_read_keeps_initial_entities(tmp_path):
    iterator = log_iter_func(str(tmp_path / "Power.log"), "Power.log", str.strip, start_at_end=True)
    (tmp_path / "Power.log").write_text("CREATE_GAME\nGameEntity EntityID=1\n")

    try:
        assert next(iterator).message_list == ["CREATE_GAME", "GameEntity EntityID=1"]
    finally:
        iterator.close()


def test_new_session_before_first_read_does_not_apply_old_file_offset(tmp_path):
    old_session = tmp_path / "Hearthstone_1"
    old_session.mkdir()
    (old_session / "Power.log").write_text("old game\n" * 20)
    iterator = log_iter_func(str(tmp_path), "Power.log", str.strip, start_at_end=True)
    new_session = tmp_path / "Hearthstone_2"
    new_session.mkdir()
    (new_session / "Power.log").write_text("CREATE_GAME\nGameEntity EntityID=1\n")

    try:
        assert next(iterator).message_list == ["CREATE_GAME", "GameEntity EntityID=1"]
    finally:
        iterator.close()


def test_mid_match_replay_keeps_events_written_before_next_update(tmp_path, monkeypatch):
    from autohs.app import fsm
    from autohs.logs.state import LogState

    session = tmp_path / "Hearthstone_1"
    session.mkdir()
    log = session / "Power.log"
    prefix = "D 08:23:19.9576520 GameState.DebugPrintPower() - "
    log.write_text(prefix + "CREATE_GAME\n" + prefix + "    GameEntity EntityID=1\n")
    monkeypatch.setattr(fsm, "PLATFORM", "Test")
    monkeypatch.setattr(fsm, "hearthstone_log_dir", lambda root: str(tmp_path))
    monkeypatch.setattr(fsm, "log_state", LogState())
    monkeypatch.setattr(fsm, "log_iter", None)

    fsm.bootstrap_log_state()
    with log.open("a") as handle:
        handle.write(prefix + "    TAG_CHANGE Entity=GameEntity tag=NUM_TURNS_IN_PLAY value=3 \n")

    try:
        assert fsm.update_log_state()
        assert fsm.log_state.game_num_turns_in_play == 3
    finally:
        fsm.log_iter.close()


def test_starting_during_mulligan_recovers_entities_created_before_start(tmp_path, monkeypatch):
    from autohs.app import fsm
    from autohs.logs.state import LogState

    session = tmp_path / "Hearthstone_1"
    session.mkdir()
    prefix = "D 08:23:19.9576520 GameState.DebugPrintPower() - "
    (session / "Power.log").write_text(
        prefix + "CREATE_GAME\n" + prefix + "    GameEntity EntityID=1\n"
        + prefix + "    tag=STATE value=RUNNING\n"
        + prefix + "    tag=STEP value=BEGIN_MULLIGAN\n"
    )
    monkeypatch.setattr(fsm, "PLATFORM", "Test")
    monkeypatch.setattr(fsm, "hearthstone_log_dir", lambda root: str(tmp_path))
    monkeypatch.setattr(fsm, "log_state", LogState())
    monkeypatch.setattr(fsm, "log_iter", None)
    monkeypatch.setattr(fsm, "log_iter_loading_screen", None)
    monkeypatch.setattr(fsm, "last_state_in_log", fsm.SCREEN_MODE_STARTUP)
    monkeypatch.setattr(fsm, "loading_screen_mode_seen", False)
    monkeypatch.setattr(fsm, "choose_hero_count", 0)

    fsm.init()
    try:
        assert fsm.update_log_state()
        assert fsm.get_state() == fsm.FSM_CHOOSING_CARD
    finally:
        fsm.log_iter.close()
        fsm.log_iter_loading_screen.close()


def test_running_reader_switches_to_a_new_session_after_first_read(tmp_path, monkeypatch):
    import autohs.logs.reader as reader

    monkeypatch.setattr(reader.time, 'sleep', lambda _: None)
    old = tmp_path / 'Hearthstone_1'; old.mkdir()
    (old / 'Power.log').write_text('old game\n')
    iterator = log_iter_func(str(tmp_path), 'Power.log', str.strip)
    try:
        assert next(iterator).message_list == ['old game']
        new = tmp_path / 'Hearthstone_2'; new.mkdir()
        (new / 'Power.log').write_text('CREATE_GAME\nGameEntity EntityID=1\n')
        assert next(iterator).message_list == ['CREATE_GAME', 'GameEntity EntityID=1']
    finally:
        iterator.close()


def test_rotated_file_with_the_same_name_is_read_from_the_start(tmp_path, monkeypatch):
    import autohs.logs.reader as reader

    monkeypatch.setattr(reader.time, 'sleep', lambda _: None)
    path = tmp_path / 'Power.log'; path.write_text('old game\n')
    iterator = log_iter_func(str(path), 'Power.log', str.strip)
    try:
        assert next(iterator).message_list == ['old game']
        replacement = tmp_path / 'replacement'; replacement.write_text('CREATE_GAME\n')
        replacement.replace(path)
        assert next(iterator).message_list == ['CREATE_GAME']
    finally:
        iterator.close()


def test_new_session_waits_for_its_log_instead_of_reading_the_old_game(tmp_path, monkeypatch):
    import autohs.logs.reader as reader
    from autohs.constants import LOG_CONTAINER_ERROR

    monkeypatch.setattr(reader.time, 'sleep', lambda _: None)
    old = tmp_path / 'Hearthstone_1'; old.mkdir()
    (old / 'Power.log').write_text('old game\n')
    iterator = log_iter_func(str(tmp_path), 'Power.log', str.strip)
    try:
        assert next(iterator).message_list == ['old game']
        new = tmp_path / 'Hearthstone_2'; new.mkdir()
        assert next(iterator).log_type == LOG_CONTAINER_ERROR
        (new / 'Power.log').write_text('CREATE_GAME\n')
        assert next(iterator).message_list == ['CREATE_GAME']
    finally:
        iterator.close()
