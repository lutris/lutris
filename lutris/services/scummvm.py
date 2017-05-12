import re
import os
from configparser import ConfigParser
from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig

NAME = "ScummVM"
SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~/.config/scummvm"), "scummvm.ini")


def mark_as_installed(scummvm_id, name, path):
    """Add scummvm from the auto-import"""
    logger.info("Setting %s as installed" % name)
    slug = slugify(name)
    config_id = make_game_config_id(slug)
    game_id = pga.add_or_update(
        name=name,
        runner='scummvm',
        slug=slug,
        installed=1,
        configpath=config_id,
        directory=path
    )
    config = LutrisConfig(
        runner_slug='scummvm',
        game_config_id=config_id
    )
    config.raw_game_config.update({
        'game_id': scummvm_id,
        'path': path
    })
    config.save()
    return game_id


def sync_with_lutris():
    if not os.path.exists(SCUMMVM_CONFIG_FILE):
        logger.info("No ScummVM config found")
        return
    config = ConfigParser()
    config.read(SCUMMVM_CONFIG_FILE)
    config_sections = config.sections()
    for section in config_sections:
        if section == 'scummvm':
            continue
        scummvm_id = section
        name = re.split(' \(.*\)$', config[section]["description"])[0]
        path = config[section]['path']
        mark_as_installed(scummvm_id, name, path)
