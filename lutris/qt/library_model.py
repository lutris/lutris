"""The table of games the library window shows, as rows from the backend's library query."""

import time
from gettext import gettext as _
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from lutris.backend.models import LibraryGame
from lutris.util.strings import get_formatted_playtime

AnyIndex = QModelIndex | QPersistentModelIndex

# Each column: what it shows, its title, and the backend's sort key for it, if it can sort by it
COLUMNS: list[tuple[str, str, str | None]] = [
    ("name", _("Name"), "name"),
    ("runner", _("Runner"), None),
    ("platform", _("Platform"), None),
    ("year", _("Year"), "year"),
    ("lastplayed", _("Last Played"), "lastplayed"),
    ("installed_at", _("Installed At"), "installed_at"),
    ("playtime", _("Play Time"), "playtime"),
]

# The model's role for the LibraryGame of a row
GameRole = Qt.ItemDataRole.UserRole + 1


def _format_time(timestamp: int | None) -> str:
    return time.strftime("%x", time.localtime(timestamp)) if timestamp and timestamp > 0 else ""


def get_column_text(game: LibraryGame, column: str) -> str:
    """Return what a column says about a game."""
    if column == "runner":
        return game.runner_name or ""
    if column == "year":
        return str(game.year or "")
    if column in ("lastplayed", "installed_at"):
        return _format_time(getattr(game, column))
    if column == "playtime":
        return get_formatted_playtime(game.playtime) if game.playtime else ""
    return str(getattr(game, column) or "")


class LibraryModel(QAbstractTableModel):
    """The games of a library view, in the backend's order. Running games are in bold,
    and games that aren't installed are dimmed."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._games: list[LibraryGame] = []
        self._running_game_ids: set[str] = set()

    @property
    def games(self) -> list[LibraryGame]:
        return list(self._games)

    def set_games(self, games: list[LibraryGame]) -> None:
        self.beginResetModel()
        self._games = list(games)
        self.endResetModel()

    def set_running_game_ids(self, game_ids: set[str]) -> None:
        self._running_game_ids = set(game_ids)
        if self._games:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._games) - 1, len(COLUMNS) - 1))

    def get_game(self, index: AnyIndex) -> LibraryGame | None:
        return self._games[index.row()] if index.isValid() and index.row() < len(self._games) else None

    def find_row(self, view_id: str) -> int | None:
        """Return the row of a game by its id in the view, or None if it isn't listed."""
        return next((row for row, game in enumerate(self._games) if game.id == view_id), None)

    def rowCount(self, parent: AnyIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._games)

    def columnCount(self, parent: AnyIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][1]
        return None

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        game = self.get_game(index)
        if not game:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return get_column_text(game, COLUMNS[index.column()][0])
        if role == GameRole:
            return game
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 0:
            return game.name
        if role == Qt.ItemDataRole.AccessibleDescriptionRole and index.column() == 0:
            if game.game_id in self._running_game_ids:
                return _("Running")
            if not game.installed:
                return _("Not installed")
        if role == Qt.ItemDataRole.FontRole and game.game_id in self._running_game_ids:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.ForegroundRole and not game.installed:
            return QApplication.palette().brush(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        return None
