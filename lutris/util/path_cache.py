"""Keep track of game executables' presence"""

import json
import os
import time

from lutris import settings
from lutris.database.games import get_games
from lutris.game import Game
from lutris.gui.widgets import NotificationSource
from lutris.util import cache_single
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger

GAME_PATH_CACHE_PATH = os.path.join(settings.CACHE_DIR, "game-paths.json")


def get_game_paths():
    game_paths = {}
    all_games = get_games(filters={"installed": 1})
    for db_game in all_games:
        if db_game.runner in ("steam", "web"):
            continue
        game = Game(db_game["id"])
        path = game.get_path_from_config()
        if not path:
            continue
        game_paths[db_game["id"]] = path
    return game_paths


def build_path_cache(recreate=False):
    """Generate a new cache path"""
    if os.path.exists(GAME_PATH_CACHE_PATH) and not recreate:
        return
    start_time = time.time()
    with open(GAME_PATH_CACHE_PATH, "w", encoding="utf-8") as cache_file:
        game_paths = get_game_paths()
        json.dump(game_paths, cache_file, indent=2)
    end_time = time.time()
    get_path_cache.cache_clear()
    logger.debug("Game path cache built in %0.2f seconds", end_time - start_time)


def add_to_path_cache(game):
    """Add or update the path of a game in the cache"""
    logger.debug("Adding %s to path cache", game)
    path = game.get_path_from_config()
    if not path:
        logger.warning("No path for %s", game)
        return
    current_cache = read_path_cache()
    current_cache[game.id] = path
    with open(GAME_PATH_CACHE_PATH, "w", encoding="utf-8") as cache_file:
        json.dump(current_cache, cache_file, indent=2)
    get_path_cache.cache_clear()


@cache_single
def get_path_cache():
    """Return the contents of the path cache file; this
    dict is cached, so do not modify it."""
    return read_path_cache()


def read_path_cache():
    """Read the contents of the path cache file, and does not cache it."""
    with open(GAME_PATH_CACHE_PATH, encoding="utf-8") as cache_file:
        try:
            return json.load(cache_file)
        except json.JSONDecodeError:
            return {}


def remove_from_path_cache(game):
    logger.debug("Removing %s from path cache", game)
    current_cache = read_path_cache()
    if game.id not in current_cache:
        logger.warning("Game %s (id=%s) not in cache path", game, game.id)
        return
    del current_cache[game.id]
    with open(GAME_PATH_CACHE_PATH, "w", encoding="utf-8") as cache_file:
        json.dump(current_cache, cache_file, indent=2)
    get_path_cache.cache_clear()


class MissingGames:
    """This class is a singleton that holds a set of game-ids for games whose directories
    are missing. It is updated on a background thread, but there's a NotificationSource ('updated')
    that fires when that thread has made changes and exited, so that the UI cab update then."""

    def __init__(self):
        self.updated = NotificationSource()
        self.missing_game_ids = set()
        self._update_running = None

    @property
    def is_initialized(self):
        """True if the missing games have ever been updated."""
        return self._update_running is not None

    def update_all_missing(self) -> None:
        """This starts the check for all games; the actual list of game-ids will be obtained
        on the worker thread, and this method will start it."""

        if not self._update_running:
            self._update_running = True
            AsyncCall(self._update_missing_games, self._update_missing_games_cb)

    def _update_missing_games(self):
        """This is the method that runs on the worker thread; it checks each game given
        and returns True if any changes to missing_game_ids was made."""

        logger.debug("Checking for missing games")

        changed = False

        for game_id, path in get_path_cache().items():
            if path:
                old_status = game_id in self.missing_game_ids
                new_status = not os.path.exists(path)
                if old_status != new_status:
                    if new_status:
                        self.missing_game_ids.add(game_id)
                    else:
                        self.missing_game_ids.discard(game_id)
                    changed = True
        return changed

    def _update_missing_games_cb(self, changed, error):
        self._update_running = False

        if error:
            logger.exception("Unable to detect missing games: %s", error)
        elif changed:
            self.updated.fire()


MISSING_GAMES = MissingGames()
