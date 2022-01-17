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
        self.completion_callback_args = None
        self.start()

    def await_completion(self, timeout):
        """Block waiting for the call to complete for a time.
        If it completes in time,  invokes the callback synchronously
        and returns True. Returns False if it times out."""
        self.join(timeout)
        if not self.is_alive():
            self.complete()
            return True
        return False

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

        self.completion_callback_args = [result, error]
        self.source_id = GLib.idle_add(self.complete)
        return self.source_id

    def complete(self):
        callback_args = self.completion_callback_args
        if callback_args is not None:
            # Make sure we don't call the callback twice, even if
            # await_completion succeeds.
            self.completion_callback_args = None
            self.callback(*callback_args)

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
    GLib.idle_add(synchronized_call, func, event, result)
    event.wait()
    return result[0]
