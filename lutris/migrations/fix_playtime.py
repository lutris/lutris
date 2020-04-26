# Lutris Modules
from lutris.pga import PGA_DB, get_games
from lutris.util import sql
from lutris.util.log import logger


def fix_playtime(game):
    """Fix a temporary glitch that happened with the playtime implementation"""
    broken_playtime = game["playtime"]
    if not broken_playtime.endswith(" hrs"):
        return
    playtime = broken_playtime.split()[0]
    logger.warning("Fixing playtime %s => %s for %s", broken_playtime, playtime, game["name"])
    sql.db_update(PGA_DB, "games", {"playtime": playtime}, ("id", game["id"]))


def migrate():
    for game in get_games():
        if not game["playtime"]:
            continue
        fix_playtime(game)
