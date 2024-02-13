import json

from lutris import settings
from lutris.api import read_api_key
from lutris.database.games import get_games
from lutris.util import http
from lutris.util.log import logger

LIBRARY_URL = settings.SITE_URL + "/api/users/library"


def get_local_library():
    game_library = []
    pga_games = get_games()
    for pga_game in pga_games:
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
    print(request.json)
