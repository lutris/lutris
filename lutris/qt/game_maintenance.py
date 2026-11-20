"""Expose game maintenance state and operations to the library dialogs."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from lutris.backend import game_maintenance
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class GameMaintenanceController(QObject):
    stateChanged = Signal()
    finished = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._game_id = ""
        self._info: game_maintenance.GameMaintenanceInfo | None = None
        self._destination = ""
        self._lookup: asyncio.Task[None] | None = None
        self._working = False

    @Property(bool, notify=stateChanged)
    def ready(self) -> bool:
        return self._info is not None

    @Property(bool, notify=stateChanged)
    def working(self) -> bool:
        return self.is_working

    @property
    def is_working(self) -> bool:
        return self._working

    @Property(bool, notify=stateChanged)
    def installed(self) -> bool:
        return bool(self._info and self._info.installed)

    @Property(str, notify=stateChanged)
    def directory(self) -> str:
        return self._info.directory if self._info else ""

    @Property(str, notify=stateChanged)
    def filesUnavailableReason(self) -> str:  # noqa: N802
        return self._info.files_unavailable_reason if self._info else ""

    @Property(str, notify=stateChanged)
    def moveTarget(self) -> str:  # noqa: N802
        if not self._info or not self._destination:
            return ""
        return str(Path(self._destination) / Path(self._info.directory).name)

    @Slot(str)
    def open_maintenance(self, game_id: str) -> None:
        self.close_maintenance()
        self._game_id = game_id
        self._lookup = start_task(self._load(game_id), self._prompts.error)

    @Slot()
    def close_maintenance(self) -> None:
        if self._lookup:
            self._lookup.cancel()
            self._lookup = None
        self._game_id = ""
        self._info = None
        self._destination = ""
        self.stateChanged.emit()

    async def _load(self, game_id: str) -> None:
        self._info = await game_maintenance.get_maintenance_info(game_id)
        self.stateChanged.emit()

    @Slot(QUrl)
    def choose_destination(self, url: QUrl) -> None:
        self._destination = url.toLocalFile()
        self.stateChanged.emit()

    @Slot()
    def move(self) -> None:
        if self._info and self._destination and not self._working:
            self._start(game_maintenance.move_game(self._game_id, self._info.directory, self._destination))

    @Slot(bool, bool)
    def uninstall(self, trash_files: bool, remove_from_library: bool) -> None:
        if self._info and not self._working:
            self._start(
                game_maintenance.uninstall_game(
                    self._game_id, self._info, trash_files=trash_files, remove_from_library=remove_from_library
                )
            )

    def _start(self, operation: Coroutine[Any, Any, str | None]) -> None:
        self._working = True
        self.stateChanged.emit()
        start_task(self._finish(operation), self._prompts.error)

    async def _finish(self, operation: Coroutine[Any, Any, str | None]) -> None:
        try:
            await operation
        finally:
            self._working = False
            self.stateChanged.emit()
        self.finished.emit()
