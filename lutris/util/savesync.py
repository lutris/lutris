import os
import shutil
from time import time

from lutris import settings
from lutris.util.log import logger


def sync_saves(game):
    saves_path = settings.read_setting("saves_path")
    if not saves_path:
        return
    game_saves_path = game.config.game_level["game"].get("saves")
    if not os.path.isabs(game_saves_path):
        return
    if os.path.isdir(game_saves_path):
        dest_path = os.path.join(saves_path, game.slug)
        os.makedirs(dest_path, exist_ok=True)
        shutil.copytree(game_saves_path, os.path.join(dest_path, str(int(time()))))
    else:
        logger.warning("Save path type not supported yet")
