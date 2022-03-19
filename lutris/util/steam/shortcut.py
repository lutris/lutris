"""Export lutris games to steam shortcuts"""
import os
import shutil

from lutris.util import resources
from lutris.util.steam import vdf
from lutris.util.steam.config import search_recursive_in_steam_dirs

steam_tag = "Lutris"


def get_shortcuts_vdf_paths():
    path_suffix = "userdata/**/config/shortcuts.vdf"
    shortcuts_vdf = search_recursive_in_steam_dirs(path_suffix)
    return shortcuts_vdf


def get_first_shortcut_path():
    shortcuts_paths = get_shortcuts_vdf_paths()
    result = shortcuts_paths[0]
    return result


def shortcut_exists(game):
    with open(get_first_shortcut_path(), "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [
        s for s in shortcuts
        if game.name in s['AppName']
    ]
    if not shortcut_found:
        return False
    return True


def has_steamtype_runner(game):
    steamtype_runners = ['steam', 'winesteam']
    for runner in steamtype_runners:
        if runner == game.runner_name:
            return True
    return False


def update_shortcut(game):
    if has_steamtype_runner(game):
        return
    with open(get_first_shortcut_path(), "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [
        s for s in shortcuts
        if game.name in s['AppName']
    ]

    if not shortcut_found:
        create_shortcut(game)


def create_shortcut(game):
    with open(get_first_shortcut_path(), "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    existing_shortcuts = [s for s in shortcuts]
    add_shortcut = [generate_shortcut(game)]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(existing_shortcuts + add_shortcut)
        }
    }

    with open(get_first_shortcut_path(), "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def remove_shortcut(game):
    with open(get_first_shortcut_path(), "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    shortcut_found = [
        s for s in shortcuts
        if game.name in s['AppName']
    ]

    if not shortcut_found:
        return

    other_shortcuts = [
        s for s in shortcuts
        if game.name not in s['AppName']
    ]
    updated_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(other_shortcuts)
        }
    }
    with open(get_first_shortcut_path(), "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(updated_shortcuts))


def generate_shortcut(game):
    name = "{} ({})".format(game.name, game.runner_name)
    slug = game.slug
    gameId = game.id
    icon = resources.get_icon_path(slug)
    lutris_binary = shutil.which("lutris")
    start_dir = os.path.dirname(lutris_binary)

    return {
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
            '0': steam_tag   # to identify generated shortcuts
        }
    }
