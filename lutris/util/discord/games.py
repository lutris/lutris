__all__ = ['GAMES_IDS']

import os
import json

from lutris.util import datapath
from lutris.util.log import logger


_GAME_IDS_PATH = os.path.join(datapath.get(), 'discord')
_GAME_IDS_JSON = os.path.join(_GAME_IDS_PATH, 'games-ids.json')

if not os.path.exists(_GAME_IDS_JSON):
    logger.exception("game-ids.json for Discord Rich Presence not found")
    GAME_IDS = {}
else:
    with open(_GAME_IDS_JSON, 'r') as games_json:
        GAMES_IDS = json.load(games_json)
