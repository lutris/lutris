from sqlite3 import OperationalError

from lutris.database.games import get_games
from lutris.game import Game
from lutris.util.log import logger


def migrate():
    """Put all previously hidden games into the new '.hidden' category."""
    logger.info("Moving hidden games to the '.hidden' category")
    try:
        game_ids = [g["id"] for g in get_games(filters={"hidden": 1})]
    except OperationalError:
        # A brand-new DB will not have the hidden column at all,
        # so no migration is required.
        return

    for game_id in game_ids:
        game = Game(game_id)
        game.mark_as_hidden(True)
        logger.info("Migrated '%s' to '.hidden' category.", game.name)
