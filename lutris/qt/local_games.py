"""Expose local game registration to Qt Quick."""

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from lutris.backend import local_games
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class LocalGameController(QObject):
    requested = Signal()
    stateChanged = Signal()
    registered = Signal(str)

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._game_id = ""
        self._game_name = ""
        self._working = False

    @Property(bool, notify=stateChanged)
    def working(self) -> bool:
        return self._working

    @Property(str, notify=stateChanged)
    def gameName(self) -> str:  # noqa: N802
        return self._game_name

    @Property(bool, notify=stateChanged)
    def linking(self) -> bool:
        return bool(self._game_id)

    @Slot(str, str)
    def open_registration(self, game_id: str, game_name: str) -> None:
        if self._working:
            return
        self._game_id = game_id
        self._game_name = game_name
        self.stateChanged.emit()
        self.requested.emit()

    @Slot(QUrl, result=str)
    def local_path(self, url: QUrl) -> str:
        return url.toLocalFile()

    @Slot(str, str, str)
    def register(self, name: str, executable: str, arguments: str) -> None:
        if self._working:
            return
        self._working = True
        self.stateChanged.emit()
        start_task(self._register(name, executable, arguments, self._game_id), self._prompts.error)

    async def _register(self, name: str, executable: str, arguments: str, game_id: str) -> None:
        try:
            game = await local_games.register_linux_game(executable, name, arguments, game_id=game_id)
        finally:
            self._working = False
            self.stateChanged.emit()
        self.registered.emit(game.name)
