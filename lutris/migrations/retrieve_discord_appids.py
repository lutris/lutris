from lutris import settings
from lutris.util.log import logger
from lutris.api import get_api_games
from lutris.database.games import get_games, sql


def migrate():
    """
    Update Games that does not have a Discord ID
    """
    logger.info("Updating Games Discord APP ID's")
    # Get Slugs from all games
    slugs_to_update = [game['slug'] for game in get_games()]
    # Retrieve game data
    games = get_api_games(slugs_to_update)
    for game in games:
        if not game['discord_id']:
            logger.info(f"{game['name']} doesn't have Discord APP Id")
            continue

        sql.db_update(
            settings.PGA_DB,
            "games",
            {"discord_id": game['discord_id']},
            {"slug": game['slug']}
        )
        logger.info(f"Updated {game['name']}")




