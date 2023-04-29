"""Export lutris games to steam shortcuts"""
import binascii
import os
import re
import shlex
import shutil

from lutris.api import format_installer_url
from lutris.game import Game
from lutris.util import resources, system
from lutris.util.log import logger
from lutris.util.steam import vdf
from lutris.util.steam.config import search_recursive_in_steam_dirs


def get_config_path():
    config_paths = search_recursive_in_steam_dirs("userdata/**/config/")
    if not config_paths:
        return None
    return config_paths[0]


def get_shortcuts_vdf_path():
    config_path = get_config_path()
    if not config_path:
        return None
    return os.path.join(config_path, "shortcuts.vdf")


def vdf_file_exists():
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
    return game_id == str(game.id)


def get_shortcuts():
    """Return all Steam shortcuts"""
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path or not os.path.exists(shortcut_path):
        return []
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts']
    return shortcuts


def shortcut_exists(game):
    try:
        shortcuts = get_shortcuts()
        if not shortcuts:
            return False
        return bool([s for s in shortcuts.values() if matches_id(s, game)])
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
            shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    else:
        shortcuts = []

    shortcuts = list(shortcuts) + [generate_shortcut(game, launch_config_name)]

    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(shortcuts)
        }
    }
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))
    set_artwork(game)


def remove_shortcut(game):
    logger.info("Removing Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path or not os.path.exists(shortcut_path):
        return
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    other_shortcuts = [s for s in shortcuts if not matches_id(s, game)]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(other_shortcuts)
        }
    }
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def generate_preliminary_id(game):
    lutris_binary = shutil.which("lutris")
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "/usr/bin/flatpak"
    exe = f'"{lutris_binary}"'
    unique_id = ''.join([exe, game.name])
    top = binascii.crc32(str.encode(unique_id, 'utf-8')) | 0x80000000
    return (top << 32) | 0x02000000


def generate_appid(game):
    return str(generate_preliminary_id(game) >> 32)


def generate_shortcut_id(game):
    return (generate_preliminary_id(game) >> 32) - 0x100000000


def generate_shortcut(game, launch_config_name):
    lutris_binary = shutil.which("lutris")

    launch_options = format_installer_url({
        "action": "rungameid",
        "game_slug": game.id,
        "launch_config_name": launch_config_name
    })

    launch_options = shlex.quote(launch_options)

    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "/usr/bin/flatpak"
        launch_options = "run net.lutris.Lutris " + launch_options
    return {
        'appid': generate_shortcut_id(game),
        'AppName': game.name,
        'Exe': f'"{lutris_binary}"',
        'StartDir': f'"{os.path.dirname(lutris_binary)}"',
        'icon': resources.get_icon_path(game.slug),
        'LaunchOptions': launch_options,
        'IsHidden': 0,
        'AllowDesktopConfig': 1,
        'AllowOverlay': 1,
        'OpenVR': 0,
        'Devkit': 0,
        'DevkitOverrideAppID': 0,
        'LastPlayTime': 0,
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
    target_cover = os.path.join(artwork_path, "{}p.jpg".format(shortcut_id))
    target_banner = os.path.join(artwork_path, "{}_hero.jpg".format(shortcut_id))
    if not system.path_exists(target_cover, exclude_empty=True):
        try:
            shutil.copyfile(source_cover, target_cover)
            logger.debug("Copied %s cover to %s", game, target_cover)
        except FileNotFoundError as ex:
            logger.error("Failed to copy cover to %s: %s", target_cover, ex)
    if not system.path_exists(target_banner, exclude_empty=True):
        try:
            shutil.copyfile(source_banner, target_banner)
            logger.debug("Copied %s cover to %s", game, target_banner)
        except FileNotFoundError as ex:
            logger.error("Failed to copy banner to %s: %s", target_banner, ex)


def update_all_artwork():
    try:
        shortcut_path = get_shortcuts_vdf_path()
        if not shortcut_path or not os.path.exists(shortcut_path):
            return
        with open(shortcut_path, "rb") as shortcut_file:
            shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
        for shortcut in shortcuts:
            id_match = re.match(r".*lutris:rungameid/(\d+)", shortcut["LaunchOptions"])
            if not id_match:
                continue
            game_id = int(id_match.groups()[0])
            game = Game(game_id)
            set_artwork(game)
    except Exception as ex:
        logger.error("Failed to update steam shortcut artwork: %s", ex)
