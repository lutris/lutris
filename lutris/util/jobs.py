import sys
import traceback
import threading
from gi.repository import GLib

from lutris.util.log import logger


class AsyncCall(threading.Thread):

    def __init__(self, func, callback=None, *args, **kwargs):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop.
        """
        self.source_id = None
        self.stop_request = threading.Event()

        super(AsyncCall, self).__init__(target=self.target, args=args, kwargs=kwargs)
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
            logger.error("Error while completing task %s: %s", self.function, ex)
            error = ex
            ex_type, ex_value, trace = sys.exc_info()
            print(ex_type, ex_value)
            traceback.print_tb(trace)

        self.source_id = GLib.idle_add(self.callback, result, error)
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
    GLib.idle_add(synchronized_call, func, event, result)
    event.wait()
    return result[0]
