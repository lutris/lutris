"""The library window's sidebar: the views of the library it can show."""

from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from lutris.backend import library, runners, services

# The sidebar's role for the view an item selects: LibraryQuery's fields for it
ViewRole = Qt.ItemDataRole.UserRole + 1

ALL_GAMES: dict[str, str] = {"category": "all"}

# The library's own views
LIBRARY_VIEWS: list[tuple[str, dict[str, str]]] = [
    (_("Games"), ALL_GAMES),
    (_("Recent"), {"dynamic_category": "recent"}),
    (_("Running"), {"dynamic_category": "running"}),
    (_("Favorites"), {"category": "favorite"}),
    (_("Uncategorized"), {"dynamic_category": ".uncategorized"}),
    (_("Missing"), {"dynamic_category": "missing"}),
    (_("Hidden"), {"category": ".hidden"}),
]


class Sidebar(QTreeWidget):
    """Lists the library's views by section; view_selected is emitted with the view's
    fields for a LibraryQuery when one is selected."""

    view_selected = Signal(dict)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(12)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self._view: dict[str, str] = ALL_GAMES

    @property
    def view(self) -> dict[str, str]:
        """The view selected."""
        return dict(self._view)

    async def refresh(self) -> None:
        """Rebuild the sidebar from the backend, keeping the selected view if it's still there."""
        categories = await library.list_categories()
        saved_searches = await library.list_saved_searches()
        enabled_services = await services.list_services()
        installed_runners = await runners.list_installed_runners()
        platforms = await library.list_platforms()

        sections: list[tuple[str, list[tuple[str, dict[str, str]]]]] = [
            (_("Library"), LIBRARY_VIEWS),
            (_("Categories"), [(name, {"category": name}) for name in categories]),
            (_("Saved Searches"), [(search.name, {"saved_search": search.name}) for search in saved_searches]),
            (_("Sources"), [(service.name, {"service": service.id}) for service in enabled_services]),
            (_("Runners"), [(runner.human_name, {"runner": runner.name}) for runner in installed_runners]),
            (_("Platforms"), [(platform, {"platform": platform}) for platform in platforms]),
        ]

        selected = self._view
        self.blockSignals(True)
        self.clear()
        selected_item = None
        for title, views in sections:
            if not views:
                continue
            section = QTreeWidgetItem(self, [title])
            section.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = section.font(0)
            font.setBold(True)
            section.setFont(0, font)
            for label, view in views:
                item = QTreeWidgetItem(section, [label])
                item.setData(0, ViewRole, view)
                if view == selected:
                    selected_item = item
        self.expandAll()
        self.blockSignals(False)

        if selected_item:
            self.setCurrentItem(selected_item)
        else:
            # The view went away (its category was removed, say), so show all games
            self.select_view(ALL_GAMES)

    def select_view(self, view: dict[str, str]) -> None:
        for index in range(self.topLevelItemCount()):
            section = self.topLevelItem(index)
            for child_index in range(section.childCount() if section else 0):
                item = section.child(child_index) if section else None
                if item and item.data(0, ViewRole) == view:
                    self.setCurrentItem(item)
                    return

    def _on_current_item_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        view = current.data(0, ViewRole) if current else None
        if view and view != self._view:
            self._view = view
            self.view_selected.emit(dict(view))
