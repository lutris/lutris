"""Read and save live game logs for a Qt Quick dialog."""

import asyncio
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from lutris.backend import events, games
from lutris.exceptions import LutrisError
from lutris.qt.tasks import start_task
from lutris.util.notifications import NotificationRegistration

if TYPE_CHECKING:
    from lutris.qt.delegates import PromptController


class GameLogController(QObject):
    logChanged = Signal()

    def __init__(self, prompts: "PromptController", parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._game_id = ""
        self._text = ""
        self._registration: NotificationRegistration | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._timer = QTimer(self, singleShot=True, interval=100)
        self._timer.timeout.connect(self._refresh)

    @Property(str, notify=logChanged)
    def logText(self) -> str:  # noqa: N802
        return self._text

    @Slot(str)
    def open_log(self, game_id: str) -> None:
        self.close_log()
        self._game_id = game_id
        self._registration = events.GAME_LOG_CHANGED.register(self._on_log_changed)
        self._refresh()

    @Slot()
    def close_log(self) -> None:
        self._game_id = ""
        self._timer.stop()
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None
        if self._registration:
            self._registration.unregister()
            self._registration = None
        self._text = ""

    def _on_log_changed(self, game_id: str) -> None:
        if game_id == self._game_id and not self._timer.isActive():
            self._timer.start()

    def _refresh(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        self._refresh_task = start_task(self._load(self._game_id), self._prompts.error)

    async def _load(self, game_id: str) -> None:
        text = await games.get_game_log(game_id)
        if game_id == self._game_id and text != self._text:
            self._text = text
            self.logChanged.emit()

    @Slot(QUrl)
    def save_log(self, url: QUrl) -> None:
        path = url.toLocalFile()
        if path and self._game_id:
            start_task(self._save(Path(path), self._game_id), self._prompts.error)

    @staticmethod
    async def _save(path: Path, game_id: str) -> None:
        text = await games.get_game_log(game_id)
        try:
            await asyncio.to_thread(path.write_text, text, encoding="utf-8")
        except OSError as error:
            raise LutrisError(_("Could not save the log to %s") % path) from error
