"""A game's category memberships for the QML editor."""

from enum import IntEnum

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from lutris.backend.game_actions import CategoryMembership
from lutris.qt.library_model import ModelIndex


class CategoryRole(IntEnum):
    NAME = Qt.ItemDataRole.UserRole + 1
    INCLUDED = NAME + 1


class CategoryModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._memberships: tuple[CategoryMembership, ...] = ()

    def set_memberships(self, memberships: tuple[CategoryMembership, ...]) -> None:
        self.beginResetModel()
        self._memberships = memberships
        self.endResetModel()

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._memberships)

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {CategoryRole.NAME: QByteArray(b"categoryName"), CategoryRole.INCLUDED: QByteArray(b"included")}

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | bool | None:
        if index.isValid():
            item = self._memberships[index.row()]
            if role in (CategoryRole.NAME, Qt.ItemDataRole.DisplayRole):
                return item.name
            if role == CategoryRole.INCLUDED:
                return item.included
        return None
