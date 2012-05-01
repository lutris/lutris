""" xdg desktop file creator """
import os
import stat
import shutil

from xdg import BaseDirectory
from subprocess import Popen, PIPE

from lutris.config import LutrisConfig
from lutris.settings  import CACHE_DIR, DATA_DIR


def create_launcher(game, desktop=False, menu=False):
    """ Create desktop file """
    config = LutrisConfig(game=game)
    desktop_dir = Popen(['xdg-user-dir', 'DESKTOP'],
                        stdout=PIPE).communicate()[0]
    desktop_dir = desktop_dir.strip()
    launcher_content = """[Desktop Entry]
Type=Application
Name=%s
GenericName=%s
Icon=%s
Exec=lutris lutris:%s
Categories=Game
""" % (config.get_real_name(),
       config.get_real_name(),
       os.path.join(DATA_DIR, "icons/%s.png" % game),
       game)

    launcher_filename = "%s.desktop" % game
    tmp_launcher_path = os.path.join(CACHE_DIR, launcher_filename)
    tmp_launcher = open(tmp_launcher_path,  "w")
    tmp_launcher.write(launcher_content)
    tmp_launcher.close()
    os.chmod(tmp_launcher_path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC | \
             stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP)

    if desktop:
        shutil.copy(tmp_launcher_path,
                    os.path.join(desktop_dir, launcher_filename))
    if menu:
        menu_path = os.path.join(BaseDirectory.xdg_data_home, 'applications')
        shutil.copy(tmp_launcher_path,
                    os.path.join(menu_path, launcher_filename))
    os.remove(tmp_launcher_path)
