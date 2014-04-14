import os
import subprocess

from lutris.runners.runner import Runner


# pylint: disable=C0103
class sdlmame(Runner):
    """Runs arcade games with SDLMame"""

    executable = "mame"
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
        """ Launch the game. """
        settings = self.settings
        fullscreen = True
        rompath = os.path.dirname(settings["game"]["main_file"])
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
            os.chdir(rompath)
        options = []
        if not fullscreen:
            options.append("-window")
        return {'command': [self.executable,
                            "-inipath", mameconfigdir,
                            "-skip_gameinfo",
                            "-rompath", "\"%s\"" % rompath,
                            "\"%s\"" % rom] + options}
