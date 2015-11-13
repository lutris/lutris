import threading
from gi.repository import GLib

from lutris.util.log import logger


class AsyncCall(threading.Thread):
    def __init__(self, function, on_done, *args, **kwargs):
        """Execute `function` in a new thread then schedule `on_done` for
        execution in the main loop.
        """
        if kwargs.pop('stoppable', False):
            self.stop_request = threading.Event()
            kwargs['stop_request'] = self.stop_request

        super(AsyncCall, self).__init__(target=self.target, args=args,
                                        kwargs=kwargs)
        self.function = function
        self.on_done = on_done if on_done else lambda r, e: None
        self.daemon = kwargs.pop('daemon', False)

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
            # raise  # Uncomment this to inspect errors

        GLib.idle_add(lambda: self.on_done(result, error))
