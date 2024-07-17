import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from lutris import settings
from lutris.database import sql
from lutris.gui.widgets import NotificationSource

SAVED_SEARCHES_UPDATED = NotificationSource()


@dataclass
class SavedSearch:
    saved_search_id: int
    name: str
    search: str

    def add(self, no_signal: bool = False) -> None:
        """Add a category to the database"""
        self.saved_search_id = sql.db_insert(
            settings.DB_PATH, "saved_searches", {"name": self.name, "search": self.search}
        )
        if not no_signal:
            SAVED_SEARCHES_UPDATED.fire()

    def update(self, no_signal: bool = False) -> None:
        query = "UPDATE saved_searches SET name=?, search=? WHERE id=?"

        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, query, (self.name, self.search, self.saved_search_id))
        if not no_signal:
            SAVED_SEARCHES_UPDATED.fire()

    def remove(self, no_signal: bool = False) -> None:
        query = "DELETE FROM saved_searches WHERE id=?"

        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, query, (self.saved_search_id,))

        if not no_signal:
            SAVED_SEARCHES_UPDATED.fire()


def _create_search(row: Dict[str, Any]) -> "SavedSearch":
    return SavedSearch(row["id"], row["name"], row["search"])


def strip_saved_search_name(name):
    """This strips the name given, and also removes extra internal whitespace."""
    name = (name or "").strip()
    name = re.sub(" +", " ", name)  # Remove excessive whitespaces
    return name


def get_saved_searches() -> List[SavedSearch]:
    """Get the list of every search in database."""
    rows = sql.db_select(settings.DB_PATH, "saved_searches")
    return [_create_search(row) for row in rows]


def get_saved_search_by_name(name: str) -> Optional[SavedSearch]:
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "saved_searches", condition=("name", name))
    if categories:
        return _create_search(categories[0])

    return None


def get_saved_search_by_id(saved_search_id: int) -> Optional[SavedSearch]:
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "saved_searches", condition=("id", saved_search_id))
    if categories:
        return _create_search(categories[0])

    return None
