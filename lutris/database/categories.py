import re
from itertools import repeat

from lutris import settings
from lutris.database import sql


def strip_category_name(name):
    """"This strips the name given, and also removes extra internal whitespace."""
    name = (name or "").strip()
    if not is_reserved_category(name):
        name = re.sub(' +', ' ', name)  # Remove excessive whitespaces
    return name


def is_reserved_category(name):
    """True of name is None, blank or is a name Lutris uses internally, or
    starts with '.' for future expansion."""
    return not name or name[0] == "." or name in ["all", "favorite"]


def get_categories():
    """Get the list of every category in database."""
    return sql.db_select(settings.DB_PATH, "categories", )


def get_category(name):
    """Return a category by name"""
    categories = sql.db_select(settings.DB_PATH, "categories", condition=("name", name))
    if categories:
        return categories[0]


def get_game_ids_for_categories(included_category_names=None, excluded_category_names=None):
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

    return [
        game["id"]
        for game in sql.db_query(settings.DB_PATH, query, tuple(parameters))
    ]


def get_categories_in_game(game_id):
    """Get the categories of a game in database."""
    query = (
        "SELECT categories.name FROM categories "
        "JOIN games_categories ON categories.id = games_categories.category_id "
        "JOIN games ON games.id = games_categories.game_id "
        "WHERE games.id=?"
    )
    return [
        category["name"]
        for category in sql.db_query(settings.DB_PATH, query, (game_id,))
    ]


def add_category(category_name):
    """Add a category to the database"""
    return sql.db_insert(settings.DB_PATH, "categories", {"name": category_name})


def add_game_to_category(game_id, category_id):
    """Add a category to a game"""
    return sql.db_insert(settings.DB_PATH, "games_categories", {"game_id": game_id, "category_id": category_id})


def remove_category_from_game(game_id, category_id):
    """Remove a category from a game"""
    query = "DELETE FROM games_categories WHERE category_id=? AND game_id=?"
    with sql.db_cursor(settings.DB_PATH) as cursor:
        sql.cursor_execute(cursor, query, (category_id, game_id))


def remove_unused_categories():
    """Remove all categories that have no games associated with them"""
    query = (
        "SELECT categories.* FROM categories "
        "LEFT JOIN games_categories ON categories.id = games_categories.category_id "
        "WHERE games_categories.category_id IS NULL"
    )

    empty_categories = sql.db_query(settings.DB_PATH, query)
    for category in empty_categories:
        if category['name'] == 'favorite':
            continue

        query = "DELETE FROM categories WHERE categories.id=?"
        with sql.db_cursor(settings.DB_PATH) as cursor:
            sql.cursor_execute(cursor, query, (category['id'],))
