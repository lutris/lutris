"""Handle Steam configuration"""
import os
from collections import OrderedDict, defaultdict

import requests

from lutris import settings
from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam.vdf import vdf_parse

STEAM_DATA_DIRS = (
    "~/.steam",
    "~/.local/share/steam",
    "~/.local/share/Steam",
    "~/.steam/steam",
    "~/.var/app/com.valvesoftware.Steam/data/steam",
    "~/.steam/debian-installation",
    "/usr/share/steam",
    "/usr/local/share/steam",
)


def get_steam_dir():
    """Main installation directory for Steam"""
    for candidate in STEAM_DATA_DIRS:
        path = system.fix_path_case(
            os.path.join(os.path.expanduser(candidate), "steamapps")
        )
        if path:
            return path[: -len("steamapps")]


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


def read_user_config(steam_data_dir):
    config_filename = os.path.join(steam_data_dir, "config/loginusers.vdf")
    if not system.path_exists(config_filename):
        return None
    with open(config_filename, "r") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    return config


def get_config_value(config, key):
    """Fetch a value from a configuration in a case insensitive way"""
    keymap = {k.lower(): k for k in config.keys()}
    if key not in keymap:
        logger.warning(
            "Config key %s not found in %s", key, ", ".join(list(config.keys()))
        )
        return
    return config[keymap[key.lower()]]


def get_user_steam_id(steam_data_dir):
    """Read user's SteamID from Steam config files"""
    user_config = read_user_config(steam_data_dir)
    if not user_config or "users" not in user_config:
        return
    last_steam_id = None
    for steam_id in user_config["users"]:
        last_steam_id = steam_id
        if get_config_value(user_config["users"][steam_id], "mostrecent") == "1":
            return steam_id
    return last_steam_id


def get_steam_library(steamid):
    """Return the list of games owned by a SteamID"""
    if not steamid:
        raise ValueError("Missing SteamID")
    steam_games_url = (
        "https://api.steampowered.com/"
        "IPlayerService/GetOwnedGames/v0001/"
        "?key={}&steamid={}&format=json&include_appinfo=1"
        "&include_played_free_games=1".format(
            settings.DEFAULT_STEAM_API_ID, steamid
        )
    )
    response = requests.get(steam_games_url)
    if response.status_code > 400:
        logger.error("Invalid response from steam: %s", response)
        return []
    json_data = response.json()
    response = json_data['response']
    if not response:
        logger.info("No games in response of %s", steam_games_url)
        return []
    if 'games' in response:
        return response['games']
    if 'game_count' in response and response['game_count'] == 0:
        return []
    logger.error("Weird response: %s", json_data)
    return []


def read_config(steam_data_dir):
    """Read the Steam configuration and return it as an object"""

    def get_entry_case_insensitive(config_dict, path):
        for key, _value in config_dict.items():
            if key.lower() == path[0].lower():
                if len(path) <= 1:
                    return config_dict[key]

                return get_entry_case_insensitive(config_dict[key], path[1:])
        raise KeyError(path[0])
    if not steam_data_dir:
        return None
    config_filename = os.path.join(steam_data_dir, "config/config.vdf")
    if not system.path_exists(config_filename):
        return None
    with open(config_filename, "r") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    try:
        return get_entry_case_insensitive(config, ["InstallConfigStore", "Software", "Valve", "Steam"])
    except KeyError as ex:
        logger.error("Steam config %s is empty: %s", config_filename, ex)


def get_steamapps_paths_for_platform(platform_name):
    from lutris.runners import winesteam, steam  # pylint: disable=import-outside-toplevel

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
