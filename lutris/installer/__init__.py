"""Install script interpreter package."""
import enum

import yaml

from lutris.api import get_game_installers, normalize_installer
from lutris.util import system
from lutris.util.log import logger

AUTO_EXE_PREFIX = "_xXx_AUTO_"
AUTO_ELF_EXE = AUTO_EXE_PREFIX + "ELF_xXx_"
AUTO_WIN32_EXE = AUTO_EXE_PREFIX + "WIN32_xXx_"


class InstallationKind(enum.Enum):
    INSTALL = 0
    UPDATE = 1
    DLC = 2


def read_script(filename):
    """Return scripts from a local file"""
    logger.debug("Loading script(s) from %s", filename)
    with open(filename, "r", encoding='utf-8') as local_file:
        script = yaml.safe_load(local_file.read())
        if isinstance(script, list):
            return script
        if "results" in script:
            return script["results"]
        return [script]


def get_installers(game_slug=None, installer_file=None, revision=None):
    # check if installer is local or online
    if system.path_exists(installer_file):
        return [normalize_installer(i) for i in read_script(installer_file)]
    return get_game_installers(game_slug=game_slug, revision=revision)
