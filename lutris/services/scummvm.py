"""Legacy ScummVM 'service', has to be ported to the current architecture"""
import os
import re
from configparser import ConfigParser
from gettext import gettext as _

from lutris.util import system
from lutris.util.log import logger

NAME = _("ScummVM")
ICON = "scummvm"
ONLINE = False
SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~/.config/scummvm"), "scummvm.ini")


def get_scummvm_games():
    """Return the available ScummVM games"""
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
