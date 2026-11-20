"""Running the backend's coroutines from the GTK frontend."""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from gi.repository import Gio, Gtk

from lutris.gui.dialogs import display_error
from lutris.gui.widgets.utils import get_main_window
from lutris.util.log import logger

T = TypeVar("T")


def start_task(coroutine: Coroutine[Any, Any, T], parent: Gtk.Widget | None = None) -> "asyncio.Task[T]":
    """Run a coroutine on the application's event loop, and show any error it raises,
    as the exception backstops do for callbacks; parent is the error dialog's parent,
    the main window by default. The application keeps running until it finishes.
    Cancelling the task (to replace it, say) shows no error."""
    application = Gio.Application.get_default()
    if application:
        task = application.create_asyncio_task(coroutine)
    else:
        task = asyncio.ensure_future(coroutine)

    def on_done(finished: "asyncio.Task[T]") -> None:
        if finished.cancelled():
            return
        error = finished.exception()
        if error:
            logger.error("Error in a background task: %s", error, exc_info=error)
            error_parent = parent or get_main_window()
            if error_parent:
                display_error(error, error_parent)

    task.add_done_callback(on_done)
    return task
