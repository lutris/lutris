# Standard Library
import sys
import threading
import traceback

# Third Party Libraries
from gi.repository import GLib

# Lutris Modules
from lutris.util.log import logger


class AsyncCall(threading.Thread):

    def __init__(self, func, callback, *args, **kwargs):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop.
        """
        self.source_id = None
        self.stop_request = threading.Event()

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

        self.source_id = GLib.idle_add(_make_idle_safe(self.callback), result, error)
        return self.source_id


def synchronized_call(func, event, result):
    """Calls func, stores the result by reference, set an event when finished"""
    result.append(func())
    event.set()


def thread_safe_call(func):
    """Synchronous call to func, safe to call in a callback started from a thread
    Not safe to use otherwise, will crash if run from the main thread.

    See: https://pygobject.readthedocs.io/en/latest/guide/threading.html
    """
    event = threading.Event()
    result = []
    GLib.idle_add(_make_idle_safe(synchronized_call), func, event, result)
    event.wait()
    return result[0]


def _make_idle_safe(function):
    """Wrap a function in another, which just discards its result.
    GLib.idle_add may call the function again if it returns True,
    but this wrapper only returns false."""
    def discarding_result(*args, **kwargs):
        function(*args, **kwargs)
        return False  # ignore result from function
    return discarding_result
