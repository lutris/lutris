"""The state of the filters of a game view.

The rules that interpret these filters live in lutris.gui.game_filter; this class just holds the
filters and the search built from them, so that a caller (the window, or a test) can hand the
state around without a window.
"""

from collections.abc import Collection
from typing import Any

from lutris.gui.game_filter import FilterValues
from lutris.search import GameSearch

# The filters a sidebar row can set; selecting a row clears the others.
SIDEBAR_FILTER_TYPES = ("category", "dynamic_category", "saved_search", "service", "runner", "platform")


class GameViewState:
    """Tracks the filters applied to a game view, and caches the search that goes with the
    search text and the service in use."""

    def __init__(self, filters: dict[str, Any] | None = None) -> None:
        self.filters: dict[str, Any] = dict(filters or {})
        self._game_search: GameSearch | None = None

    @property
    def values(self) -> FilterValues:
        """Returns a snapshot of the filters with the defaults applied, for the filtering
        rules in lutris.gui.game_filter."""
        return FilterValues(self.filters)

    def set_text(self, text: str) -> None:
        """Replaces the text searched for in the view."""
        self.filters["text"] = text

    def set_installed(self, installed: bool) -> None:
        """Shows or hides uninstalled games."""
        self.filters["installed"] = installed

    def select_sidebar(self, row_type: str, row_id: str) -> str:
        """Replaces the filters set by the previous sidebar row with those of the row given,
        and returns the name of the filter that this row sets (the sidebar calls a category a
        'user_category'); the others are all cleared."""
        for filter_type in SIDEBAR_FILTER_TYPES:
            self.filters.pop(filter_type, None)

        if row_type == "user_category":
            row_type = "category"

        self.filters[row_type] = row_id
        return row_type

    def is_sort_sensitive(
        self, dynamic_categories: Collection[str], sortable_dynamic_categories: Collection[str]
    ) -> bool:
        """True if the view sorting options will be effective; most dynamic categories ignore
        them. 'dynamic_categories' are the dynamic categories the view knows, and
        'sortable_dynamic_categories' the ones among them that do honor the sort."""
        dynamic = self.filters.get("dynamic_category")
        return dynamic not in dynamic_categories or dynamic in sortable_dynamic_categories

    def get_game_search(self, service: Any) -> GameSearch:
        """Returns a game-search object for the current search text and service; this object
        is cached so that we need not re-parse the search if it has not changed."""
        text = self.filters.get("text") or ""
        if self._game_search is None or self._game_search.service != service or self._game_search.text != text:
            self._game_search = GameSearch(text, service)
        return self._game_search
