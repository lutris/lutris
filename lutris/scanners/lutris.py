import os
import re

from lutris.util.log import logger


def scan_directory(dirname):
    """Scan a directory for games previously installed with lutris"""
    folders = os.listdir(dirname)
    game_folders = []
    for folder in folders:
        if not os.path.isdir(os.path.join(dirname, folder)):
            continue
        if not re.match(r"^[a-z0-9-]*$", folder):
            logger.info("Skipping non matching folder %s", folder)
            continue
        game_folders.append(folder)
    for game_folder in game_folders:
        print(game_folder)
    print("%d games to check" % len(game_folders))
