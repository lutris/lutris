"""Running the backend's coroutines from the Qt frontend, and showing errors."""

import asyncio
from collections.abc import Coroutine
from gettext import gettext as _
from typing import Any, TypeVar

from gi.repository import Gio
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from lutris.exceptions import LutrisError
from lutris.util.log import logger

T = TypeVar("T")


def start_task(coroutine: Coroutine[Any, Any, T], parent: QWidget | None = None) -> "asyncio.Task[T]":
    """Run a coroutine on the application's event loop, and show any error it raises
    over parent. The application keeps running until it finishes. Cancelling the task
    (to replace it, say) shows no error."""
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
            show_error(error, parent)

    task.add_done_callback(on_done)
    return task


def show_error(error: BaseException, parent: QWidget | None = None) -> None:
    """Show an error in a message box, without waiting for the user to close it."""
    message = error.message if isinstance(error, LutrisError) else str(error)
    box = QMessageBox(QMessageBox.Icon.Critical, _("Error"), message, QMessageBox.StandardButton.Close, parent)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.open()
