"""Expose where library artwork comes from, and the SteamGridDB API key, to Qt Quick."""

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from lutris.backend import media
from lutris.backend.models import ArtworkSettings
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class ArtworkSettingsController(QObject):
    requested = Signal()
    stateChanged = Signal()
    saved = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._settings: ArtworkSettings | None = None
        self._working = False

    @Property(bool, notify=stateChanged)
    def ready(self) -> bool:
        return self._settings is not None

    @Property(bool, notify=stateChanged)
    def working(self) -> bool:
        return self._working

    @Property(bool, notify=stateChanged)
    def keySet(self) -> bool:  # noqa: N802
        return bool(self._settings and self._settings.steamgriddb_key_set)

    @Property(bool, notify=stateChanged)
    def keyFromEnvironment(self) -> bool:  # noqa: N802
        return bool(self._settings and self._settings.steamgriddb_key_from_environment)

    @Slot()
    def open_settings(self) -> None:
        self.requested.emit()
        start_task(self._load(), self._prompts.error)

    async def _load(self) -> None:
        self._settings = await media.get_artwork_settings()
        self.stateChanged.emit()

    @Slot()
    def open_key_page(self) -> None:
        if self._settings:
            QDesktopServices.openUrl(QUrl(self._settings.steamgriddb_key_page))

    @Slot(str)
    def save_key(self, api_key: str) -> None:
        if not self._working:
            self._working = True
            self.stateChanged.emit()
            start_task(self._save(api_key), self._prompts.error)

    async def _save(self, api_key: str) -> None:
        try:
            self._settings = await media.set_steamgriddb_api_key(api_key)
        finally:
            self._working = False
            self.stateChanged.emit()
        self.saved.emit()
