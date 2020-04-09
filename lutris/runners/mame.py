import os
import subprocess
from lutris.runners.runner import Runner
from lutris.util import system


class mame(Runner):
    human_name = "MAME"
    description = "Arcade game emulator"
    platforms = ["Arcade"]
    runner_executable = "mame/mame"
    runnable_alone = True
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {"option": "fullscreen", "type": "bool", "label": "Fullscreen", "default": True},
        {
            "option": "waitvsync",
            "type": "bool",
            "label": "Wait for VSync",
            "help": (
                "Enable waiting for  the  start  of  VBLANK  before "
                "flipping  screens; reduces tearing effects."
            ),
            "default": False
        }
    ]

    @property
    def config_dir(self):
        return os.path.join(os.path.expanduser("~"), ".mame")

    @property
    def working_dir(self):
        return self.config_dir

    def prelaunch(self):
        if not system.path_exists(os.path.join(self.config_dir, "mame.ini")):
            try:
                os.makedirs(self.config_dir)
            except OSError:
                pass
            subprocess.Popen(
                [self.get_executable(), "-createconfig"], stdout=subprocess.PIPE
            )
        return True

    def play(self):
        options = []
        rompath = os.path.dirname(self.game_config.get("main_file"))
        rom = os.path.basename(self.game_config.get("main_file"))
        if not self.runner_config.get("fullscreen"):
            options.append("-window")

        if self.runner_config.get("waitvsync"):
            options.append("-waitvsync")

        return {
            "command": [
                self.get_executable(),
                "-inipath",
                self.config_dir,
                "-video",
                "opengl",
                "-skip_gameinfo",
                "-rompath",
                rompath,
                rom,
            ]
            + options
        }
