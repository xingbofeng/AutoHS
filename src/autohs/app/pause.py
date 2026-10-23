"""Local Cmd+Shift+P pause control; importing this module starts no listener.

The FSM catches AutomationPaused, calls pause_controller.wait(), and rebuilds
its battlefield snapshot before deciding on another action. Only that outer
loop should wait: input methods must unwind and release any held buttons.
"""

import threading

from autohs.infrastructure.logging import logger


class AutomationPaused(Exception):
    """Discard the current action and return control to the FSM."""


def _hotkey_pressed():
    import Quartz

    source = Quartz.kCGEventSourceStateHIDSystemState
    key_down = Quartz.CGEventSourceKeyState
    return bool(
        key_down(source, 0x23)  # P
        and (key_down(source, 0x37) or key_down(source, 0x36))  # Command
        and (key_down(source, 0x38) or key_down(source, 0x3C))  # Shift
    )


class PauseController:
    def __init__(self, poll_interval=0.02):
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._poll_interval = poll_interval
        self._condition = threading.Condition()
        self._stopped = threading.Event()
        self._thread = None
        self._paused = False
        self._interrupted = False
        self._error = None

    @property
    def paused(self):
        with self._condition:
            return self._paused

    @property
    def stopped(self):
        """True after stop or listener failure, but not after a wait timeout."""
        return self._stopped.is_set()

    def start(self):
        """Start one polling thread, preserving the current pause state."""
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopped.clear()
            self._error = None
            self._thread = threading.Thread(
                target=self._poll, name="autohs-pause", daemon=True,
            )
            self._thread.start()

    def stop(self):
        """Stop polling, wake waiters, and keep further input disabled."""
        with self._condition:
            self._stopped.set()
            self._condition.notify_all()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    def toggle(self):
        with self._condition:
            self.set_paused(not self._paused)

    def set_paused(self, paused):
        """Use one idempotent pause state for the client and global hotkey."""
        with self._condition:
            if self._paused == paused:
                return
            self._paused = paused
            # Even a quick pause/resume must invalidate the old target.
            self._interrupted = self._interrupted or self._paused
            self._condition.notify_all()
            logger.info("自动操作已暂停" if self._paused else "自动操作已继续")

    def checkpoint(self):
        """Raise immediately on pause, unacknowledged interruption, or stop."""
        with self._condition:
            if self._stopped.is_set():
                raise AutomationPaused("Pause listener stopped") from self._error
            if self._paused or self._interrupted:
                raise AutomationPaused("Discard the interrupted action")

    def wait(self, timeout=None):
        """Acknowledge resume in the outer loop; False means timeout or stop.

        A True result requires a fresh battlefield read before further input.
        """
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._stopped.is_set() or not self._paused,
                timeout=timeout,
            )
            if not ready or self._stopped.is_set():
                return False
            self._interrupted = False
            return True

    def _poll(self):
        held = False
        try:
            while not self._stopped.is_set():
                pressed = _hotkey_pressed()
                with self._condition:
                    if self._stopped.is_set():
                        return
                    if pressed and not held:
                        self.toggle()
                    held = pressed
                self._stopped.wait(self._poll_interval)
        except Exception as error:  # noqa: BLE001 - Fail closed at the worker boundary.
            # A failed listener must wake the FSM and prevent unchecked input.
            with self._condition:
                self._error = error
                self._stopped.set()
                self._condition.notify_all()


pause_controller = PauseController()
