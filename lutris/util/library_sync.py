import json
import sys
import time
from typing import List, Optional

from lutris import settings
from lutris.api import read_api_key
from lutris.database.categories import (
    add_category,
    add_game_to_category,
    get_all_games_categories,
    get_categories,
    remove_category_from_game,
)
from lutris.database.games import add_game, get_games, get_games_where
from lutris.game import Game
from lutris.gui.widgets import NotificationSource
from lutris.util import http
from lutris.util.log import logger

LIBRARY_URL = settings.SITE_URL + "/api/users/library"
LOCAL_LIBRARY_SYNCING = NotificationSource()
LOCAL_LIBRARY_SYNCED = NotificationSource()
LOCAL_LIBRARY_UPDATED = NotificationSource()
_IS_LOCAL_LIBRARY_SYNCING = False


def is_local_library_syncing():
    """True if the library is syncing now; attempting to sync again will do nothing if so."""
    # This provides access to the mutable global _IS_LOCAL_LIBRARY_SYNCING in a safer
    # way; if you just import the global directly you get a copy of its current state at import
    # time which is not very useful.
    return _IS_LOCAL_LIBRARY_SYNCING


class LibrarySyncer:
    def __init__(self):
        self.categories = self._load_categories()
        self.category_ids = self._load_categories(reverse=True)
        self.games_categories = get_all_games_categories()

    def _load_categories(self, reverse=False):
        """Create a mapping of category ID to name or name to ID if reverse is used"""
        key = "name" if reverse else "id"
        value = "id" if reverse else "name"
        return {r[key]: r[value] for r in get_categories()}

    def _get_request(self, since=None):
        """Return a request object and ensures authentication to the Lutris API"""
        credentials = read_api_key()
        if not credentials:
            return
        url = LIBRARY_URL
        if since:
            url += "?since=%s" % since
        return http.Request(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Token " + credentials["token"],
            },
        )

    def _make_game_key(self, game):
        """Create a unique-ish key used to discriminate between games"""
        return (
            game["slug"],
            game["runner"] or "",
            game["platform"] or "",
            game["service"] or "",
        )

    def _get_game(self, remote_game) -> Optional[Game]:
        """Return a Game instance from a remote API record"""
        conditions = {"slug": remote_game["slug"]}
        for cond_key in ("runner", "platform", "service"):
            if remote_game[cond_key]:
                conditions[cond_key] = remote_game[cond_key]
        pga_game = get_games_where(**conditions)
        if len(pga_game) == 0:
            logger.error("No game found for %s", remote_game["slug"])
            return None
        if len(pga_game) > 1:
            logger.error("More than one game found for %s", remote_game["slug"])
            return None
        pga_game = pga_game[0]
        return Game(pga_game["id"])

    def _create_new_game(self, remote_game):
        """Create a new local game from a remote record"""
        logger.info("Create %s", remote_game["slug"])
        game_id = add_game(
            name=remote_game["name"],
            slug=remote_game["slug"],
            runner=remote_game["runner"],
            platform=remote_game["platform"],
            lastplayed=remote_game["lastplayed"],
            playtime=remote_game["playtime"],
            service=remote_game["service"],
            service_id=remote_game["service_id"],
            installed=0,
        )
        for category in remote_game["categories"]:
            self._ensure_category(category)
            add_game_to_category(game_id, self.category_ids[category])

    def _ensure_category(self, category):
        """Make sure a given category exists in the database, create it if not"""
        if category not in self.categories.values():
            add_category(category)
            self.categories = self._load_categories()
            self.category_ids = self._load_categories(reverse=True)

    def _update_categories(self, game: Game, remote_game: dict):
        """Update the categories of a local game"""
        game_categories: List[str] = game.get_categories()
        remote_categories: List[str] = remote_game["categories"]
        for category in game_categories:
            if category not in remote_categories:
                remove_category_from_game(game.id, self.category_ids[category])
        for category in remote_categories:
            if category not in game_categories:
                self._ensure_category(category)
                add_game_to_category(game.id, self.category_ids[category])

    def _db_game_to_api(self, db_game):
        """Serialize DB game entry to a payload compatible with the API"""
        try:
            categories = [self.categories[cat_id] for cat_id in self.games_categories.get(db_game["id"], [])]
        except KeyError:
            self.panic_at_the_key_error(db_game, "id")
            return
        return {
            "name": db_game["name"],
            "slug": db_game["slug"],
            "runner": db_game["runner"] or "",
            "platform": db_game["platform"] or "",
            "playtime": "%0.5f" % (db_game["playtime"] or 0),
            "lastplayed": db_game["lastplayed"] or 0,
            "service": db_game["service"] or "",
            "service_id": db_game["service_id"] or "",
            "categories": categories,
        }

    def panic_at_the_key_error(self, db_game, key):
        logger.error((("!" * 120) + "\n") * 240)
        logger.exception("No installed_at key in db_game. CORRUPTED OBJECT!!!!!")
        logger.exception("OBJECT CONTENT %s", db_game)
        logger.error((("!" * 120) + "\n") * 24)
        sys.exit(-999)

    def _db_games_to_api(self, db_games, since=None):
        """Serialize a collection of games to API format, optionally filtering by date"""
        payload = []
        for db_game in db_games:
            lastplayed = db_game["lastplayed"] or 0
            try:
                installed_at = db_game["installed_at"] or 0
            except KeyError:
                self.panic_at_the_key_error(db_game, "installed_at")

            if since and lastplayed < since and installed_at < since:
                continue
            payload.append(self._db_game_to_api(db_game))
        return payload

    def sync_local_library(self, force: bool = False) -> None:
        """Sync task to send recent changes to the server and sync back server changes to the local client"""
        global _IS_LOCAL_LIBRARY_SYNCING

        if _IS_LOCAL_LIBRARY_SYNCING:
            return

        if not force and settings.read_setting("last_library_sync_at"):
            since = int(settings.read_setting("last_library_sync_at"))
        else:
            since = None
        all_games = get_games()
        local_library = self._db_games_to_api(all_games)
        local_library_updates = self._db_games_to_api(all_games, since=since)

        request = self._get_request(since)
        if not request:
            return

        LOCAL_LIBRARY_SYNCING.fire()
        any_local_changes = False
        try:
            _IS_LOCAL_LIBRARY_SYNCING = True
            try:
                request.post(data=json.dumps(local_library_updates).encode())
            except http.HTTPError as ex:
                logger.error("Could not send local library to server: %s", ex)
                return None
            library_keys = set()
            duplicate_keys = set()
            library_map = {}
            library_slugs = set()
            for game in local_library:
                library_key = self._make_game_key(game)
                if library_key in library_keys:
                    duplicate_keys.add(library_key)
                library_keys.add(library_key)
                library_map[library_key] = game
                library_slugs.add(game["slug"])

            for remote_game in request.json:
                remote_key = self._make_game_key(remote_game)
                if remote_key in duplicate_keys:
                    logger.warning("Duplicate game %s, not syncing.", remote_key)
                    continue
                if remote_key in library_map:
                    game = self._get_game(remote_game)
                    if not game:
                        continue
                    changed = False
                    if remote_game["playtime"] > game.playtime:
                        game.playtime = remote_game["playtime"]
                        changed = True
                    if remote_game["lastplayed"] > game.lastplayed:
                        game.lastplayed = remote_game["lastplayed"]
                        changed = True
                    if set(remote_game["categories"]) != set(game.get_categories()):
                        self._update_categories(game, remote_game)
                    if changed:
                        any_local_changes = True
                        game.save()
                else:
                    if remote_game["slug"] in library_slugs:
                        continue
                    self._create_new_game(remote_game)
                    any_local_changes = True

            settings.write_setting("last_library_sync_at", int(time.time()))
        finally:
            _IS_LOCAL_LIBRARY_SYNCING = False
            LOCAL_LIBRARY_SYNCED.fire()
            if any_local_changes:
                LOCAL_LIBRARY_UPDATED.fire()

    def delete_from_remote_library(self, games):
        """Task to delete a game entry from the remote library"""
        request = self._get_request()
        if not request:
            return
        try:
            request.delete(data=json.dumps(self._db_games_to_api(games)).encode())
        except http.HTTPError as ex:
            logger.error(ex)
            return None
        return request.json
