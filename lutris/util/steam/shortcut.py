"""Export lutris games to steam shortcuts"""
import binascii
import os
import shutil

from lutris.util import resources
from lutris.util.log import logger
from lutris.util.steam import vdf
from lutris.util.steam.config import search_recursive_in_steam_dirs


def get_config_path():
    path_suffix = "userdata/**/config/"
    config_paths = search_recursive_in_steam_dirs(path_suffix)
    if not config_paths:
        return None
    if len(config_paths) > 1:
        logger.warning("More than one config path found: %s", ", ".join(config_paths))
    return config_paths[0]


def get_shortcuts_vdf_path():
    config_path = get_config_path()
    if not config_path:
        return None
    return os.path.join(config_path, "shortcuts.vdf")


def get_artwork_target_path():
    config_path = get_config_path()
    if not config_path:
        return None
    artwork_path = os.path.join(config_path, "grid")
    if not os.path.exists(artwork_path):
        os.makedirs(artwork_path)
    return artwork_path


def vdf_file_exists():
    return bool(get_shortcuts_vdf_path)


def shortcut_exists(game):
    shortcut_path = get_shortcuts_vdf_path()
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [s for s in shortcuts if matches_appname(s, game)]
    return bool(shortcut_found)


def has_steamtype_runner(game):
    return game.runner_name == "steam"


def update_shortcut(game):
    if has_steamtype_runner(game):
        return
    if not shortcut_exists(game):
        create_shortcut(game)


def create_shortcut(game):
    shortcut_path = get_shortcuts_vdf_path()
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    existing_shortcuts = list(shortcuts)
    add_shortcut = [generate_shortcut(game)]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(existing_shortcuts + add_shortcut)
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
    shortcut_found = [
        s for s in shortcuts
        if matches_appname(s, game)
    ]
    if not shortcut_found:
        logger.warning("Couldn't remove shortcut for %s. Shortcut not found.", game)
        return

    other_shortcuts = [
        s for s in shortcuts
        if not matches_appname(s, game)
    ]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(other_shortcuts)
        }
    }
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def generate_shortcut(game):
    name = game.name
    slug = game.slug
    gameId = game.id
    icon = resources.get_icon_path(slug)
    lutris_binary = shutil.which("lutris")
    launch_options = f'lutris:rungameid/{gameId}'
    if lutris_binary == "/app/bin/lutris":
        lutris_binary = "flatpak"
        launch_options = "run net.lutris.Lutris " + launch_options
    start_dir = os.path.dirname(lutris_binary)

    return {
        'appid': "lutris-{}".format(slug),
        'AllowDesktopConfig': 1,
        'AllowOverlay': 1,
        'AppName': name,
        'Devkit': 0,
        'DevkitGameID': '',
        'Exe': f'"{lutris_binary}"',
        'IsHidden': 0,
        'LastPlayTime': 0,
        'LaunchOptions': launch_options,
        'OpenVR': 0,
        'ShortcutPath': '',
        'StartDir': f'"{start_dir}"',
        'icon': icon,
        'tags': {  # has been replaced by "collections" in steam. Tags are not visible in the UI anymore.
            '0': "Lutris"   # to identify generated shortcuts
        }
    }


def matches_appname(shortcut, game):
    """Test if the game seems to be the one a shortcut refers to."""
    appname = shortcut.get('AppName') or shortcut.get('appname')
    return appname and game.name in appname


def get_steam_shortcut_id(game):
    lutris_binary = shutil.which("lutris")
    exe = f'"{lutris_binary}"'
    appname = "{} ({})".format(game.name, game.runner_name)
    unique_id = ''.join([exe, appname])
    return binascii.crc32(str.encode(unique_id)) | 0x80000000


def set_artwork(game):
    shortcut_id = get_steam_shortcut_id(game)
    source_cover = resources.get_cover_path(game.slug)
    source_banner = resources.get_banner_path(game.slug)
    artwork_path = get_artwork_target_path()
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
