import sys
import threading
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from gi.repository import GLib

from lutris.util.log import logger

if TYPE_CHECKING:
    from gi.repository import Gtk

ResultType = TypeVar("ResultType")


class AsyncCall(threading.Thread):
    def __init__(
        self,
        func: Callable[..., ResultType],
        callback: Callable[[ResultType, Exception], None] | None,
        *args: Any,
        callback_target: "Gtk.Widget | None" = None,
        **kwargs: Any,
    ):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop. If 'callback_target' is a widget and it is destroyed
        in the meantime, the callback is cancelled.
        """
        self.callback_task = None
        self.stop_request = threading.Event()

        super().__init__(target=self.target, args=args, kwargs=kwargs)
        self.function = func
        if not callback:
            self.callback = lambda r, e: None
        else:
            self.callback = self._protect_callback(callback, callback_target)
        self.daemon = kwargs.pop("daemon", True)
        self.start()

    def _protect_callback(
        self, callback: Callable[[Any, Exception], None], callback_target: "Gtk.Widget | None" = None
    ) -> Callable[[Any, Exception], None]:
        """Wraps and hooks up an on-destroyed handler on the callback_target that
        removes the callback; this prevents an AsyncJob from completing on a
        destroyed widget, which can cause a crash.

        If no callback_target is given, this will use the receiver of the callback
        (if it has one)."""
        if not callback_target:
            callback_target = callback.__self__ if hasattr(callback, "__self__") else None

        if callback_target and hasattr(callback_target, "call_when_destroyed"):

            def unhook() -> None:
                # If the target is destroyed, block the callback; no need to disconnect
                # from a dead object.
                self.callback = lambda r, e: None

            def fire(r: Any, e: Exception) -> None:
                # Before starting the callback, unhook the on-destroyed callback
                # so we don't leak it.
                disconnecter()
                callback(r, e)

            disconnecter = callback_target.call_when_destroyed(unhook)
            return fire
        else:
            return callback

    def target(self, *a: Any, **kw: Any) -> None:
        result = None
        error = None

        try:
            result = self.function(*a, **kw)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error while completing task %s: %s %s", self.function, type(ex), ex)
            error = ex
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)

        self.callback_task = schedule_at_idle(self.callback, result, error)


class IdleTask:
    """This class provides a safe interface for cancelling idle tasks and timeouts;
    this will simply do nothing after being used once, and once the task completes,
    it will also do nothing.

    These objects are returned by the schedule methods below, which disconnect
    them when appropriate."""

    def __init__(self) -> None:
        """Initializes a task with no connection to a source, but also not completed; this can be
        connected to a source via the connect() method, unless it is completed first."""
        self.source_id: int | None = None
        self._is_completed = False

    def unschedule(self) -> None:
        """Call this to prevent the idle task from running, if it has not already run."""
        if self.source_id is not None:
            GLib.source_remove(self.source_id)
            self.disconnect()

    def is_completed(self) -> bool:
        """True if the idle task has completed; that is, if mark_completed() was called on it."""
        return self._is_completed

    def connect(self, source_id: int) -> None:
        """Connects this task to a source to be unscheduled; but if the task is already
        completed, this does nothing."""
        if not self._is_completed:
            self.source_id = source_id

    def disconnect(self) -> None:
        """Break the link to the idle task, so it can't be unscheduled."""
        self.source_id = None

    def mark_completed(self) -> None:
        """Marks the task as completed, and also disconnect it."""
        self._is_completed = True
        self.disconnect()


# A task that is always completed and disconnected and does nothing.
COMPLETED_IDLE_TASK = IdleTask()
COMPLETED_IDLE_TASK.mark_completed()


def schedule_at_idle(func: Callable[..., None], *args: Any, delay_seconds: float = 0.0) -> IdleTask:
    """Schedules a function to run at idle time, once. You can specify a delay in seconds
    before it runs.
    Returns an object to prevent it running."""

    task = IdleTask()

    def wrapper(*a: Any, **kw: Any) -> bool:
        try:
            func(*a, **kw)
            return False
        finally:
            task.disconnect()

    handler_object = func.__self__ if hasattr(func, "__self__") else None
    if handler_object:
        wrapper.__self__ = handler_object  # type: ignore[attr-defined]

    if delay_seconds >= 0.0:
        milliseconds = int(delay_seconds * 1000)
        source_id = GLib.timeout_add(milliseconds, wrapper, *args)
    else:
        source_id = GLib.idle_add(wrapper, *args)

    task.connect(source_id)
    return task


def run_until_complete(async_func: Callable[..., None], *args, timeout_seconds: float = 30.0, **kwargs) -> None:
    """Iterate the GLib main context until an async operation completes.

    This is intended for CLI code paths where no main loop is running, or
    where nesting a second GLib.MainLoop would interfere with the
    Gtk.Application lifecycle. The async_func receives two extra keyword
    arguments — ``completion_function`` and ``error_function`` — which it
    must call when the operation finishes.

    Raises whatever exception is passed to error_function, or TimeoutError
    if timeout_seconds elapses first.
    """
    context = GLib.MainContext.default()
    done = False
    error_holder: list[Exception | None] = [None]

    def on_complete() -> None:
        nonlocal done
        done = True

    def on_error(ex: Exception) -> None:
        nonlocal done
        error_holder[0] = ex
        done = True

    deadline = GLib.get_monotonic_time() + int(timeout_seconds * 1_000_000)
    async_func(*args, completion_function=on_complete, error_function=on_error, **kwargs)

    while not done:
        if GLib.get_monotonic_time() >= deadline:
            raise TimeoutError(f"Async operation timed out after {timeout_seconds}s")
        context.iteration(True)

    if error_holder[0]:
        raise error_holder[0]


def schedule_repeating_at_idle(
    func: Callable[..., bool],
    *args: Any,
    interval_seconds: float = 0.0,
) -> IdleTask:
    """Schedules a function to run at idle time, over and over until it returns False.
    It can be repeated at an interval in seconds, which will also delay it's first invocation.
    Returns an object to stop it running."""

    task = IdleTask()

    def wrapper(*a: Any, **kw: Any) -> bool:
        repeat = False
        try:
            repeat = func(*a, **kw)
            return repeat
        finally:
            if not repeat:
                task.disconnect()

    handler_object = func.__self__ if hasattr(func, "__self__") else None
    if handler_object:
        wrapper.__self__ = handler_object  # type: ignore[attr-defined]

    if interval_seconds >= 0.0:
        milliseconds = int(interval_seconds * 1000)
        source_id = GLib.timeout_add(milliseconds, wrapper, *args)
    else:
        source_id = GLib.idle_add(wrapper, *args)

    task.connect(source_id)
    return task
