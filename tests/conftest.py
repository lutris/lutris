"""Shared pytest setup."""

from collections.abc import Callable

import pytest

from lutris.util import mainloop


class FakeMainLoop:
    """A main loop driven by hand: run_pending() runs whatever is due."""

    def __init__(self) -> None:
        self.scheduled: dict[int, tuple[mainloop.LoopCallback, float]] = {}
        self.cancelled: list[int] = []
        self._next_handle = 1
        self.on_iterate: Callable[[], None] = lambda: None

    def schedule(self, callback: mainloop.LoopCallback, delay_seconds: float) -> object:
        handle = self._next_handle
        self._next_handle += 1
        self.scheduled[handle] = (callback, delay_seconds)
        return handle

    def cancel(self, handle: object) -> None:
        assert isinstance(handle, int)
        self.cancelled.append(handle)
        self.scheduled.pop(handle, None)

    def iterate(self) -> None:
        self.on_iterate()
        self.run_pending()

    def run_pending(self) -> None:
        for handle, (callback, _delay) in list(self.scheduled.items()):
            if not callback():
                self.scheduled.pop(handle, None)


@pytest.fixture
def fake_main_loop(monkeypatch):
    """Install a FakeMainLoop for the test, in place of GLib's."""
    loop = FakeMainLoop()
    monkeypatch.setattr(mainloop, "_main_loop", loop)
    return loop
