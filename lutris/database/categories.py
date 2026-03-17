import abc
import re
from collections import defaultdict
from itertools import repeat
from typing import Any, Dict, List, Optional, Set, Tuple, TypeAlias, Union

from lutris import settings
from lutris.database import games as games_db
from lutris.database import sql
from lutris.gui.widgets import NotificationSource
from lutris.util.strings import get_natural_sort_key

CATEGORIES_UPDATED = NotificationSource()

DbCategoryDict: TypeAlias = Dict[str, Any]


class _SmartCategory(abc.ABC):
    """Abstract class to define smart categories. Smart categories are automatically defined based on a rule."""

    @abc.abstractmethod
    def get_name(self) -> str:
        pass

    def get_game_ids(self) -> Set[str]:
        return set(game["id"] for game in self.get_games())

    @abc.abstractmethod
    def get_games(self) -> List[Any]:
        pass


class _SmartUncategorizedCategory(_SmartCategory):
    """A SmartCategory that resolves to all uncategorized games."""

    def get_name(self) -> str:
        return ".uncategorized"

    def get_game_ids(self) -> Set[str]:
        return get_uncategorized_game_ids()

    def get_games(self) -> List[Any]:
        return get_uncategorized_games()


# All smart categories should be added to this variable.
# TODO: Expose a way for the users to define new smart categories.
_SMART_CATEGORIES: List[_SmartCategory] = [_SmartUncategorizedCategory()]


def strip_category_name(name: str) -> str:
    """ "This strips the name given, and also removes extra internal whitespace."""
    name = (name or "").strip()
    if not is_reserved_category(name):
        name = re.sub(" +", " ", name)  # Remove excessive whitespaces
    return name


def is_reserved_category(name: str) -> bool:
    """True if name is None, blank or is a name Lutris uses internally, or
    starts with '.' for future expansion."""
    return not name or name[0] == "." or name in ["all", "favorite"]


def get_categories() -> List[Dict[str, Union[int, str]]]:
    """Get the list of every category in database."""
    # Categories look like [{"id": 1, "name": "My Category"}, ...]
    return sql.db_select(settings.DB_PATH, "categories")


def get_all_games_categories() -> Dict[str, List[int]]:
    games_categories = defaultdict(list)
    for row in sql.db_select(settings.DB_PATH, "games_categories"):
        games_categories[row["game_id"]].append(row["category_id"])
    return games_categories


def get_category_by_name(name: str) -> Optional[DbCategoryDict]:
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "categories", condition=("name", name))
    if categories:
        return categories[0]
    return None


def get_category_by_id(category_id: int) -> Optional[DbCategoryDict]:
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "categories", condition=("id", category_id))
    if categories:
        return categories[0]
    return None


def normalized_category_names(name: str, subname_allowed: bool = False) -> List[str]:
    """Searches for a category name case-insensitively and returns all matching names;
    if none match, it just returns 'name' as is.

    If subname_allowed is true but name is not a match for any category, we'll look for
    any category that contains the name as a substring instead before falling back to
    'name' itself."""
    query = "SELECT name FROM categories WHERE name=? COLLATE NOCASE"
    parameters = (name,)
    names = [cat["name"] for cat in sql.db_query(settings.DB_PATH, query, parameters)]

    if not names and subname_allowed:
        query = "SELECT name FROM categories WHERE name LIKE ? COLLATE NOCASE"
        parameters = (f"%{name}%",)
        names = [cat["name"] for cat in sql.db_query(settings.DB_PATH, query, parameters)]

    return names or [name]


def get_game_ids_for_categories(
    included_category_names: List[str] = None, excluded_category_names: List[str] = None
) -> List[str]:
    """Get the ids of games in database."""
    filters = []
    parameters = []

    if included_category_names:
        # Query that finds games in the included categories
        query = (
            "SELECT games.id FROM games "
            "INNER JOIN games_categories ON games.id = games_categories.game_id "
            "INNER JOIN categories ON categories.id = games_categories.category_id"
        )
        filters.append("categories.name IN (%s)" % ", ".join(repeat("?", len(included_category_names))))
        parameters.extend(included_category_names)
    else:
        # Or, if you listed none, we fall back to all games
        query = "SELECT games.id FROM games"

    if excluded_category_names:
        # Sub-query to exclude the excluded categories, if any.
        exclude_filter = (
            "NOT EXISTS(SELECT * FROM games_categories AS gc "
            "INNER JOIN categories AS c ON gc.category_id = c.id "
            "WHERE gc.game_id = games.id "
            "AND c.name IN (%s))" % ", ".join(repeat("?", len(excluded_category_names)))
        )
        filters.append(exclude_filter)
        parameters.extend(excluded_category_names)

    if filters:
        query += " WHERE %s" % " AND ".join(filters)

    result = set(game["id"] for game in sql.db_query(settings.DB_PATH, query, tuple(parameters)))
    for smart_cat in _SMART_CATEGORIES:
        if excluded_category_names is not None and smart_cat.get_name() in excluded_category_names:
            continue
        if included_category_names is not None and smart_cat.get_name() not in included_category_names:
            continue
        result |= smart_cat.get_game_ids()

    return list(sorted(result))


def get_uncategorized_game_ids() -> Set[str]:
    """Returns the ids of games that are in no categories. We do not count
    the 'favorites' category, but we do count '.hidden'- hidden games are hidden
    from this too."""
    query = (
        "SELECT games.id FROM games WHERE NOT EXISTS("
        "SELECT * FROM games_categories "
        "INNER JOIN categories ON categories.id = games_categories.category_id "
        "AND categories.name NOT IN ('all', 'favorite') "
        "WHERE games.id = games_categories.game_id)"
    )
    uncategorized = sql.db_query(settings.DB_PATH, query)
    return set(row["id"] for row in uncategorized)


def get_uncategorized_games() -> List[Any]:
    """Return a list of currently running games"""
    games = games_db.get_games_by_ids(get_uncategorized_game_ids())

    def get_key(g: Dict[str, Any]) -> Tuple[bool, str]:
        """Sort in the default order for Lutris- installed games first, then by name."""
        name = str(g.get("name") or "")
        installed = bool(g.get("installed"))
        return not installed, get_natural_sort_key(name)

    games.sort(key=get_key)
    return games


def get_categories_in_game(game_id: str) -> list[str]:
    """Get the categories of a game in database."""
    return get_categories_in_games([game_id]).get(game_id, [])


def get_categories_in_games(game_ids: list[str]) -> dict[str, list[str]]:
    """Get the categories of multiple games in database, returned as a dict mapping game ID to category names."""
    if not game_ids:
        return {}
    placeholders = ", ".join(repeat("?", len(game_ids)))
    query = (
        "SELECT games.id, categories.name FROM categories "
        "JOIN games_categories ON categories.id = games_categories.category_id "
        "JOIN games ON games.id = games_categories.game_id "
        f"WHERE games.id IN ({placeholders})"
    )
    result: dict[str, list[str]] = defaultdict(list)
    for row in sql.db_query(settings.DB_PATH, query, tuple(game_ids)):
        result[str(row["id"])].append(row["name"])
    return dict(result)


def add_category(category_name: str, no_signal: bool = False) -> int:
    """Add a category to the database"""
    cat = sql.db_insert(settings.DB_PATH, "categories", {"name": category_name})
    if not no_signal:
        CATEGORIES_UPDATED.fire()
    return cat


def redefine_category(category_id: int, new_name: str, no_signal: bool = False) -> None:
    query = "UPDATE categories SET name=? WHERE id=?"

    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, query, (new_name, category_id))
    if not no_signal:
        CATEGORIES_UPDATED.fire()


def remove_category(category_id: int, no_signal: bool = False) -> None:
    queries = ["DELETE FROM games_categories WHERE category_id=?", "DELETE FROM categories WHERE id=?"]

    for query in queries:
        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, query, (category_id,))

    if not no_signal:
        CATEGORIES_UPDATED.fire()


def add_game_to_category(game_id: str, category_id: int, no_signal: bool = False) -> None:
    """Add a category to a game"""
    sql.db_insert(settings.DB_PATH, "games_categories", {"game_id": game_id, "category_id": category_id})
    if not no_signal:
        CATEGORIES_UPDATED.fire()


def remove_category_from_game(game_id: str, category_id: int, no_signal: bool = False) -> None:
    """Remove a category from a game"""
    query = "DELETE FROM games_categories WHERE category_id=? AND game_id=?"
    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, query, (category_id, game_id))
    if not no_signal:
        CATEGORIES_UPDATED.fire()


def remove_unused_categories() -> None:
    """Remove all categories that have no games associated with them"""

    delete_orphaned_games = (
        "DELETE FROM games_categories "
        "WHERE NOT EXISTS(SELECT * FROM games WHERE game_id=id) "
        "OR NOT EXISTS(SELECT * FROM categories WHERE category_id=id)"
    )

    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, delete_orphaned_games, ())

    find_orphaned_categories = (
        "SELECT categories.* FROM categories "
        "LEFT JOIN games_categories ON categories.id = games_categories.category_id "
        "WHERE games_categories.category_id IS NULL"
    )

    empty_categories = sql.db_query(settings.DB_PATH, find_orphaned_categories)
    for category in empty_categories:
        if category["name"] == "favorite":
            continue

        delete_orphaned_categories = "DELETE FROM categories WHERE categories.id=?"
        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, delete_orphaned_categories, (category["id"],))
