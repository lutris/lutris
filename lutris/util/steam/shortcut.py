"""Export lutris games to steam shortcuts"""
import os
import shutil

from lutris.util import resources
from lutris.util.steam import vdf

steam_tag = "Lutris"


def update_shortcuts(steamUserId):
    shortcut_path = os.path.expanduser(f'~/.local/share/Steam/userdata/{steamUserId}/config/shortcuts.vdf')

    lutris_shortcuts = []

    # Read existing shortcuts, that have no lutris tag
    with open(shortcut_path, "rb") as shortcut_file:
        shortcuts = vdf.binary_loads(shortcut_file.read())['shortcuts'].values()
    other_shortcuts = [
        s for s in shortcuts
        if steam_tag not in s['tags'].values()
    ]

    new_shortcuts = {
        'shortcuts': {
            str(index): elem for index, elem in enumerate(other_shortcuts + lutris_shortcuts)
        }
    }

    # Write shortcuts back to file
    with open(shortcut_path, "wb") as shortcut_file:
        shortcut_file.write(vdf.binary_dumps(new_shortcuts))


def generate_shortcut(game):
    name = game['name']
    slug = game['slug']
    gameId = game['id']
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
