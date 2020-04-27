"""XDG shortcuts handling"""
# Standard Library
import os
import shutil
import stat
from textwrap import dedent

# Third Party Libraries
from gi.repository import GLib

# Lutris Modules
from lutris.settings import CACHE_DIR
from lutris.util import system


def get_xdg_entry(directory):
    """Return the path for specific user folders"""
    special_dir = {
        "DESKTOP": GLib.UserDirectory.DIRECTORY_DESKTOP,
        "MUSIC": GLib.UserDirectory.DIRECTORY_MUSIC,
        "PICTURES": GLib.UserDirectory.DIRECTORY_PICTURES,
        "VIDEOS": GLib.UserDirectory.DIRECTORY_VIDEOS,
        "DOCUMENTS": GLib.UserDirectory.DIRECTORY_DOCUMENTS,
    }
    directory = directory.upper()
    if directory not in special_dir.keys():
        raise ValueError(
            directory + " not supported. Only those folders are supported: " + ", ".join(special_dir.keys())
        )
    return GLib.get_user_special_dir(special_dir[directory])


def get_xdg_basename(game_slug, game_id, base_dir=None):
    """Return the filename for .desktop shortcuts"""
    if base_dir:
        # When base dir is provided, lookup possible combinations
        # and return the first match
        for path in [
            "{}.desktop".format(game_slug),
            "{}-{}.desktop".format(game_slug, game_id),
            "net.lutris.{}-{}.desktop".format(game_slug, game_id),
        ]:
            if system.path_exists(os.path.join(base_dir, path)):
                return path

    return "net.lutris.{}-{}.desktop".format(game_slug, game_id)


def create_launcher(game_slug, game_id, game_name, desktop=False, menu=False):
    """Create a .desktop file."""
    desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    launcher_content = dedent(
        """
        [Desktop Entry]
        Type=Application
        Name={}
        Icon={}
        Exec=lutris lutris:rungameid/{}
        Categories=Game
        """.format(game_name, "lutris_{}".format(game_slug), game_id)
    )

    launcher_filename = get_xdg_basename(game_slug, game_id)
    tmp_launcher_path = os.path.join(CACHE_DIR, launcher_filename)
    tmp_launcher = open(tmp_launcher_path, "w")
    tmp_launcher.write(launcher_content)
    tmp_launcher.close()
    os.chmod(
        tmp_launcher_path,
        stat.S_IREAD
        | stat.S_IWRITE
        | stat.S_IEXEC
        | stat.S_IRGRP
        | stat.S_IWGRP
        | stat.S_IXGRP,
    )

    if desktop:
        if not os.path.exists(desktop_dir):
            os.mkdir(desktop_dir)
        shutil.copy(tmp_launcher_path, os.path.join(desktop_dir, launcher_filename))
    if menu:
        menu_path = os.path.join(GLib.get_user_data_dir(), "applications")
        if not os.path.exists(menu_path):
            os.mkdir(menu_path)
        shutil.copy(tmp_launcher_path, os.path.join(menu_path, launcher_filename))
    os.remove(tmp_launcher_path)


def get_launcher_path(game_slug, game_id):
    """Return the path of a XDG game launcher.
    When legacy is set, it will return the old path with only the slug,
    otherwise it will return the path with slug + id
    """
    desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)

    return os.path.join(desktop_dir, get_xdg_basename(game_slug, game_id, base_dir=desktop_dir))


def get_menu_launcher_path(game_slug, game_id):
    """Return the path to a XDG menu launcher, prioritizing legacy paths if
    they exist
    """
    menu_dir = os.path.join(GLib.get_user_data_dir(), "applications")
    return os.path.join(menu_dir, get_xdg_basename(game_slug, game_id, base_dir=menu_dir))


def desktop_launcher_exists(game_slug, game_id):
    """Return True if there is an existing desktop icon for a game"""
    return system.path_exists(get_launcher_path(game_slug, game_id))


def menu_launcher_exists(game_slug, game_id):
    """Return True if there is an existing application menu entry for a game"""
    return system.path_exists(get_menu_launcher_path(game_slug, game_id))


def remove_launcher(game_slug, game_id, desktop=False, menu=False):
    """Remove existing .desktop file."""
    if desktop:
        launcher_path = get_launcher_path(game_slug, game_id)
        if system.path_exists(launcher_path):
            os.remove(launcher_path)

    if menu:
        menu_path = get_menu_launcher_path(game_slug, game_id)
        if system.path_exists(menu_path):
            os.remove(menu_path)
