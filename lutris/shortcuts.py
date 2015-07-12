""" desktop file creator """
import os
import stat
import shutil
import subprocess

from gi.repository import GLib

from lutris.game import Game
from lutris.settings import CACHE_DIR


def create_launcher(game_slug, desktop=False, menu=False):
    """ Create desktop file """
    game = Game(game_slug)

    desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    launcher_content = """[Desktop Entry]
Type=Application
Name=%s
Icon=%s
Exec=lutris lutris:%s
Categories=Game
""" % (game.name, 'lutris_' + game_slug, game_slug)

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
