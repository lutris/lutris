"""Signal handling module"""
import os
import signal
from gi.repository import GLib
from lutris.util.log import logger

PID_HANDLERS = {}


def sigchld_handler(_signum, _frame):
    """This handler uses SIGCHLD as a trigger to check on the runner process
    in order to detect the monitoredcommand's complete exit asynchronously."""
    try:
        pid, returncode, _ = os.wait3(os.WNOHANG)
    except ChildProcessError as ex:  # already handled by someone else
        logger.debug("Wait call failed: %s", ex)
        return
    try:
        handler = PID_HANDLERS.pop(pid)
    except KeyError:
        logger.debug("No handler for pid %s", pid)
        return
    GLib.timeout_add(0, handler, returncode)


def register_handler(pid, handler):
    """No idea what is the purpose of this"""
    PID_HANDLERS[pid] = handler


signal.signal(signal.SIGCHLD, sigchld_handler)
