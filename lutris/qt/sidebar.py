"""Group library views into a model for the Qt Quick sidebar."""

from dataclasses import dataclass
from gettext import gettext as _

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from lutris.backend import library, runners, services
from lutris.qt.library_model import ModelIndex

ALL_GAMES = {"category": "all"}
_LABEL_ROLE = Qt.ItemDataRole.UserRole + 1
_SECTION_ROLE = _LABEL_ROLE + 1
_RUNNER_ROLE = _LABEL_ROLE + 2
_ICON_ROLE = _LABEL_ROLE + 3

# The icons of the library's own views; the others take their section's icon
_VIEW_ICONS = {
    ("category", "all"): "games",
    ("dynamic_category", "recent"): "recent",
    ("dynamic_category", "running"): "running",
    ("category", "favorite"): "favorite",
    ("dynamic_category", ".uncategorized"): "uncategorized",
    ("dynamic_category", "missing"): "missing",
    ("category", ".hidden"): "hidden",
}
_KIND_ICONS = {
    "category": "category",
    "saved_search": "saved-search",
    "service": "store",
    "runner": "runner",
    "platform": "platform",
}


def get_view_icon(view: dict[str, str]) -> str:
    """Name the icon, from the style's icon set, that shows a view in the sidebar."""
    for kind, value in view.items():
        if icon := _VIEW_ICONS.get((kind, value)) or _KIND_ICONS.get(kind):
            return icon
    return "games"


@dataclass(frozen=True)
class SidebarEntry:
    title: str
    view: dict[str, str]


class SidebarModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._entries: list[tuple[str, SidebarEntry]] = []

    async def refresh(self) -> None:
        sections = (
            (
                _("Library"),
                [
                    SidebarEntry(_("Games"), ALL_GAMES),
                    SidebarEntry(_("Recent"), {"dynamic_category": "recent"}),
                    SidebarEntry(_("Running"), {"dynamic_category": "running"}),
                    SidebarEntry(_("Favorites"), {"category": "favorite"}),
                    SidebarEntry(_("Uncategorized"), {"dynamic_category": ".uncategorized"}),
                    SidebarEntry(_("Missing"), {"dynamic_category": "missing"}),
                    SidebarEntry(_("Hidden"), {"category": ".hidden"}),
                ],
            ),
            (_("Categories"), [SidebarEntry(name, {"category": name}) for name in await library.list_categories()]),
            (
                _("Saved Searches"),
                [SidebarEntry(item.name, {"saved_search": item.name}) for item in await library.list_saved_searches()],
            ),
            (_("Sources"), [SidebarEntry(item.name, {"service": item.id}) for item in await services.list_services()]),
            (
                _("Runners"),
                [
                    SidebarEntry(item.human_name, {"runner": item.name})
                    for item in await runners.list_installed_runners()
                ],
            ),
            (_("Platforms"), [SidebarEntry(name, {"platform": name}) for name in await library.list_platforms()]),
        )
        self.beginResetModel()
        self._entries = [(section, entry) for section, entries in sections for entry in entries]
        self.endResetModel()

    def view_at(self, row: int) -> dict[str, str] | None:
        return self._entries[row][1].view if 0 <= row < len(self._entries) else None

    def find_row(self, view: dict[str, str]) -> int:
        return next((row for row, (_, entry) in enumerate(self._entries) if entry.view == view), -1)

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._entries)

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {
            _LABEL_ROLE: QByteArray(b"viewTitle"),
            _SECTION_ROLE: QByteArray(b"sectionTitle"),
            _RUNNER_ROLE: QByteArray(b"runnerName"),
            _ICON_ROLE: QByteArray(b"viewIcon"),
        }

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid():
            return None
        section, entry = self._entries[index.row()]
        if role in (_LABEL_ROLE, Qt.ItemDataRole.DisplayRole):
            return entry.title
        if role == _RUNNER_ROLE:
            return entry.view.get("runner", "")
        if role == _ICON_ROLE:
            return get_view_icon(entry.view)
        return section if role == _SECTION_ROLE else None
