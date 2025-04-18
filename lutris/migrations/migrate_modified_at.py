from lutris import settings
from lutris.database import sql
from lutris.database.games import get_games
from lutris.util.log import logger


def migrate():
    """Add modified at field to all games"""
    logger.info("Adding modified at field to database")
    games = get_games()
    for game in games:
        if "modified_at" not in game.keys() or game["modified_at"] is None:
            installed_at = game["installed_at"]
            slug = game["slug"]
            logger.info("Using installed at %d as modified at for game %s", installed_at, slug)
            sql.db_update(settings.DB_PATH, "games", {"modified_at": installed_at}, {"slug": slug})
