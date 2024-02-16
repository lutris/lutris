import json

from lutris import settings
from lutris.api import read_api_key
from lutris.database.games import add_or_update, get_games_where
from lutris.game import Game
from lutris.util import http
from lutris.util.log import logger

LIBRARY_URL = settings.SITE_URL + "/api/users/library"


def get_local_library():
    game_library = []
    pga_games = get_games_where(lastplayed__not=0)
    for pga_game in pga_games:
        if not pga_game["lastplayed"]:
            continue
        game_library.append(
            {
                "name": pga_game["name"],
                "slug": pga_game["slug"],
                "playtime": pga_game["playtime"],
                "lastplayed": pga_game["lastplayed"],
                "platform": pga_game["platform"],
                "runner": pga_game["runner"],
                "service": pga_game["service"],
                "service_id": pga_game["service_id"],
            }
        )
    return game_library


def sync_local_library():
    library = get_local_library()
    payload = json.dumps(library, indent=2)
    credentials = read_api_key()
    request = http.Request(
        LIBRARY_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Token " + credentials["token"],
        },
    )
    try:
        request.post(data=payload.encode())
    except http.HTTPError as ex:
        logger.error("Could not send local library to server: %s", ex)
        return None
    library_keys = set()
    duplicate_keys = set()
    library_map = {}
    for game in library:
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
            logger.info("Create %s", remote_key)
            add_or_update(
                name=remote_game["name"],
                slug=remote_game["slug"],
                runner=remote_game["runner"],
                platform=remote_game["platform"],
                lastplayed=remote_game["lastplayed"],
                service=remote_game["service"],
                service_id=remote_game["service_id"],
                installed=0,
            )
