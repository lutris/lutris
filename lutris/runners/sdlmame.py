import os
import subprocess
from lutris.runners.runner import Runner


class sdlmame(Runner):
    """Runs arcade games with SDLMame"""
    executable = "mame"
    package = "sdlmame"
    is_installable = True
    platform = "Arcade"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "Rom file"
        }
    ]

    runner_options = [
        {
            "option": "windowed",
            "type": "bool",
            "label": "Windowed"
        }
    ]

    def play(self):
        options = []
        rompath = os.path.dirname(self.settings["game"]["main_file"])
        rom = os.path.basename(self.settings["game"]["main_file"])
        mameconfigdir = os.path.join(os.path.expanduser("~"), ".mame")
        if self.runner_config.get("windowed", False):
            options.append("-window")
        if not os.path.exists(os.path.join(mameconfigdir, "mame.ini")):
            try:
                os.makedirs(mameconfigdir)
            except OSError:
                pass
            os.chdir(mameconfigdir)
            subprocess.Popen([self.executable, "-createconfig"],
                             stdout=subprocess.PIPE)
            os.chdir(rompath)
        return {'command': [self.executable,
                            "-inipath", mameconfigdir,
                            "-skip_gameinfo",
                            "-rompath", "\"%s\"" % rompath,
                            "\"%s\"" % rom] + options}
