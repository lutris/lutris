from lutris.gui.widgets import NotificationSource
from lutris.util.jobs import AsyncCall

BUSY_STARTED = NotificationSource()
BUSY_STOPPED = NotificationSource()
_busy_count = 0


def start_busy():
    """Put Lutris into the 'busy' state, which causes BUSY_STARTED to fire; LutrisWindow
    will display a 'progress' cursor."""
    global _busy_count
    _busy_count += 1
    if _busy_count == 1:
        BUSY_STARTED.fire()


def stop_busy():
    """Takes Lutris out of the 'busy' state', which causes BUSY_STOPPED to fire. Note
    that busy states can be nested or overlapped; business must be stopped as many times
    as it is started."""
    global _busy_count
    _busy_count -= 1
    if _busy_count == 0:
        BUSY_STOPPED.fire()


class BusyAsyncCall(AsyncCall):
    """This is a version of AsyncCall that calls start_busy() and stop_busy(), which
    will cause the LutrisWindow to show a progress cursor while the task runs."""

    def __init__(self, func, callback, *args, **kwargs):
        def on_completion(*a, **kw):
            stop_busy()
            if callback:
                callback(*a, **kw)

        super().__init__(func, on_completion, *args, **kwargs)
        start_busy()
