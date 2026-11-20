"""Shared pytest setup.

Pin the GTK/GDK versions before any test module is imported: modules that stub
gi.repository or import lutris GUI code can otherwise load GTK 4 before
gi.require_version("Gtk", "3.0") runs, breaking every GTK 3 import after it.
"""

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from collections.abc import Callable  # noqa: E402

import pytest  # noqa: E402

from lutris.util import mainloop  # noqa: E402


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
