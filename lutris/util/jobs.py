import threading
from gi.repository import GObject, GLib


def async_call(func, on_done, *args, **kwargs):
    """ Launch given function `func` in a new thread """
    if not on_done:
        on_done = lambda r, e: None

    def do_call(*args, **kwargs):
        result = None
        error = None

        try:
            result = func(*args, **kwargs)
        except Exception, err:
            #raise  # Uncomment this to inspect errors
            error = err
        GLib.idle_add(lambda: on_done(result, error))

    thread = threading.Thread(target=do_call, args=args, kwargs=kwargs)
    thread.start()
