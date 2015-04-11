import os
import subprocess
from lutris import settings
from lutris.runners.runner import Runner


class mame(Runner):
    """Arcade game emulator"""
    human_name = "MAME"
    platform = "Arcade"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": "Fullscreen",
            'default': True,
        }
    ]

    tarballs = {
        "x64": "mame-0.154-x86_64.tar.gz",
    }

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, "mame/mame")

    def play(self):
        options = []
        rompath = os.path.dirname(self.game_config.get('main_file'))
        rom = os.path.basename(self.game_config.get('main_file'))
        mameconfigdir = os.path.join(os.path.expanduser("~"), ".mame")
        if not self.runner_config.get('fullscreen'):
            options.append("-window")
        if not os.path.exists(os.path.join(mameconfigdir, "mame.ini")):
            try:
                os.makedirs(mameconfigdir)
            except OSError:
                pass
            os.chdir(mameconfigdir)
            subprocess.Popen([self.get_executable(), "-createconfig"],
                             stdout=subprocess.PIPE)
            os.chdir(rompath)
        return {'command': [self.get_executable(),
                            "-inipath", mameconfigdir,
                            "-skip_gameinfo",
                            "-rompath", rompath,
                            rom] + options}
