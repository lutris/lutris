"""Plain library rows exposed to Qt Quick views."""

import time
from enum import IntEnum

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt, QUrl

from lutris.backend.models import LibraryGame
from lutris.util.strings import get_formatted_playtime

type ModelIndex = QModelIndex | QPersistentModelIndex
type RoleValue = str | bool | QUrl | None


class GameRole(IntEnum):
    TITLE = Qt.ItemDataRole.UserRole + 1
    RUNNER = TITLE + 1
    PLATFORM = TITLE + 2
    YEAR = TITLE + 3
    LAST_PLAYED = TITLE + 4
    INSTALLED_AT = TITLE + 5
    PLAY_TIME = TITLE + 6
    INSTALLED = TITLE + 7
    RUNNING = TITLE + 8
    COVER = TITLE + 9
    BANNER = TITLE + 10
    ICON = TITLE + 11
    ICON_NAME = TITLE + 12


_ROLES = {
    GameRole.TITLE: b"gameTitle",
    GameRole.RUNNER: b"runnerText",
    GameRole.PLATFORM: b"platformText",
    GameRole.YEAR: b"yearText",
    GameRole.LAST_PLAYED: b"lastPlayedText",
    GameRole.INSTALLED_AT: b"installedAtText",
    GameRole.PLAY_TIME: b"playTimeText",
    GameRole.INSTALLED: b"installed",
    GameRole.RUNNING: b"running",
    GameRole.COVER: b"coverUrl",
    GameRole.BANNER: b"bannerUrl",
    GameRole.ICON: b"iconUrl",
    GameRole.ICON_NAME: b"iconName",
}

_ARTWORK_ROLES = [GameRole.COVER, GameRole.BANNER, GameRole.ICON]


def _format_time(timestamp: int | None) -> str:
    return time.strftime("%x", time.localtime(timestamp)) if timestamp and timestamp > 0 else ""


class LibraryModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._games: list[LibraryGame] = []
        self._running_ids: set[str] = set()
        self._artwork_revision = 0

    def set_games(self, games: list[LibraryGame]) -> None:
        self.beginResetModel()
        self._games = games
        self.endResetModel()

    def set_running_game_ids(self, game_ids: set[str]) -> None:
        changed = self._running_ids ^ game_ids
        self._running_ids = set(game_ids)
        for row, game in enumerate(self._games):
            if game.game_id in changed:
                index = self.index(row)
                self.dataChanged.emit(index, index, [GameRole.RUNNING])

    def invalidate_artwork(self) -> None:
        self._artwork_revision += 1
        if self._games:
            self.dataChanged.emit(self.index(0), self.index(len(self._games) - 1), _ARTWORK_ROLES)

    def _artwork_url(self, path: str | None) -> QUrl:
        if not path:
            return QUrl()
        url = QUrl.fromLocalFile(path)
        url.setQuery(f"revision={self._artwork_revision}")
        return url

    def game_at(self, row: int) -> LibraryGame | None:
        return self._games[row] if 0 <= row < len(self._games) else None

    def find_row(self, view_id: str) -> int:
        return next((row for row, game in enumerate(self._games) if game.id == view_id), -1)

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._games)

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {role: QByteArray(name) for role, name in _ROLES.items()}

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> RoleValue:
        game = self.game_at(index.row())
        if not game:
            return None
        artwork = game.artwork
        match role:
            case GameRole.TITLE | Qt.ItemDataRole.DisplayRole:
                return game.name
            case GameRole.RUNNER:
                return game.runner_name or ""
            case GameRole.PLATFORM:
                return game.platform or ""
            case GameRole.YEAR:
                return str(game.year or "")
            case GameRole.LAST_PLAYED:
                return _format_time(game.lastplayed)
            case GameRole.INSTALLED_AT:
                return _format_time(game.installed_at)
            case GameRole.PLAY_TIME:
                return get_formatted_playtime(game.playtime) if game.playtime else ""
            case GameRole.INSTALLED:
                return game.installed
            case GameRole.RUNNING:
                return game.game_id in self._running_ids
            case GameRole.COVER:
                return self._artwork_url(artwork.cover_path if artwork else None)
            case GameRole.BANNER:
                return self._artwork_url(artwork.banner_path if artwork else None)
            case GameRole.ICON:
                return self._artwork_url(artwork.icon_path if artwork else None)
            case GameRole.ICON_NAME:
                return (artwork.icon_name or "") if artwork else ""
        return None
