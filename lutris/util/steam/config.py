"""Handle Steam configuration"""
import os
from collections import OrderedDict

from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam.vdf import vdf_parse


def get_default_acf(appid, name):
    """Return a default configuration usable to
    create a runnable game in Steam"""

    userconfig = OrderedDict()
    userconfig["name"] = name
    userconfig["gameid"] = appid

    appstate = OrderedDict()
    appstate["appID"] = appid
    appstate["Universe"] = "1"
    appstate["StateFlags"] = "1026"
    appstate["installdir"] = name
    appstate["UserConfig"] = userconfig
    return {"AppState": appstate}


def read_config(steam_data_dir):
    """Read the Steam configuration and return it as an object"""
    config_filename = os.path.join(steam_data_dir, "config/config.vdf")
    if not system.path_exists(config_filename):
        return None
    with open(config_filename, "r") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    try:
        config = config["InstallConfigStore"]["Software"]["Valve"]["Steam"]
    except KeyError as ex:
        logger.error("Steam config %s is empty: %s", config_filename, ex)
        return None
    else:
        return config
