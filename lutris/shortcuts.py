import sys,os, shutil
from subprocess import Popen, PIPE
from xdg import BaseDirectory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lutris.config import LutrisConfig
from lutris.constants import ICON_PATH, TMP_PATH


def create_launcher(game, desktop=False, menu=False):
    config = LutrisConfig(game=game)

    desktop_dir = Popen(['xdg-user-dir', 'DESKTOP'], stdout=PIPE).communicate()[0]
    desktop_dir = desktop_dir.strip()

    launcher_content = """#!/usr/bin/env xdg-open
[Desktop Entry]
Type=Application
Name=%s
Icon=%s
Exec=lutris lutris:%s
Categories=Game""" % (
        config.get_real_name(),
        os.path.join(ICON_PATH, game + '.png'),
        game
    )
        
    launcher_filename = "%s.desktop" % game
    tmp_launcher_path = os.path.join(TMP_PATH, launcher_filename )
    tmp_launcher = open(tmp_launcher_path,  "w")
    tmp_launcher.write(launcher_content)
    tmp_launcher.close()
    
    if desktop:
        shutil.copy(tmp_launcher_path, os.path.join(desktop_dir, launcher_filename))
    if menu:
        menu_path = os.path.join(BaseDirectory.xdg_data_home, 'applications')
        shutil.copy (tmp_launcher_path, os.path.join(menu_path, launcher_filename))
    os.remove(tmp_launcher_path)
    
if __name__ == "__main__":
    create_launcher("quake", desktop=True, menu=True
                    )

