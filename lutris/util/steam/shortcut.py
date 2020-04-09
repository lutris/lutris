"""Export lutris games to steam shortcuts"""
import os
import shutil
from pathlib import Path

import lutris.util.resources as rs
import lutris.vendor.vdf as vdf
from lutris import pga
from lutris.util.log import logger

steam_tag = "Lutris"

def update_shortcuts(steamUserId):
    shortcut_path = os.path.join(Path.home(), f'.local/share/Steam/userdata/{steamUserId}/config/shortcuts.vdf')
    # Get shortcuts for non-steam lutris games
    lutris_shortcuts = generate_shortcuts()

    # Read existing shortcuts, that have no lutris tag
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    other_shortcuts = [
        s for s in shortcuts
        if steam_tag not in s['tags'].values()
    ]    

    # Merge them
    new_shortcuts = {
        'shortcuts': list_todict(other_shortcuts + lutris_shortcuts)
    }

    # Write shortcuts back to file
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(new_shortcuts))


def list_todict(l):
    return {str(i): l[i] for i in range(0, len(l))}

def generate_shortcuts(games = pga.get_games(filter_installed=True)):
    non_steam_games = [g for g in games if g['runner'] != 'steam']
    return list(map(generate_shortcut, non_steam_games))

def generate_shortcut(game):
    name = game['name']
    slug = game['slug']
    gameId = game['id']
    icon = rs.get_icon_path(slug)
    banner = rs.get_banner_path(slug)
    lutris_binary = shutil.which("lutris")
    start_dir = os.path.dirname(lutris_binary)

    shortcut_dict = {
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
        'tags': { # has been replaced by "collections" in steam. Tags are not visible in the UI anymore.
            '0': steam_tag   # to identify generated shortcuts
        }
    }
    return shortcut_dict

# update_shortcuts()
