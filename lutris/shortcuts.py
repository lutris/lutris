"""Desktop file creator."""
import os
import stat
import shutil
import subprocess

from textwrap import dedent
from xdg import BaseDirectory
from gi.repository import GLib

from lutris.util import system
from lutris.util.log import logger
from lutris.settings import CACHE_DIR


def get_xdg_basename(game_slug, game_id, legacy=False):
    if legacy:
        filename = "{}.desktop".format(game_slug)
    else:
        filename = "{}-{}.desktop".format(game_slug, game_id)
    return filename


def create_launcher(game_slug, game_id, game_name, desktop=False, menu=False):
    """Create a .desktop file."""
    desktop_dir = (
        GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    )
    launcher_content = dedent(
        """
        [Desktop Entry]
        Type=Application
        Name=%s
        Icon=%s
        Exec=lutris lutris:%s
        Categories=Game
        """.format(game_name, 'lutris_{}'.format(game_slug), game_id)
    )

    launcher_filename = get_xdg_basename(game_slug, game_id, legacy=False)
    tmp_launcher_path = os.path.join(CACHE_DIR, launcher_filename)
    tmp_launcher = open(tmp_launcher_path,  "w")
    tmp_launcher.write(launcher_content)
    tmp_launcher.close()
    os.chmod(tmp_launcher_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC |
             stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP)

    if desktop:
        shutil.copy(tmp_launcher_path,
                    os.path.join(desktop_dir, launcher_filename))
    if menu:
        menu_path = os.path.join(GLib.get_user_data_dir(), 'applications')
        shutil.copy(tmp_launcher_path,
                    os.path.join(menu_path, launcher_filename))
    os.remove(tmp_launcher_path)


def get_launcher_path(game_slug, game_id):
    """Return the path of a XDG game launcher.
    When legacy is set, it will return the old path with only the slug,
    otherwise it will return the path with slug + id
    """
    xdg_executable = 'xdg-user-dir'
    if not system.find_executable(xdg_executable):
        logger.error("%s not found", xdg_executable)
        return
    desktop_dir = subprocess.Popen([xdg_executable, 'DESKTOP'],
                                   stdout=subprocess.PIPE).communicate()[0]
    desktop_dir = str(desktop_dir).strip()

    legacy_launcher_path = os.path.join(
        desktop_dir, get_xdg_basename(game_slug, game_id, legacy=True)
    )
    # First check if legacy path exists, for backward compatibility
    if system.path_exists(legacy_launcher_path):
        return legacy_launcher_path
    # Otherwise return new path, whether it exists or not
    return os.path.join(
        desktop_dir, get_xdg_basename(game_slug, game_id, legacy=False)
    )


def get_menu_launcher_path(game_slug, game_id):
    """Return the path to a XDG menu launcher, prioritizing legacy paths if
    they exist
    """
    menu_dir = os.path.join(BaseDirectory.xdg_data_home, 'applications')
    menu_path = os.path.join(
        menu_dir, get_xdg_basename(game_slug, game_id, legacy=True)
    )
    if system.path_exists(menu_path):
        return menu_path
    return os.path.join(
        menu_dir, get_xdg_basename(game_slug, game_id, legacy=False)
    )


def desktop_launcher_exists(game_slug, game_id):
    return system.path_exists(get_launcher_path(game_slug, game_id))


def menu_launcher_exists(game_slug, game_id):
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
