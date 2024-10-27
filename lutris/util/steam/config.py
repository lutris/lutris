"""Handle Steam configuration"""

import os
from collections import OrderedDict

import requests

from lutris import settings
from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam.steamid import SteamID
from lutris.util.steam.vdfutils import vdf_parse

STEAM_DATA_DIRS = (
    "~/.steam/debian-installation",
    "~/.steam",
    "~/.local/share/steam",
    "~/.local/share/Steam",
    "~/snap/steam/common/.local/share/Steam",
    "~/.steam/steam",
    "~/.var/app/com.valvesoftware.Steam/data/steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
    "/usr/share/steam",
    "/usr/local/share/steam",
)
STEAM_ACCOUNT_SETTING = "active_steam_account"


def get_steam_dir():
    """Main installation directory for Steam"""
    steam_dir = search_in_steam_dirs("steamapps")
    if steam_dir:
        return steam_dir[: -len("steamapps")]


def search_in_steam_dirs(file):
    """Find the (last) file/dir in all the Steam directories"""
    for candidate in STEAM_DATA_DIRS:
        path = system.fix_path_case(os.path.join(os.path.expanduser(candidate), file))
        if path and system.path_exists(path):
            return path


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


def read_user_config():
    config_filename = search_in_steam_dirs("config/loginusers.vdf")
    if not system.path_exists(config_filename):
        return None
    with open(config_filename, "r", encoding="utf-8") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    return config


def get_config_value(config: dict, key: str):
    """Fetch a value from a configuration in a case insensitive way"""
    keymap = {k.lower(): k for k in config.keys()}
    if key not in keymap:
        logger.warning("Config key %s not found in %s", key, ", ".join(list(config.keys())))
        return
    return config[keymap[key.lower()]]


def get_user_data_dirs():
    """Return the list of available Steam user config directories (using a SteamID32)
    and the base path where the settings are located (Returns the 1st location found)
    """
    for steam_dir in STEAM_DATA_DIRS:
        userdata_path = os.path.join(os.path.expanduser(steam_dir), "userdata")
        if not os.path.exists(userdata_path):
            continue
        user_ids = [f for f in os.listdir(userdata_path) if f.isnumeric()]
        if user_ids:
            return userdata_path, user_ids
    return "", []


def get_steam_users() -> list:
    """Return a list of available Steam users.
    Most recently used account is 1st in the list."""
    steam_users = []
    user_config = read_user_config()
    if not user_config or "users" not in user_config:
        return []
    most_recent = None
    for steam_id, account in user_config["users"].items():
        account["steamid64"] = steam_id
        if get_config_value(account, "mostrecent") == "1":
            most_recent = account
        else:
            steam_users.append(account)
    if most_recent:
        steam_users = [most_recent] + steam_users
    return steam_users


def get_active_steamid64() -> str:
    """Return the currently active Steam ID"""
    steam_ids = [u["steamid64"] for u in get_steam_users()]
    active_steam_id = settings.read_setting(STEAM_ACCOUNT_SETTING)
    if active_steam_id in steam_ids:
        return active_steam_id
    if steam_ids:
        return steam_ids[0]
    return ""


def convert_steamid64_to_steamid32(steamid64: str) -> str:
    """Return the 32-bit variant of SteamIDs, used for folder names in userdata"""
    if not steamid64.isnumeric():
        return ""
    steam_id = SteamID.from_steamid64(int(steamid64))
    return str(steam_id.get_32_bit_community_id())


def get_steam_library(steamid):
    """Return the list of games owned by a SteamID"""
    if not steamid:
        raise ValueError("Missing SteamID")
    steam_games_url = (
        "https://api.steampowered.com/"
        "IPlayerService/GetOwnedGames/v0001/"
        "?key={}&steamid={}&format=json&include_appinfo=1"
        "&include_played_free_games=1".format(settings.STEAM_API_KEY, steamid)
    )
    response = requests.get(steam_games_url, timeout=30)
    if response.status_code > 400:
        logger.error("Invalid response from steam: %s", response)
        return []
    json_data = response.json()
    response = json_data["response"]
    if not response:
        logger.info("No games in response of %s", steam_games_url)
        return []
    if "games" in response:
        return response["games"]
    if "game_count" in response and response["game_count"] == 0:
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
    with open(config_filename, "r", encoding="utf-8") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    try:
        return get_entry_case_insensitive(config, ["InstallConfigStore", "Software", "Valve", "Steam"])
    except KeyError as ex:
        logger.error("Steam config %s is empty: %s", config_filename, ex)


def read_library_folders(steam_data_dir):
    """Read the Steam Library Folders config and return it as an object"""

    def get_entry_case_insensitive(library_dict, path):
        for key, value in library_dict.items():
            if key.lower() == path[0].lower():
                if len(path) <= 1:
                    return value
                return get_entry_case_insensitive(library_dict[key], path[1:])
            raise KeyError(path[0])

    if not steam_data_dir:
        return None
    library_filename = os.path.join(steam_data_dir, "config/libraryfolders.vdf")
    if not system.path_exists(library_filename):
        return None
    with open(library_filename, "r", encoding="utf-8") as steam_library_file:
        library = vdf_parse(steam_library_file, {})
        # The contentstatsid key is unused and causes problems when looking for library paths.
        library["libraryfolders"].pop("contentstatsid", None)
    try:
        return get_entry_case_insensitive(library, ["libraryfolders"])
    except KeyError as ex:
        logger.error("Steam libraryfolders %s is empty: %s", library_filename, ex)


def get_steam_config():
    """Return the "Steam" part of Steam's config.vdf as a dict."""
    return read_config(get_steam_dir())


def get_library_config():
    """Return the "libraryfolders" part of Steam's libraryfolders.vdf as a dict"""
    return read_library_folders(get_steam_dir())


def get_steamapps_dirs():
    """Return a list of the Steam library main + custom folders."""
    dirs = []
    # Extra colon-separated compatibility tools dirs environment variable
    if "STEAM_EXTRA_COMPAT_TOOLS_PATHS" in os.environ:
        dirs += os.getenv("STEAM_EXTRA_COMPAT_TOOLS_PATHS").split(":")
    # Main steamapps dir and compatibilitytools.d dir
    for data_dir in STEAM_DATA_DIRS:
        for _dir in ["steamapps", "compatibilitytools.d"]:
            abs_dir = os.path.join(os.path.expanduser(data_dir), _dir)
            abs_dir = system.fix_path_case(abs_dir)
            if abs_dir and os.path.isdir(abs_dir):
                dirs.append(abs_dir)

    # Custom dirs
    steam_config = get_steam_config()
    if steam_config:
        i = 1
        while "BaseInstallFolder_%s" % i in steam_config:
            path = steam_config["BaseInstallFolder_%s" % i] + "/steamapps"
            path = system.fix_path_case(path)
            if path and os.path.isdir(path):
                dirs.append(path)
            i += 1

    # New Custom dirs
    library_config = get_library_config()
    if library_config:
        paths = []
        for entry in library_config.values():
            if "mounted" in entry:
                if entry.get("path") and entry.get("mounted") == "1":
                    path = system.fix_path_case(entry.get("path") + "/steamapps")
                    paths.append(path)
            else:
                path = system.fix_path_case(entry.get("path") + "/steamapps")
                paths.append(path)
        for path in paths:
            if path and os.path.isdir(path):
                dirs.append(path)
    return system.list_unique_folders(dirs)
