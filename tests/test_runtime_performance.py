from types import SimpleNamespace

import numpy as np


def test_idle_log_tail_returns_quickly_for_action_confirmation(tmp_path, monkeypatch):
    import autohs.logs.reader as reader

    delays = []
    monkeypatch.setattr(reader.time, "sleep", delays.append)
    log = tmp_path / "Power.log"
    log.write_text("")
    iterator = reader.log_iter_func(str(log), "Power.log", str.strip)
    try:
        assert next(iterator).message_list == []
    finally:
        iterator.close()
    assert delays and all(delay <= 0.05 for delay in delays)


def test_action_confirmation_polls_quickly(monkeypatch):
    from autohs.app import fsm

    delays = []
    checks = 0

    class Attempt:
        def same_context(self, log):
            return True

        def confirmed(self, log):
            nonlocal checks
            checks += 1
            return checks > 1

    monkeypatch.setattr(fsm, "quitting_flag", False)
    monkeypatch.setattr(fsm, "update_log_state", lambda: True)
    monkeypatch.setattr(fsm.pause_controller, "checkpoint", lambda: None)
    monkeypatch.setattr(fsm.time, "sleep", delays.append)

    assert fsm._wait_for_action_confirmation(Attempt()) == "confirmed"
    assert delays and max(delays) <= 0.05


def test_untargeted_spell_keeps_a_shortened_nonzero_wait(monkeypatch):
    from autohs.behaviors import basic
    from autohs.config import autohs_config

    delays = []
    calls = []
    fake_controller = SimpleNamespace(
        cards=SimpleNamespace(
            selectAndUseHandCard=lambda index, count: calls.append((index, count)),
        ),
    )
    monkeypatch.setattr(basic, "clicks", lambda: fake_controller)
    monkeypatch.setattr(basic.time, "sleep", delays.append)

    basic.SpellNoPoint.use_with_arg(
        SimpleNamespace(my_hand_card_num=3), 1,
    )

    assert calls == [(1, 3)]
    assert delays == [autohs_config.basic_spell_wait_time]
    assert 0 < delays[0] < 1.5


def test_action_waits_are_shortened_without_removing_settle_time():
    from autohs.behaviors.basic import (
        HeroPowerCard,
        MinionCard,
        SpellCard,
        WeaponCard,
    )
    from autohs.behaviors.detail import Hysteria, HolySmite

    assert 0 < MinionCard.wait_time < 0.8
    assert 0 < SpellCard.wait_time < 1.5
    assert 0 < WeaponCard.wait_time < 1
    assert 0 < HeroPowerCard.wait_time < 1
    assert 0 < HolySmite.wait_time < 2
    assert 0 < Hysteria.wait_time < 5


def test_mouse_click_uses_short_predictable_motion(monkeypatch):
    import autohs.execution.mouse as mouse

    motion = []
    holds = []
    monkeypatch.setattr(mouse.sys, "platform", "darwin")
    monkeypatch.setattr(mouse.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(
        mouse.pyautogui, "moveTo",
        lambda position, duration, tween: motion.append((position, duration, tween)),
    )
    monkeypatch.setattr(mouse.pyautogui, "mouseDown", lambda *args: None)
    monkeypatch.setattr(mouse.pyautogui, "mouseUp", lambda *args: None)
    monkeypatch.setattr(mouse.time, "sleep", holds.append)

    mouse.MouseController().mouseClickPosition([200, 300])

    assert motion[0][1] <= 0.1
    assert motion[0][2] is mouse.pyautogui.easeInOutQuad
    assert max(holds, default=0) <= 0.1


def test_mouse_drag_and_automatic_pause_are_short(monkeypatch):
    import autohs.execution.mouse as mouse

    holds = []
    monkeypatch.setattr(mouse.sys, "platform", "darwin")
    monkeypatch.setattr(mouse.pyautogui, "position", lambda: (100, 100))
    monkeypatch.setattr(mouse.pyautogui, "moveTo", lambda *args, **kwargs: None)
    monkeypatch.setattr(mouse.pyautogui, "mouseDown", lambda *args: None)
    monkeypatch.setattr(mouse.pyautogui, "mouseUp", lambda *args: None)
    monkeypatch.setattr(mouse.time, "sleep", holds.append)

    mouse.MouseController().mouseDragToPosition([200, 300])

    assert max(holds, default=0) <= 0.15
    assert mouse.pyautogui.PAUSE <= 0.05


def test_battlefield_stability_polling_is_short(monkeypatch):
    import skimage.metrics

    from autohs.desktop import capture
    from autohs.desktop.coordinates import COORDINATES_1920_1080

    delays = []
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    monkeypatch.setattr(capture, "take_snapshot", lambda: image)
    monkeypatch.setattr(skimage.metrics, "structural_similarity", lambda *args, **kwargs: 1)
    monkeypatch.setattr(capture.time, "sleep", delays.append)

    capture.wait_battlefield_stable(
        SimpleNamespace(click_coordinates=COORDINATES_1920_1080),
    )

    assert delays and max(delays) <= 0.2
