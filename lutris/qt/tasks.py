"""Run backend coroutines on the application's event loop."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from gi.repository import Gio

from lutris.util.log import logger


def start_task[T](coroutine: Coroutine[Any, Any, T], show_error: Callable[[BaseException], None]) -> asyncio.Task[T]:
    """Keep the application alive until the task finishes and report any error."""
    application = Gio.Application.get_default()
    task = application.create_asyncio_task(coroutine) if application else asyncio.create_task(coroutine)

    def on_done(finished: asyncio.Task[T]) -> None:
        if not finished.cancelled() and (error := finished.exception()):
            logger.error("Error in a background task: %s", error, exc_info=error)
            show_error(error)

    task.add_done_callback(on_done)
    return task
