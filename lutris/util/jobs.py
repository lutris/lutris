import asyncio
import sys
import threading
import traceback

from gi.repository import GLib

from lutris.util.log import logger


class AsyncCall(threading.Thread):

    def __init__(self, func, callback, *args, **kwargs):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop.
        """
        self.source_id = None
        self.stop_request = threading.Event()

        if not func:
            raise ValueError("AsyncCall func argument can't be None.")

        super().__init__(target=self.target, args=args, kwargs=kwargs)
        self.function = func
        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop("daemon", True)

        self.start()

    def target(self, *args, **kwargs):
        result = None
        error = None

        try:
            result = self.function(*args, **kwargs)
        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error while completing task %s: %s %s", self.function, type(ex), ex)
            error = ex
            _ex_type, _ex_value, trace = sys.exc_info()
            traceback.print_tb(trace)

        self.source_id = schedule_at_idle(self.callback, result, error)
        return self.source_id


_main_loop = None


def init_main_loop():
    global _main_loop
    _main_loop = asyncio.get_running_loop()


def get_main_loop():
    if not _main_loop:
        raise RuntimeError("The main loop has not been started yet.")
    return _main_loop


async def call_async(func, *args, **kwargs):
    def on_complete(r, e):
        if e:
            completed.set_exception(e)
        elif not completed.cancelled():
            completed.set_result(r)

    completed = get_main_loop().create_future()
    AsyncCall(func, on_complete, *args, **kwargs)
    return await completed


def synchronized_call(func, event, result):
    """Calls func, stores the result by reference, set an event when finished"""
    result.append(func())
    event.set()


def schedule_at_idle(func, *args):
    return GLib.idle_add(_make_idle_safe(func), *args)


async def execute_at_idle_async(func, *args, **kwargs):
    """Runs a function at idle time; await this to obtain the
    result or exception."""

    def execute():
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as ex:
            future.set_exception(ex)

        return False  # do not repeat

    future = get_main_loop().create_future()
    GLib.idle_add(execute)
    return await future


def _make_idle_safe(function):
    """Wrap a function in another, which just discards its result.
    GLib.idle_add may call the function again if it returns True,
    but this wrapper only returns false."""

    def discarding_result(*args, **kwargs):
        function(*args, **kwargs)
        return False  # ignore result from function

    # This is a hack, but if 'function' is a method the
    # exception handling will want to know what it's __self__ was,
    # so we'll just paste it right on here.

    if hasattr(function, "__self__"):
        discarding_result.__self__ = function.__self__
    return discarding_result
