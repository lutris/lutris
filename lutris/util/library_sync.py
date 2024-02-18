import json
import time

from lutris import settings
from lutris.api import read_api_key
from lutris.database.games import add_game, get_games, get_games_where
from lutris.game import Game
from lutris.util import http
from lutris.util.log import logger

LIBRARY_URL = settings.SITE_URL + "/api/users/library"


def get_local_library(since=None):
    game_library = []
    pga_games = get_games()

    for pga_game in pga_games:
        lastplayed = pga_game["lastplayed"] or 0
        installed_at = pga_game["installed_at"] or 0
        if since and lastplayed < since and installed_at < since:
            continue
        game_library.append(
            {
                "name": pga_game["name"],
                "slug": pga_game["slug"],
                "playtime": "%0.5f" % (pga_game["playtime"] or 0),
                "lastplayed": pga_game["lastplayed"] or 0,
                "platform": pga_game["platform"] or "",
                "runner": pga_game["runner"] or "",
                "service": pga_game["service"] or "",
                "service_id": pga_game["service_id"] or "",
            }
        )
    return game_library


def sync_local_library():
    if settings.read_setting("last_library_sync_at"):
        since = int(settings.read_setting("last_library_sync_at"))
    else:
        since = None
    local_library = get_local_library()
    local_library_updates = get_local_library(since=since)
    credentials = read_api_key()
    url = LIBRARY_URL
    if settings.read_setting("last_library_sync_at"):
        url += "?since=%s" % settings.read_setting("last_library_sync_at")
    request = http.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Token " + credentials["token"],
        },
    )
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
        key = (
            game["slug"],
            game["runner"] or "",
            game["platform"] or "",
            game["service"] or "",
        )
        if key in library_keys:
            duplicate_keys.add(key)
        library_keys.add(key)
        library_map[key] = game
        library_slugs.add(game["slug"])
    for remote_game in request.json:
        remote_key = (
            remote_game["slug"],
            remote_game["runner"] or "",
            remote_game["platform"] or "",
            remote_game["service"] or "",
        )
        if remote_key in duplicate_keys:
            logger.warning("Duplicate game %s, not syncing.", remote_key)
            continue
        if remote_key in library_map:
            changed = False
            conditions = {"slug": remote_game["slug"]}
            for key in ("runner", "platform", "service"):
                if remote_game[key]:
                    conditions[key] = remote_game[key]
            pga_game = get_games_where(**conditions)
            if len(pga_game) == 0:
                logger.error("No game found for %s", remote_key)
                continue
            if len(pga_game) > 1:
                logger.error("More than one game found for %s", remote_key)
                continue
            pga_game = pga_game[0]
            game = Game(pga_game["id"])
            if remote_game["playtime"] > game.playtime:
                game.playtime = remote_game["playtime"]
                changed = True
            if remote_game["lastplayed"] > game.lastplayed:
                game.lastplayed = remote_game["lastplayed"]
                changed = True
            if changed:
                game.save()
        else:
            if remote_game["slug"] in library_slugs:
                continue
            logger.info("Create %s", remote_key)
            add_game(
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
    settings.write_setting("last_library_sync_at", int(time.time()))


def delete_from_remote_library(games):
    for game in games:
        print(game)
        payload = {
            "name": game["name"],
            "slug": game["slug"],
            "runner": game["runner"],
            "platform": game["platform"],
            "lastplayed": game["lastplayed"],
            "playtime": game["playtime"],
            "service": game["service"],
            "service_id": game["service_id"],
        }
    credentials = read_api_key()
    url = LIBRARY_URL
    request = http.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Token " + credentials["token"],
        },
    )
    try:
        request.delete(data=json.dumps(payload).encode())
    except http.HTTPError as ex:
        logger.error(ex)
        return None
