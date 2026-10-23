"""Share the runner's real pause state and accept local client commands."""

import json
import os
import sys
import threading
import time
from pathlib import Path

from autohs.infrastructure.logging import logger


def desktop_permissions():
    if sys.platform != "darwin":
        return {"screen": True, "input": True}
    import Quartz

    return {"screen": bool(Quartz.CGPreflightScreenCaptureAccess()),
            "input": bool(Quartz.CGPreflightPostEventAccess())}


class RuntimeReporter:
    def __init__(self, root, controller, phase_provider, revision,
                 permission_provider=desktop_permissions):
        root = Path(root)
        self.state_path = root / "autohs-runtime.json"
        self.control_path = root / "autohs-control.json"
        self.controller = controller
        self.phase_provider = phase_provider
        self.revision = revision
        self.command_id = None
        self.permission_provider = permission_provider
        self.permissions = {}
        self._permission_check = float("-inf")
        self._stopped = threading.Event()
        self._thread = None

    def publish(self):
        if time.monotonic() - self._permission_check >= 1:
            self.permissions = self.permission_provider()
            self._permission_check = time.monotonic()
        ready = all(self.permissions.values())
        try:
            command = json.loads(self.control_path.read_text())
        except (OSError, ValueError):
            command = {}
        if (isinstance(command, dict) and command.get("pid") == os.getpid()
                and isinstance(command.get("id"), str)
                and command.get("id") != self.command_id
                and command.get("action") in ("pause", "start")):
            self.controller.set_paused(command["action"] == "pause" or not ready)
            self.command_id = command["id"]
        if not ready:
            self.controller.set_paused(True)
        record = {
            "pid": os.getpid(),
            "state": ("needs_permission" if not ready else
                      "paused" if self.controller.paused else "running"),
            "permissions": self.permissions,
            "phase": self.phase_provider(),
            "revision": self.revision,
            "command_id": self.command_id,
            "updated_at": time.time(),
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record))
        temporary.replace(self.state_path)

    def start(self):
        self.publish()
        self._thread = threading.Thread(target=self._run, name="autohs-runtime", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stopped.wait(0.1):
            try:
                self.publish()
            except OSError:
                logger.exception("Cannot update the local launcher status")
                return

    def stop(self):
        self._stopped.set()
        if self._thread is not None:
            self._thread.join()
