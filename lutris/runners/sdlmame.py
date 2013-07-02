import os
import subprocess

from lutris.runners.runner import Runner


# pylint: disable=C0103
class sdlmame(Runner):
    """Runs arcade games with SDLMame"""
    def __init__(self, settings=None):
        """ Mame initialization """
        super(sdlmame, self).__init__()
        self.executable = "mame"
        self.platform = "Arcade"
        self.game_options = [
            {
                "option": "main_file",
                "type": "file_chooser",
                "label": "Rom file"
            }
        ]
        self.runner_options = [
            {
                "option": "windowed",
                "type": "bool",
                "label": "Windowed"
            }
        ]
        self.settings = settings

    def play(self):
        """ Launch the game. """
        settings = self.settings
        fullscreen = True
        romdir = os.path.dirname(settings["game"]["main_file"])
        rom = os.path.basename(settings["game"]["main_file"])
        mameconfigdir = os.path.join(os.path.expanduser("~"), ".mame")
        if "sdlmame" in settings.config:
            if "windowed" in settings["sdlmame"]:
                fullscreen = not settings["sdlmame"]["windowed"]
        if not os.path.exists(os.path.join(mameconfigdir, "mame.ini")):
            try:
                os.makedirs(mameconfigdir)
            except OSError:
                pass
            os.chdir(mameconfigdir)
            subprocess.Popen([self.executable, "-createconfig"],
                             stdout=subprocess.PIPE)
            os.chdir(romdir)
        arguments = []
        if not fullscreen:
            arguments = arguments + ["-window"]
        return {'command': [self.executable,
                            "-inipath", mameconfigdir,
                            "-skip_gameinfo",
                            "-rompath", romdir, rom] + arguments}
