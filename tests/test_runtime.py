import json
import os
import threading

from autohs.app.pause import PauseController


def test_client_pause_is_acknowledged_by_the_same_controller_as_the_hotkey(tmp_path):
    from autohs.app.runtime import RuntimeReporter

    controller = PauseController()
    reporter = RuntimeReporter(tmp_path, controller, lambda: "Battling", "revision-1")
    (tmp_path / "autohs-control.json").write_text(json.dumps({
        "pid": os.getpid(), "id": "pause-1", "action": "pause",
    }))

    reporter.publish()

    record = json.loads((tmp_path / "autohs-runtime.json").read_text())
    assert controller.paused
    assert record["command_id"] == "pause-1"
    assert record["state"] == "paused"
    assert record["revision"] == "revision-1"


def test_hotkey_pause_updates_client_status_without_a_command(tmp_path):
    from autohs.app.runtime import RuntimeReporter

    controller = PauseController()
    reporter = RuntimeReporter(tmp_path, controller, lambda: "Battling", "revision-1")
    controller.toggle()
    reporter.publish()

    assert json.loads((tmp_path / "autohs-runtime.json").read_text())["state"] == "paused"


def test_old_process_command_cannot_resume_current_process(tmp_path):
    from autohs.app.runtime import RuntimeReporter

    controller = PauseController()
    controller.toggle()
    reporter = RuntimeReporter(tmp_path, controller, lambda: "Battling", "revision-1")
    (tmp_path / "autohs-control.json").write_text(json.dumps({
        "pid": os.getpid() + 1, "id": "stale", "action": "start",
    }))
    reporter.publish()

    assert controller.paused


def test_reporter_stops_its_worker_on_exit(tmp_path):
    from autohs.app.runtime import RuntimeReporter

    reporter = RuntimeReporter(tmp_path, PauseController(), lambda: "", "revision-1")
    reporter.start()
    reporter.stop()

    assert not any(t.name == "autohs-runtime" for t in threading.enumerate())


def test_start_cannot_claim_running_without_screen_and_input_permission(tmp_path):
    from autohs.app.runtime import RuntimeReporter

    controller = PauseController()
    reporter = RuntimeReporter(tmp_path, controller, lambda: "", "revision-1",
                               permission_provider=lambda: {"screen": False, "input": True})
    (tmp_path / "autohs-control.json").write_text(json.dumps({
        "pid": os.getpid(), "id": "start-1", "action": "start",
    }))

    reporter.publish()

    record = json.loads((tmp_path / "autohs-runtime.json").read_text())
    assert controller.paused
    assert record["state"] == "needs_permission"
    assert record["permissions"] == {"screen": False, "input": True}
