"""Drive game imports from Qt Quick."""

from collections.abc import Coroutine
from gettext import gettext as _
from gettext import ngettext
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from lutris.backend import imports
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class ImportController(QObject):
    stateChanged = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._busy = False
        self._stop = False
        self._results: list[str] = []

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(list, notify=stateChanged)
    def results(self) -> list[str]:
        return self._results[:]

    @Slot(QUrl)
    def import_roms(self, folder: QUrl) -> None:
        if not self._busy:
            self._start(self._import_rom_folder(folder.toLocalFile()))

    @Slot(list, result=bool)
    def import_rom_files(self, urls: list[QUrl]) -> bool:
        if self._busy:
            return False
        paths = tuple(dict.fromkeys(url.toLocalFile() for url in urls if url.isLocalFile()))
        if not paths:
            return False
        self._start(self._import_roms(paths))
        return True

    @Slot()
    def import_playtron(self) -> None:
        if not self._busy:
            self._start(self._import_playtron())

    @Slot()
    def stop(self) -> None:
        self._stop = True

    def _start(self, operation: Coroutine[Any, Any, None]) -> None:
        self._busy = True
        self._stop = False
        self._results.clear()
        self.stateChanged.emit()
        start_task(self._run(operation), self._prompts.error)

    async def _run(self, operation: Coroutine[Any, Any, None]) -> None:
        try:
            await operation
        finally:
            self._busy = False
            self.stateChanged.emit()

    async def _import_rom_folder(self, folder: str) -> None:
        await self._import_roms(await imports.list_rom_files(folder))

    async def _import_roms(self, paths: tuple[str, ...]) -> None:
        if not paths:
            self._results.append(_("No files found."))
        for path in paths:
            if self._stop:
                break
            result = await imports.import_rom(path)
            status = result.error or (_("Imported") if result.imported else _("Already in your library"))
            self._results.append(_("%(name)s: %(status)s") % {"name": result.name, "status": status})
            self.stateChanged.emit()

    async def _import_playtron(self) -> None:
        count = await imports.import_playtron_games()
        self._results.append(ngettext("Imported %d game.", "Imported %d games.", count) % count)
