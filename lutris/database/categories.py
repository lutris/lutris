from lutris import settings
from lutris.database import sql

PGA_DB = settings.PGA_DB


def get_categories():
    """Get the list of every category in database."""
    return sql.db_select(PGA_DB, "categories",)


def get_category(name):
    """Return a category by name"""
    categories = sql.db_select(PGA_DB, "categories", condition=("name", name))
    if categories:
        return categories[0]


def get_game_ids_for_category(category_name):
    """Get the ids of games in database."""
    query = (
        "select game_id from games_categories "
        "JOIN categories ON categories.id = games_categories.category_id "
        "WHERE categories.name=?"
    )
    return [
        game["game_id"]
        for game in sql.db_query(PGA_DB, query, (category_name, ))
    ]


def get_categories_in_game(game_id):
    """Get the categories of a game in database."""
    query = (
        "select categories.name from categories "
        "JOIN games_categories ON categories.id = games_categories.category_id "
        "JOIN games ON games.id = games_categories.game_id "
        "WHERE games.id=?"
    )
    return [
        category["name"]
        for category in sql.db_query(PGA_DB, query, (game_id,))
    ]


def add_category(category_name):
    """Add a category to the database"""
    return sql.db_insert(PGA_DB, "categories", {"name": category_name})


def add_game_to_category(game_id, category_id):
    """Add a category to a game"""
    return sql.db_insert(PGA_DB, "games_categories", {"game_id": game_id, "category_id": category_id})


def remove_category_from_game(game_id, category_id):
    """Remove a category from a game"""
    query = "DELETE FROM games_categories WHERE category_id=? AND game_id=?"
    with sql.db_cursor(PGA_DB) as cursor:
        sql.cursor_execute(cursor, query, (category_id, game_id))
