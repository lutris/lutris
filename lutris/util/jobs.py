import threading
from gi.repository import GLib

from lutris.util.log import logger


def async_call(func, on_done, *args, **kwargs):
    """ Launch given function `func` in a new thread """
    logger.debug("Async call: %s", str(func.__name__))
    if not on_done:
        on_done = lambda r, e: None

    def do_call(*args, **kwargs):
        result = None
        error = None

        try:
            result = func(*args, **kwargs)
        except Exception, err:
            logger.error("Error while completing task %s: %s", func, err)
            #raise  # Uncomment this to inspect errors
            error = err
        GLib.idle_add(lambda: on_done(result, error))

    thread = threading.Thread(target=do_call, args=args, kwargs=kwargs)
    thread.start()
