"""Handle Steam configuration"""
import os
from collections import OrderedDict, defaultdict

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


def get_steamapps_paths_for_platform(platform_name):
    from lutris.runners import winesteam, steam

    runners = {"linux": steam.steam, "windows": winesteam.winesteam}
    runner = runners[platform_name]()
    return runner.get_steamapps_dirs()


def get_steamapps_paths(flat=False, platform=None):
    base_platforms = ["linux", "windows"]
    if flat:
        steamapps_paths = []
    else:
        steamapps_paths = defaultdict(list)

    if platform:
        if platform not in base_platforms:
            raise ValueError("Illegal value for Steam platform: %s" % platform)
        platforms = [platform]
    else:
        platforms = base_platforms

    for _platform in platforms:
        folders = get_steamapps_paths_for_platform(_platform)
        if flat:
            steamapps_paths += folders
        else:
            steamapps_paths[_platform] = folders

    return steamapps_paths
