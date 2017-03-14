import sys
import traceback
import threading
from gi.repository import GLib

from lutris.util.log import logger


class AsyncCall(threading.Thread):
    def __init__(self, function, callback=None, *args, **kwargs):
        """Execute `function` in a new thread then schedule `callback` for
        execution in the main loop.
        """
        self.stop_request = threading.Event()

        super(AsyncCall, self).__init__(target=self.target, args=args,
                                        kwargs=kwargs)
        self.function = function
        self.callback = callback if callback else lambda r, e: None
        self.daemon = kwargs.pop('daemon', True)

        self.start()

    def target(self, *args, **kwargs):
        result = None
        error = None

        try:
            result = self.function(*args, **kwargs)
        except Exception as err:
            logger.error("Error while completing task %s: %s",
                         self.function, err)
            error = err
            ex_type, ex_value, tb = sys.exc_info()
            print(ex_type, ex_value)
            traceback.print_tb(tb)

        GLib.idle_add(lambda: self.callback(result, error))
