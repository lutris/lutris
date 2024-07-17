import re
from typing import Dict, List, Optional, Union

from lutris import settings
from lutris.database import sql
from lutris.gui.widgets import NotificationSource

SAVED_SEARCHES_UPDATED = NotificationSource()


def strip_saved_search_name(name):
    """This strips the name given, and also removes extra internal whitespace."""
    name = (name or "").strip()
    name = re.sub(" +", " ", name)  # Remove excessive whitespaces
    return name


def get_saved_searches() -> List[Dict[str, Union[int, str]]]:
    """Get the list of every category in database."""
    # Categories look like [{"id": 1, "name": "My Category"}, ...]
    return sql.db_select(settings.DB_PATH, "saved_searches")


def get_saved_search_by_name(name: str):
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "saved_searches", condition=("name", name))
    if categories:
        return categories[0]


def get_saved_search_by_id(saved_search_id: int):
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "saved_searches", condition=("id", saved_search_id))
    if categories:
        return categories[0]


def get_search_for_saved_search(name: str) -> Optional[str]:
    if name:
        category = get_saved_search_by_name(name)
        if category:
            search = category.get("search")
            if search:
                return search
    return None


def add_saved_search(name: str, search: str, no_signal: bool = False):
    """Add a category to the database"""
    cat = sql.db_insert(settings.DB_PATH, "saved_searches", {"name": name, "search": search})
    if not no_signal:
        SAVED_SEARCHES_UPDATED.fire()
    return cat


def redefine_saved_search(saved_search_id: int, new_name: str, new_search: str = None, no_signal: bool = False) -> None:
    query = "UPDATE saved_searches SET name=?, search=? WHERE id=?"

    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, query, (new_name, new_search, saved_search_id))
    if not no_signal:
        SAVED_SEARCHES_UPDATED.fire()


def remove_saved_search(category_id: int, no_signal: bool = False) -> None:
    query = "DELETE FROM saved_searches WHERE id=?"

    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, query, (category_id,))

    if not no_signal:
        SAVED_SEARCHES_UPDATED.fire()
