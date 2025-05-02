"""Export lutris games to Steam shortcuts"""

import binascii
import os
import re
import shlex
import shutil

from lutris.api import format_installer_url
from lutris.util import resources, system
from lutris.util.log import logger
from lutris.util.steam import vdf
from lutris.util.steam.config import convert_steamid64_to_steamid32, get_active_steamid64, get_user_data_dirs


def get_config_path() -> str:
    """Return config path for a Steam user"""
    userdatapath, user_ids = get_user_data_dirs()
    if not user_ids:
        return ""
    user_id = user_ids[0]
    if len(user_ids) > 1:
        active_account = get_active_steamid64()
        if active_account:
            active_account32 = convert_steamid64_to_steamid32(active_account)
            if active_account32 in user_ids:
                user_id = active_account32
    return os.path.join(userdatapath, user_id, "config")


def get_shortcuts_vdf_path() -> str:
    config_path = get_config_path()
    if not config_path:
        return ""
    return os.path.join(config_path, "shortcuts.vdf")


def vdf_file_exists() -> bool:
    try:
        return bool(get_shortcuts_vdf_path())
    except Exception as ex:
        logger.error("Failed to locate vdf file: %s", ex)
        return False


def matches_id(shortcut, game):
    """Test if the game seems to be the one a shortcut refers to."""
    id_match = re.match(r".*lutris:rungameid/(\d+)", shortcut.get("LaunchOptions", ""))
    if not id_match:
        return False
    game_id = id_match.groups()[0]
    return game_id == game.id


def get_shortcuts():
    """Return all Steam shortcuts"""
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path or not os.path.exists(shortcut_path):
        return []
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())["shortcuts"]
    return shortcuts


def shortcut_exists(game):
    try:
        shortcuts = get_shortcuts()
        if not shortcuts:
            return False
        return any(s for s in shortcuts.values() if matches_id(s, game))
    except Exception as ex:
        logger.error("Failed to read shortcut vdf file: %s", ex)
        return False


def is_steam_game(game):
    return game.runner_name == "steam"


def create_shortcut(game, launch_config_name=None):
    if is_steam_game(game):
        logger.warning("Not updating shortcut for Steam game")
        return
    logger.info("Creating Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    if os.path.exists(shortcut_path):
        with open(shortcut_path, "rb") as shortcut_file:
            shortcuts = vdf.binary_loads(shortcut_file.read())["shortcuts"].values()
    else:
        shortcuts = []

    shortcuts = list(shortcuts) + [generate_shortcut(game, launch_config_name)]

    updated_shortcuts = {"shortcuts": {str(index): elem for index, elem in enumerate(shortcuts)}}
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))
    set_artwork(game)


def remove_shortcut(game):
    logger.info("Removing Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path or not os.path.exists(shortcut_path):
        return
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())["shortcuts"].values()
    other_shortcuts = [s for s in shortcuts if not matches_id(s, game)]
    # Quit early if no shortcut is removed
    if len(shortcuts) == len(other_shortcuts):
        return
    updated_shortcuts = {"shortcuts": {str(index): elem for index, elem in enumerate(other_shortcuts)}}
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def generate_preliminary_id(game):
    lutris_binary = shutil.which("lutris")
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "/usr/bin/flatpak"
    exe = f'"{lutris_binary}"'
    unique_id = "".join([exe, game.name])
    top = binascii.crc32(str.encode(unique_id, "utf-8")) | 0x80000000
    return (top << 32) | 0x02000000


def generate_appid(game):
    return str(generate_preliminary_id(game) >> 32)


def generate_shortcut_id(game):
    return (generate_preliminary_id(game) >> 32) - 0x100000000


def generate_shortcut(game, launch_config_name):
    lutris_binary = shutil.which("lutris")

    launch_options = format_installer_url(
        {"action": "rungameid", "game_slug": game.id, "launch_config_name": launch_config_name}
    )

    launch_options = shlex.quote(launch_options)

    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "/usr/bin/flatpak"
        launch_options = "run net.lutris.Lutris " + launch_options
    return {
        "appid": generate_shortcut_id(game),
        "AppName": game.name,
        "Exe": f'"{lutris_binary}"',
        "StartDir": f'"{os.path.dirname(lutris_binary)}"',
        "icon": resources.get_icon_path(game.slug),
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
    }


def set_artwork(game):
    config_path = get_config_path()
    if not config_path:
        return None
    artwork_path = os.path.join(config_path, "grid")
    if not os.path.exists(artwork_path):
        os.makedirs(artwork_path)
    shortcut_id = generate_appid(game)
    source_cover = resources.get_cover_path(game.slug)
    source_banner = resources.get_banner_path(game.slug)
    source_icon = resources.get_icon_path(game.slug)
    assets = [
        ("grid horizontal", source_banner, os.path.join(artwork_path, "{}.jpg".format(shortcut_id))),
        ("grid vertical", source_cover, os.path.join(artwork_path, "{}p.jpg".format(shortcut_id))),
        ("hero", source_banner, os.path.join(artwork_path, "{}_hero.jpg".format(shortcut_id))),
        ("icon", source_icon, os.path.join(artwork_path, "{}_icon.jpg".format(shortcut_id))),
    ]
    for name, source, target in assets:
        if not system.path_exists(target, exclude_empty=True):
            try:
                shutil.copyfile(source, target)
                logger.debug("Copied %s %s asset to %s", game, name, target)
            except FileNotFoundError as ex:
                logger.error("Failed to copy %s %s asset to %s: %s", game, name, target, ex)
