import sys
import threading
import traceback
from typing import Callable

from gi.repository import GLib

from lutris.util.log import logger


class AsyncCall(threading.Thread):
    def __init__(self, func, callback, *args, **kwargs):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop.
        """
        self.callback_unscheduler = None
        self.stop_request = threading.Event()

        super().__init__(target=self.target, args=args, kwargs=kwargs)
        self.function = func
        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop("daemon", True)

        self.start()

    def target(self, *a, **kw):
        result = None
        error = None

        try:
            result = self.function(*a, **kw)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error while completing task %s: %s %s", self.function, type(ex), ex)
            error = ex
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)

        schedule_at_idle(self.callback, result, error)


class Unscheduler:
    """This class provides a safe interface for cancelling idle tasks and timeouts;
    this will simply do nothing after being used once, and once the task completes,
    it will also do nothing.

    These objects are returned by the schedule methods below, which disconnect
    them when appropriate."""

    def __init__(self, source_id: int = None) -> None:
        self.source_id = source_id
        self._is_completed = source_id is None

    def unschedule(self) -> None:
        """Call this to prevent the idle task from running, if it has not already run."""
        if self.is_connected():
            GLib.source_remove(self.source_id)
            self.disconnect()

    def is_connected(self) -> bool:
        """True if the idle task can still be unscheduled. If false, unschedule() will do nothing."""
        return self.source_id is not None

    def is_completed(self) -> bool:
        """True if the idle task has completed; that is, if mark_completed() was called on it."""
        return self._is_completed

    def disconnect(self) -> None:
        """Break the link to the idle task, so it can't be unscheduled."""
        self.source_id = None

    def mark_completed(self) -> None:
        """Marks the unscheduler as completed, and also disconnect it."""
        self._is_completed = True
        self.disconnect()


# An unscheduler that is always completed and disconnected and does nothing.
COMPLETED_UNSCHEDULER = Unscheduler(None)


def schedule_at_idle(func: Callable[..., None], *args, delay_seconds: float = 0.0) -> Unscheduler:
    """Schedules a function to run at idle time, once. You can specify a delay in seconds
    before it runs.
    Returns an object to prevent it running."""

    def wrapper(*a, **kw) -> bool:
        try:
            func(*a, **kw)
            return False
        finally:
            unscheduler.disconnect()

    if delay_seconds >= 0.0:
        milliseconds = int(delay_seconds * 1000)
        source_id = GLib.timeout_add(milliseconds, wrapper, *args)
    else:
        source_id = GLib.idle_add(wrapper, *args)

    unscheduler = Unscheduler(source_id)
    return unscheduler


def schedule_repeating_at_idle(
    func: Callable[..., bool],
    *args,
    interval_seconds: float = 0.0,
) -> Unscheduler:
    """Schedules a function to run at idle time, over and over until it returns False.
    It can be repeated at an interval in seconds, which will also delay it's first invocation.
    Returns an object to stop it running."""

    def wrapper(*a, **kw) -> bool:
        repeat = False
        try:
            repeat = func(*a, **kw)
            return repeat
        finally:
            if not repeat:
                unscheduler.disconnect()

    if interval_seconds >= 0.0:
        milliseconds = int(interval_seconds * 1000)
        source_id = GLib.timeout_add(milliseconds, wrapper, *args)
    else:
        source_id = GLib.idle_add(wrapper, *args)

    unscheduler = Unscheduler(source_id)
    return unscheduler
