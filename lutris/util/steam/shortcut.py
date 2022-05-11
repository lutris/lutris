"""Export lutris games to steam shortcuts"""
import binascii
import os
import shutil

from lutris.util import resources
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
    return bool(get_shortcuts_vdf_path)


def matches_appid(shortcut, game):
    """Test if the game seems to be the one a shortcut refers to."""
    appid = shortcut.get('appid') or shortcut.get('AppId') or shortcut.get('AppID')
    return appid == "lutris-{}".format(game.slug)


def shortcut_exists(game):
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path:
        return False
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    return bool([s for s in shortcuts if matches_appid(s, game)])


def is_steam_game(game):
    return game.runner_name == "steam"


def create_shortcut(game):
    if is_steam_game(game):
        logger.warning("Not updating shortcut for Steam game")
        return
    logger.info("Creating Steam shortcut for %s", game)
    shortcut_path = get_shortcuts_vdf_path()
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(list(shortcuts) + [generate_shortcut(game)])
        }
    }
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))
    set_artwork(game)


def remove_shortcut(game):
    shortcut_path = get_shortcuts_vdf_path()
    if not shortcut_path:
        return
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    other_shortcuts = [s for s in shortcuts if not matches_appid(s, game)]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(other_shortcuts)
        }
    }
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def generate_shortcut(game):
    lutris_binary = shutil.which("lutris")
    launch_options = f'lutris:rungameid/{game.id}'
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "flatpak"
        launch_options = "run net.lutris.Lutris " + launch_options
    return {
        'appid': "lutris-{}".format(game.slug),
        'AllowDesktopConfig': 1,
        'AllowOverlay': 1,
        'AppName': game.name,
        'Devkit': 0,
        'DevkitGameID': '',
        'Exe': f'"{lutris_binary}"',
        'IsHidden': 0,
        'LastPlayTime': 0,
        'LaunchOptions': launch_options,
        'OpenVR': 0,
        'ShortcutPath': '',
        'StartDir': f'"{os.path.dirname(lutris_binary)}"',
        'icon': resources.get_icon_path(game.slug),
        'tags': {  # has been replaced by "collections" in steam. Tags are not visible in the UI anymore.
            '0': "Lutris"   # to identify generated shortcuts
        }
    }


def get_steam_shortcut_id(game):
    lutris_binary = shutil.which("lutris")
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "flatpak"
    exe = f'"{lutris_binary}"'
    unique_id = ''.join([exe, game.name])
    return binascii.crc32(str.encode(unique_id)) | 0x80000000


def set_artwork(game):
    shortcut_id = get_steam_shortcut_id(game)
    source_cover = resources.get_cover_path(game.slug)
    source_banner = resources.get_banner_path(game.slug)
    config_path = get_config_path()
    if not config_path:
        return None
    artwork_path = os.path.join(config_path, "grid")
    if not os.path.exists(artwork_path):
        os.makedirs(artwork_path)
    target_cover = os.path.join(artwork_path, "{}p.jpg".format(shortcut_id))
    target_banner = os.path.join(artwork_path, "{}_hero.jpg".format(shortcut_id))
    try:
        shutil.copyfile(source_cover, target_cover)
    except FileNotFoundError as ex:
        logger.error("Failed to copy cover to %s: %s", target_cover, ex)

    try:
        shutil.copyfile(source_banner, target_banner)
    except FileNotFoundError as ex:
        logger.error("Failed to copy banner to %s: %s", target_banner, ex)
