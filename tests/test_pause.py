import importlib
import importlib.util
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def pause_module():
    if importlib.util.find_spec("autohs.app.pause") is None:
        pytest.fail("The independent pause API has not been implemented")
    return importlib.import_module("autohs.app.pause")


def wait_for(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline, "Timed out waiting for the worker"
        threading.Event().wait(0.001)


def test_checkpoint_allows_input_before_listener_start():
    pause = pause_module()
    controller = pause.PauseController()
    assert not controller.paused
    controller.checkpoint()
    assert controller.wait(timeout=0)


def test_pause_unwinds_the_old_target_instead_of_waiting_inside_checkpoint():
    pause = pause_module()
    controller = pause.PauseController()
    actions = []
    controller.toggle()

    with pytest.raises(pause.AutomationPaused):
        controller.checkpoint()
        actions.append("old target")

    assert controller.paused
    assert actions == []


def test_quick_resume_still_invalidates_the_old_target_until_main_thread_waits():
    pause = pause_module()
    controller = pause.PauseController()
    controller.toggle()
    controller.toggle()

    assert not controller.paused
    with pytest.raises(pause.AutomationPaused):
        controller.checkpoint()
    assert controller.wait(timeout=0)
    controller.checkpoint()


def test_wait_blocks_until_resume():
    pause = pause_module()
    controller = pause.PauseController()
    controller.toggle()
    result = []
    finished = threading.Event()

    def wait():
        result.append(controller.wait())
        finished.set()

    waiter = threading.Thread(target=wait, daemon=True)
    waiter.start()
    try:
        assert not finished.wait(0.02)
        controller.toggle()
        assert finished.wait(2)
        assert result == [True]
        controller.checkpoint()
    finally:
        controller.stop()
        waiter.join(2)


def test_wait_timeout_does_not_resume_or_acknowledge_pause():
    pause = pause_module()
    controller = pause.PauseController()
    controller.toggle()

    assert not controller.wait(timeout=0.01)
    assert controller.paused
    with pytest.raises(pause.AutomationPaused):
        controller.checkpoint()


def test_stop_wakes_waiters_without_allowing_old_input():
    pause = pause_module()
    controller = pause.PauseController()
    controller.toggle()
    result = []
    entered = threading.Event()

    def wait():
        entered.set()
        result.append(controller.wait())

    waiter = threading.Thread(target=wait, daemon=True)
    waiter.start()
    assert entered.wait(2)
    controller.stop()
    waiter.join(2)

    assert not waiter.is_alive()
    assert result == [False]
    with pytest.raises(pause.AutomationPaused):
        controller.checkpoint()


def test_stop_is_idempotent_before_start():
    controller = pause_module().PauseController()
    controller.stop()
    controller.stop()
    assert not controller.wait(timeout=0)


def test_listener_toggles_once_per_chord_press_not_once_per_poll(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController(poll_interval=0.001)
    keys = iter([False, True, True, True, False, True, True, False])
    observed = []
    sampled = threading.Event()

    def hotkey_pressed():
        try:
            pressed = next(keys)
        except StopIteration:
            sampled.set()
            return False
        observed.append(controller.paused)
        return pressed

    monkeypatch.setattr(pause, "_hotkey_pressed", hotkey_pressed)
    controller.start()
    try:
        assert sampled.wait(2)
        assert observed == [False, False, True, True, True, True, False, False]
        assert not controller.paused
        with pytest.raises(pause.AutomationPaused):
            controller.checkpoint()
        assert controller.wait(timeout=0)
        controller.checkpoint()
    finally:
        controller.stop()


def test_start_is_idempotent_and_stop_joins_the_listener(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController(poll_interval=0.001)
    workers = set()
    samples = []

    def hotkey_pressed():
        workers.add(threading.current_thread())
        samples.append(False)
        return False

    monkeypatch.setattr(pause, "_hotkey_pressed", hotkey_pressed)
    controller.start()
    try:
        wait_for(lambda: len(samples) >= 2)
        controller.start()
        wait_for(lambda: len(samples) >= 4)
    finally:
        controller.stop()
    assert len(workers) == 1
    assert not next(iter(workers)).is_alive()
    assert not controller.wait(timeout=0)


def test_stop_interrupts_the_poll_interval_and_allows_restart(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController(poll_interval=30)
    sampled = threading.Event()
    workers = []

    def hotkey_pressed():
        workers.append(threading.current_thread())
        sampled.set()
        return False

    monkeypatch.setattr(pause, "_hotkey_pressed", hotkey_pressed)
    controller.start()
    try:
        assert sampled.wait(2)
        started = time.monotonic()
        controller.stop()
        assert time.monotonic() - started < 1
        assert not workers[0].is_alive()
        sampled.clear()
        controller.start()
        assert sampled.wait(2)
        assert workers[0] is not workers[-1]
        assert controller.wait(timeout=0)
        controller.checkpoint()
    finally:
        controller.stop()


def test_listener_failure_wakes_waiters_and_prevents_input(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController(poll_interval=0.001)
    failure = RuntimeError("key state unavailable")

    def hotkey_pressed():
        raise failure

    monkeypatch.setattr(pause, "_hotkey_pressed", hotkey_pressed)
    controller.toggle()
    controller.start()
    try:
        assert not controller.wait(timeout=2)
        with pytest.raises(pause.AutomationPaused) as caught:
            controller.checkpoint()
        assert caught.value.__cause__ is failure
    finally:
        controller.stop()


@pytest.mark.parametrize("interval", [0, -0.1])
def test_poll_interval_must_be_positive(interval):
    with pytest.raises(ValueError):
        pause_module().PauseController(poll_interval=interval)


def test_stopped_distinguishes_pause_timeout_from_stop_and_failure(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController()
    assert not controller.stopped
    controller.toggle()
    assert not controller.wait(timeout=0)
    assert not controller.stopped
    controller.stop()
    assert controller.stopped
    assert not controller.wait(timeout=0)

    monkeypatch.setattr(pause, "_hotkey_pressed", Mock(side_effect=RuntimeError("failed")))
    controller.start()
    try:
        wait_for(lambda: controller.stopped)
        assert not controller.wait(timeout=0)
    finally:
        controller.stop()


def test_toggle_logs_one_state_message_per_transition(monkeypatch):
    pause = pause_module()
    logger = Mock()
    monkeypatch.setattr(pause, "logger", logger)
    controller = pause.PauseController()
    controller.toggle()
    controller.toggle()
    assert [call.args for call in logger.info.call_args_list] == [
        ("自动操作已暂停",), ("自动操作已继续",),
    ]


def test_pause_button_is_idempotent_and_resume_discards_old_targets():
    pause = pause_module()
    controller = pause.PauseController()
    controller.set_paused(True)
    controller.set_paused(True)
    assert controller.paused
    controller.set_paused(False)
    with pytest.raises(pause.AutomationPaused):
        controller.checkpoint()
    assert controller.wait(timeout=0)
    controller.checkpoint()


@pytest.mark.parametrize("command", [0x36, 0x37])
@pytest.mark.parametrize("shift", [0x38, 0x3C])
def test_hotkey_accepts_either_command_and_shift_key(monkeypatch, command, shift):
    pause = pause_module()
    pressed = {0x23, command, shift}
    reads = []

    def key_state(source, key):
        reads.append((source, key))
        return key in pressed

    monkeypatch.setitem(sys.modules, "Quartz", SimpleNamespace(
        CGEventSourceKeyState=key_state, kCGEventSourceStateHIDSystemState=1,
    ))

    assert pause._hotkey_pressed()
    assert all(source == 1 for source, _ in reads)
    assert {key for _, key in reads} <= {0x23, 0x36, 0x37, 0x38, 0x3C}


@pytest.mark.parametrize("pressed", [set(), {0x23}, {0x37, 0x38},
                                         {0x23, 0x37}, {0x23, 0x38}])
def test_incomplete_hotkey_does_not_toggle(monkeypatch, pressed):
    pause = pause_module()
    monkeypatch.setitem(sys.modules, "Quartz", SimpleNamespace(
        CGEventSourceKeyState=lambda source, key: key in pressed,
        kCGEventSourceStateHIDSystemState=1,
    ))
    assert not pause._hotkey_pressed()


@pytest.fixture
def mouse_environment(monkeypatch):
    pause = pause_module()
    controller = pause.PauseController()
    monkeypatch.setattr(pause, "pause_controller", controller)
    pointer = Mock(FAILSAFE=False, FAILSAFE_POINTS=[(0, 0)])
    pointer.position.return_value = (100, 100)
    pointer.size.return_value = (1920, 1080)
    monkeypatch.setitem(sys.modules, "pyautogui", pointer)
    spec = importlib.util.find_spec("autohs.execution.mouse")
    module_spec = importlib.util.spec_from_file_location("pause_test_mouse", spec.origin)
    mouse = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(mouse)
    monkeypatch.setattr(mouse, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(mouse, "time", SimpleNamespace(sleep=Mock()))
    return mouse, pointer, controller, pause


@pytest.mark.parametrize("method,args", [
    ("mouseMoveToPosition", ((20, 30),)),
    ("mouseDragToPosition", ((20, 30),)),
    ("mouseClickPosition", ((20, 30),)),
    ("mouseRightClickPosition", ((20, 30),)),
    ("positionClickPosition", ((20, 30), (40, 50))),
])
def test_paused_input_has_no_mouse_side_effects(mouse_environment, method, args):
    mouse, pointer, controller, pause = mouse_environment
    controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        getattr(mouse.MouseController(), method)(*args)
    assert pointer.mock_calls == []


@pytest.mark.parametrize("method", ["mouseClickPosition", "mouseRightClickPosition"])
def test_pause_during_move_prevents_click(mouse_environment, method):
    mouse, pointer, controller, pause = mouse_environment
    pointer.moveTo.side_effect = lambda *args, **kwargs: controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        getattr(mouse.MouseController(), method)((20, 30))
    pointer.mouseDown.assert_not_called()
    pointer.rightClick.assert_not_called()


def test_pause_after_drag_mouse_down_always_releases_button(mouse_environment):
    mouse, pointer, controller, pause = mouse_environment
    pointer.mouseDown.side_effect = controller.toggle
    with pytest.raises(pause.AutomationPaused):
        mouse.MouseController().mouseDragToPosition((20, 30))
    pointer.moveTo.assert_not_called()
    pointer.mouseUp.assert_called_once_with()


@pytest.mark.parametrize("method", ["mouseClickPosition", "mouseDragToPosition"])
def test_pause_while_button_held_releases_before_unwinding(mouse_environment, method):
    mouse, pointer, controller, pause = mouse_environment
    mouse.time.sleep.side_effect = lambda duration: controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        getattr(mouse.MouseController(), method)((20, 30))
    pointer.mouseUp.assert_called_once()
    assert controller.paused


@pytest.mark.parametrize("method", ["mouseClickPosition", "mouseDragToPosition"])
def test_other_errors_while_button_held_still_release(mouse_environment, method):
    mouse, pointer, _controller, _pause = mouse_environment
    mouse.time.sleep.side_effect = RuntimeError("input failed")
    with pytest.raises(RuntimeError, match="input failed"):
        getattr(mouse.MouseController(), method)((20, 30))
    pointer.mouseUp.assert_called_once()


def test_pause_between_target_clicks_discards_enemy_target(mouse_environment):
    mouse, pointer, controller, pause = mouse_environment
    pointer.mouseUp.side_effect = lambda *args: controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        mouse.MouseController().positionClickPosition((20, 30), (40, 50))
    assert pointer.moveTo.call_count == 1
    pointer.mouseDown.assert_called_once_with((20, 30))
    pointer.mouseUp.assert_called_once_with((20, 30))


def test_pause_during_failsafe_recovery_restores_failsafe(mouse_environment):
    mouse, pointer, controller, pause = mouse_environment
    pointer.FAILSAFE = True
    pointer.position.return_value = (0, 0)
    pointer.moveTo.side_effect = lambda *args, **kwargs: controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        mouse.MouseController().mouseMoveToPosition((20, 30))
    pointer.moveTo.assert_called_once_with(960, 540)
    assert pointer.FAILSAFE


@pytest.mark.parametrize("method", ["mouseDragToPosition", "mouseClickPosition",
                                    "mouseRightClickPosition"])
def test_non_macos_input_also_checks_pause(mouse_environment, monkeypatch, method):
    mouse, pointer, controller, pause = mouse_environment
    monkeypatch.setattr(mouse, "sys", SimpleNamespace(platform="win32"))
    controller.toggle()
    with pytest.raises(pause.AutomationPaused):
        getattr(mouse.MouseController(), method)((20, 30))
    assert pointer.mock_calls == []
