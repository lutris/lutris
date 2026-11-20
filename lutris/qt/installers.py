"""Expose install script discovery and selection to Qt Quick."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from lutris.backend import installers
from lutris.backend.models import InstallerCatalog, InstallerSelection
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class InstallerController(QObject):
    requested = Signal()
    stateChanged = Signal()
    closeRequested = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._game_name = ""
        self._catalog: InstallerCatalog | None = None
        self._selection: InstallerSelection | None = None
        self._directory = ""
        self._task: asyncio.Task[None] | None = None

    @Property(bool, notify=stateChanged)
    def loading(self) -> bool:
        return self._task is not None

    @Property(str, notify=stateChanged)
    def gameName(self) -> str:  # noqa: N802
        return self._catalog.game_name if self._catalog else self._game_name

    @Property(list, notify=stateChanged)
    def choices(self) -> list[dict[str, str]]:
        if not self._catalog:
            return []
        return [
            {
                "id": choice.id,
                "version": choice.version,
                "runnerName": choice.runner_name,
                "description": choice.description,
                "notes": choice.notes,
                "credits": choice.credits,
            }
            for choice in self._catalog.choices
        ]

    @Property(bool, notify=stateChanged)
    def selected(self) -> bool:
        return self._selection is not None

    @Property(str, notify=stateChanged)
    def selectedVersion(self) -> str:  # noqa: N802
        return self._selection.version if self._selection else ""

    @Property(bool, notify=stateChanged)
    def createsGameFolder(self) -> bool:  # noqa: N802
        return bool(self._selection and self._selection.creates_game_folder)

    @Property(str, notify=stateChanged)
    def directory(self) -> str:
        return self._directory

    @Property(list, notify=stateChanged)
    def runnersToInstall(self) -> list[str]:  # noqa: N802
        return list(self._selection.runners_to_install) if self._selection else []

    @Property(str, notify=stateChanged)
    def requiredGame(self) -> str:  # noqa: N802
        return (self._selection.required_game_slug or "") if self._selection else ""

    @Slot(str, str)
    def open_installers(self, game_id: str, game_name: str) -> None:
        self._reset(game_name)
        self._start(self._load(installers.find_game_installers(game_id)))
        self.requested.emit()

    @Slot()
    def open_required_game(self) -> None:
        if self._selection and (slug := self._selection.required_game_slug):
            self._reset(slug)
            self._start(self._load(installers.find_installers(slug)))

    @Slot(str)
    def select(self, choice_id: str) -> None:
        if self._catalog and not self._task:
            self._start(self._select(self._catalog.id, choice_id))

    @Slot()
    def back(self) -> None:
        if not self._task:
            self._selection = None
            self._directory = ""
            self.stateChanged.emit()

    @Slot(QUrl)
    def choose_directory(self, url: QUrl) -> None:
        self.set_directory(url.toLocalFile())

    @Slot(str)
    def set_directory(self, directory: str) -> None:
        if directory != self._directory:
            self._directory = directory
            self.stateChanged.emit()

    @Slot()
    def close_installers(self) -> None:
        self._reset("")

    def _reset(self, game_name: str) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self._catalog:
            start_task(installers.close_catalog(self._catalog.id), self._prompts.error)
        self._game_name = game_name
        self._catalog = None
        self._selection = None
        self._directory = ""
        self.stateChanged.emit()

    def _start(self, operation: Coroutine[Any, Any, None]) -> None:
        self._task = start_task(operation, self._prompts.error)
        self.stateChanged.emit()

    def _finish(self) -> None:
        # A cancelled task must not clear the task that replaced it
        if self._task is asyncio.current_task():
            self._task = None
            self.stateChanged.emit()

    async def _load(self, request: Coroutine[Any, Any, InstallerCatalog]) -> None:
        try:
            self._catalog = await request
        except asyncio.CancelledError:
            raise
        except Exception:
            self.closeRequested.emit()
            raise
        finally:
            self._finish()

    async def _select(self, catalog_id: str, choice_id: str) -> None:
        try:
            self._selection = await installers.select_installer(catalog_id, choice_id)
            self._directory = self._selection.default_directory
        finally:
            self._finish()
