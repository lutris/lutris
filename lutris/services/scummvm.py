import re
import os
from configparser import ConfigParser
from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig
from lutris.util import system

NAME = "ScummVM"
ICON = "scummvm"
ONLINE = False
INSTALLER_SLUG = "system-scummvm"
SCUMMVM_CONFIG_FILE = os.path.join(
    os.path.expanduser("~/.config/scummvm"), "scummvm.ini"
)


def mark_as_installed(scummvm_id, name, path):
    """Add scummvm from the auto-import"""
    logger.info("Setting %s as installed", name)
    slug = slugify(name)
    config_id = make_game_config_id(slug)
    game_id = pga.add_or_update(
        name=name,
        runner="scummvm",
        installer_slug=INSTALLER_SLUG,
        slug=slug,
        installed=1,
        configpath=config_id,
        directory=path,
    )
    config = LutrisConfig(runner_slug="scummvm", game_config_id=config_id)
    config.raw_game_config.update({"game_id": scummvm_id, "path": path})
    config.save()
    return game_id


def mark_as_uninstalled(game_info):
    logger.info("Uninstalling %s", game_info["name"])
    return pga.add_or_update(id=game_info["id"], installed=0)


def get_scummvm_games():
    if not system.path_exists(SCUMMVM_CONFIG_FILE):
        logger.info("No ScummVM config found")
        return []
    config = ConfigParser()
    config.read(SCUMMVM_CONFIG_FILE)
    config_sections = config.sections()
    for section in config_sections:
        if section == "scummvm":
            continue
        scummvm_id = section
        name = re.split(r" \(.*\)$", config[section]["description"])[0]
        path = config[section]["path"]
        yield (scummvm_id, name, path)


def sync_with_lutris():
    scummvm_games = {
        game["slug"]: game
        for game in pga.get_games_where(
            runner="scummvm", installer_slug=INSTALLER_SLUG, installed=1
        )
    }
    seen = set()

    for scummvm_id, name, path in get_scummvm_games():
        slug = slugify(name)
        seen.add(slug)
        if slug not in scummvm_games.keys():
            mark_as_installed(scummvm_id, name, path)
    for slug in set(scummvm_games.keys()).difference(seen):
        mark_as_uninstalled(scummvm_games[slug])
