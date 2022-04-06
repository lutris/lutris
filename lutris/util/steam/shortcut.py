"""Export lutris games to steam shortcuts"""
import binascii
import os
import shutil

from lutris.util import resources
from lutris.util.steam import vdf
from lutris.util.steam.config import search_recursive_in_steam_dirs


def get_shortcuts_vdf_paths():
    path_suffix = "userdata/**/config/shortcuts.vdf"
    shortcuts_vdf = search_recursive_in_steam_dirs(path_suffix)
    return shortcuts_vdf


def get_artwork_target_paths():
    path_suffix = "userdata/**/config/grid"
    target_paths = search_recursive_in_steam_dirs(path_suffix)
    return target_paths


def vdf_file_exists():
    shortcuts_paths = get_shortcuts_vdf_paths()
    if len(shortcuts_paths) > 0:
        return True
    return False


def shortcut_exists(game, shortcut_path):
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [
        s for s in shortcuts
        if matches_appname(s, game)
    ]
    if not shortcut_found:
        return False
    return True


def all_shortcuts_set(game):
    paths_shortcut = get_shortcuts_vdf_paths()
    shortcuts_found = 0
    for shortcut_path in paths_shortcut:
        with open(shortcut_path, "rb") as shortcut_file:
            shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
        shortcut_found = [
            s for s in shortcuts
            if matches_appname(s, game)
        ]
        shortcuts_found += len(shortcut_found)

    if len(paths_shortcut) == shortcuts_found:
        return True
    return False


def has_steamtype_runner(game):
    steamtype_runners = ['steam', 'winesteam']
    for runner in steamtype_runners:
        if runner == game.runner_name:
            return True
    return False


def update_shortcut(game):
    if has_steamtype_runner(game):
        return
    for shortcut_path in get_shortcuts_vdf_paths():
        if not shortcut_exists(game, shortcut_path):
            create_shortcut(game, shortcut_path)


def remove_all_shortcuts(game):
    for shortcut_path in get_shortcuts_vdf_paths():
        remove_shortcut(game, shortcut_path)


def create_shortcut(game, shortcut_path):
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


def remove_shortcut(game, shortcut_path):
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [
        s for s in shortcuts
        if matches_appname(s, game)
    ]

    if not shortcut_found:
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
        'LaunchOptions': f'lutris:rungameid/{gameId}',
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
    target_cover = "{}p.jpg".format(shortcut_id)
    target_banner = "{}_hero.jpg".format(shortcut_id)
    for target_path in get_artwork_target_paths():
        target_cover = os.path.join(target_path, target_cover)
        target_banner = os.path.join(target_path, target_banner)
        try:
            shutil.copyfile(source_cover, target_cover)
            shutil.copyfile(source_banner, target_banner)
        except FileNotFoundError:
            pass
