from sqlite3 import OperationalError

from lutris import settings
from lutris.database import sql
from lutris.game import Game
from lutris.util.log import logger


def migrate():
    """Put all previously hidden games into the new '.hidden' category."""
    logger.info("Moving hidden games to the '.hidden' category")
    try:
        # The hidden column has been removed from the schema, so it is no longer one of the
        # fields that can be used in a filtered query. A literal statement is used instead,
        # which keeps failing with OperationalError on databases that never had the column.
        hidden_games = sql.db_query(settings.DB_PATH, "select id from games where hidden = 1")
    except OperationalError:
        # A brand-new DB will not have the hidden column at all,
        # so no migration is required.
        return

    for game_id in [game["id"] for game in hidden_games]:
        game = Game(game_id)
        game.mark_as_hidden(True)
        logger.info("Migrated '%s' to '.hidden' category.", game.name)
