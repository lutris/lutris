""" desktop file creator """
import os
import stat
import shutil
import subprocess

from textwrap import dedent
from xdg import BaseDirectory
from gi.repository import GLib

from lutris.settings import CACHE_DIR


def create_launcher(game_slug, game_name, desktop=False, menu=False):
    """Create .desktop file."""
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
        """ % (game_name, 'lutris_' + game_slug, game_slug))

    launcher_filename = "%s.desktop" % game_slug
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


def desktop_launcher_exists(game_slug):
    filename = "%s.desktop" % game_slug

    desktop_dir = subprocess.Popen(['xdg-user-dir', 'DESKTOP'],
                                   stdout=subprocess.PIPE).communicate()[0]
    desktop_dir = desktop_dir.strip()
    file_path = os.path.join(desktop_dir, filename)
    if os.path.exists(file_path):
        return True
    return False


def menu_launcher_exists(game_slug):
    filename = "%s.desktop" % game_slug
    menu_path = os.path.join(BaseDirectory.xdg_data_home, 'applications')
    file_path = os.path.join(menu_path, filename)
    if os.path.exists(file_path):
        return True
    return False


def remove_launcher(game_slug, desktop=False, menu=False):
    """Remove existing .desktop file."""
    filename = "%s.desktop" % game_slug

    if desktop:
        desktop_dir = subprocess.Popen(['xdg-user-dir', 'DESKTOP'],
                                       stdout=subprocess.PIPE).communicate()[0]
        desktop_dir = desktop_dir.strip()
        file_path = os.path.join(desktop_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    if menu:
        menu_path = os.path.join(BaseDirectory.xdg_data_home, 'applications')
        file_path = os.path.join(menu_path, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
