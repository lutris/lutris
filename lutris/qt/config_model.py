"""The options of a configuration page, exposed to Qt Quick as a list model."""

from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QPersistentModelIndex, Qt

from lutris.backend.models import ConfigOptionInfo

type ModelIndex = QModelIndex | QPersistentModelIndex


class OptionRole(IntEnum):
    SECTION = Qt.ItemDataRole.UserRole + 1
    KEY = SECTION + 1
    TYPE = SECTION + 2
    LABEL = SECTION + 3
    GROUP = SECTION + 4
    HELP = SECTION + 5
    VALUE = SECTION + 6
    DEFAULT_LABEL = SECTION + 7
    CHOICES = SECTION + 8
    MINIMUM = SECTION + 9
    MAXIMUM = SECTION + 10
    ENABLED = SECTION + 11
    SET_HERE = SECTION + 12
    CHANGED_BELOW = SECTION + 13
    WARNING = SECTION + 14
    ERROR = SECTION + 15


_ROLES = {
    OptionRole.SECTION: b"optionSection",
    OptionRole.KEY: b"optionKey",
    OptionRole.TYPE: b"optionType",
    OptionRole.LABEL: b"optionLabel",
    OptionRole.GROUP: b"optionGroup",
    OptionRole.HELP: b"optionHelp",
    OptionRole.VALUE: b"optionValue",
    OptionRole.DEFAULT_LABEL: b"defaultLabel",
    OptionRole.CHOICES: b"choices",
    OptionRole.MINIMUM: b"minimum",
    OptionRole.MAXIMUM: b"maximum",
    OptionRole.ENABLED: b"optionEnabled",
    OptionRole.SET_HERE: b"setHere",
    OptionRole.CHANGED_BELOW: b"changedBelow",
    OptionRole.WARNING: b"warning",
    OptionRole.ERROR: b"error",
}


def _value(option: ConfigOptionInfo) -> Any:
    # QML edits a mapping as rows, which keep their order while they're edited
    if option.type == "mapping" and isinstance(option.value, dict):
        return [{"name": name, "value": value} for name, value in option.value.items()]
    return option.value


class ConfigOptionModel(QAbstractListModel):
    """Keeps its rows when the same options come back with new values, so views keep
    their delegates and scroll position while the user edits."""

    def __init__(self) -> None:
        super().__init__()
        self._options: list[ConfigOptionInfo] = []

    def set_options(self, options: list[ConfigOptionInfo]) -> None:
        if [(option.section, option.key) for option in options] == [
            (option.section, option.key) for option in self._options
        ]:
            changed = [row for row, option in enumerate(options) if option != self._options[row]]
            self._options = options
            for row in changed:
                index = self.index(row)
                self.dataChanged.emit(index, index, [])
            return
        self.beginResetModel()
        self._options = options
        self.endResetModel()

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._options)

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {role: QByteArray(name) for role, name in _ROLES.items()}

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._options):
            return None
        option = self._options[index.row()]
        match role:
            case OptionRole.SECTION:
                return option.section
            case OptionRole.KEY:
                return option.key
            case OptionRole.TYPE:
                return option.type
            case OptionRole.LABEL | Qt.ItemDataRole.DisplayRole:
                return option.label
            case OptionRole.GROUP:
                return option.group
            case OptionRole.HELP:
                return option.help
            case OptionRole.VALUE:
                return _value(option)
            case OptionRole.DEFAULT_LABEL:
                return option.default_label
            case OptionRole.CHOICES:
                return [{"label": choice.label, "value": choice.value} for choice in option.choices]
            case OptionRole.MINIMUM:
                return option.minimum if option.minimum is not None else 0
            case OptionRole.MAXIMUM:
                return option.maximum if option.maximum is not None else 2_147_483_647
            case OptionRole.ENABLED:
                return option.enabled
            case OptionRole.SET_HERE:
                return option.set_here
            case OptionRole.CHANGED_BELOW:
                return option.changed_below
            case OptionRole.WARNING:
                return option.warning
            case OptionRole.ERROR:
                return option.error
        return None
