from lutris import settings
from lutris.api import get_api_games
from lutris.database import sql
from lutris.database.games import get_games
from lutris.util.log import logger


def migrate():
    """Add blank sortname field to games that do not yet have one"""
    logger.info("Adding blank sortname field to database")
    slugs_to_update = [game['slug'] for game in get_games()]
    games = get_api_games(slugs_to_update)
    for game in games:
        if 'sortname' not in game.keys() or game['sortname'] is None:
            sql.db_update(
                settings.DB_PATH,
                "games",
                {"sortname": ""},
                {"slug": game['slug']}
            )
        logger.info("Added blank sortname for %s", game['name'])
