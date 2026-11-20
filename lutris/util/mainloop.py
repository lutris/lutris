"""The event loop Lutris schedules deferred work on, behind a small interface.

Code outside the UI never talks to a toolkit's loop directly; it goes through
lutris.util.jobs, which uses whatever MainLoop is installed here. The default
runs on GLib, which both frontends use. A frontend using a different event loop
can install its own implementation with set_main_loop().
"""

from collections.abc import Callable
from typing import Protocol

# Called by the loop; returning True asks for it to be called again after the
# same delay, returning False (or None) ends it
LoopCallback = Callable[[], bool | None]


class MainLoop(Protocol):
    """What Lutris needs from an event loop."""

    def schedule(self, callback: LoopCallback, delay_seconds: float) -> object:
        """Call `callback` on the loop's thread after `delay_seconds`, or as soon as
        the loop is idle if the delay is negative. Returns a handle for cancel()."""
        ...

    def cancel(self, handle: object) -> None:
        """Stop a scheduled callback from running (again)."""
        ...

    def iterate(self) -> None:
        """Run one iteration of the loop, waiting for an event if none is pending."""
        ...


class GLibMainLoop:
    """The GLib main loop used by both frontends."""

    def schedule(self, callback: LoopCallback, delay_seconds: float) -> object:
        from gi.repository import GLib

        if delay_seconds < 0.0:
            return GLib.idle_add(callback)
        return GLib.timeout_add(int(delay_seconds * 1000), callback)

    def cancel(self, handle: object) -> None:
        from gi.repository import GLib

        if isinstance(handle, int):
            GLib.source_remove(handle)

    def iterate(self) -> None:
        from gi.repository import GLib

        GLib.MainContext.default().iteration(True)


_main_loop: MainLoop | None = None


def get_main_loop() -> MainLoop:
    """Return the installed main loop, installing the GLib one if there's none yet."""
    global _main_loop
    if _main_loop is None:
        _main_loop = GLibMainLoop()
    return _main_loop


def set_main_loop(main_loop: MainLoop) -> None:
    """Install the main loop deferred work runs on; a frontend does this at startup."""
    global _main_loop
    _main_loop = main_loop


def run_asyncio_on_glib() -> None:
    """Make asyncio run on GLib's main loop, so that the backend's coroutines run while
    a Gio.Application runs. Call this before starting the application."""
    import warnings

    with warnings.catch_warnings():
        # PyGObject's module looks up asyncio's deprecated event loop policy classes
        warnings.simplefilter("ignore", DeprecationWarning)
        from gi.events import GLibEventLoopPolicy

    # This creates the event loop for GLib's default main context, which PyGObject's
    # Gio.Application.run() then runs, without installing the policy (deprecated too)
    GLibEventLoopPolicy().get_event_loop()
