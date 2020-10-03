# Standard Library
import os
import shlex
from gettext import gettext as _

# Lutris Modules
from lutris.runners.commands.dosbox import dosexec, makeconfig  # NOQA pylint: disable=unused-import
from lutris.runners.runner import Runner
from lutris.util import system


class dosbox(Runner):
    human_name = _("DOSBox")
    description = _("MS-Dos emulator")
    platforms = [_("MS-DOS")]
    runnable_alone = True
    runner_executable = "dosbox/bin/dosbox"
    require_libs = ["libopusfile.so.0", ]
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Main file"),
            "help": _(
                "The CONF, EXE, COM or BAT file to launch.\n"
                "It can be left blank if the launch of the executable is "
                "managed in the config file."
            ),
        },
        {
            "option": "config_file",
            "type": "file",
            "label": _("Configuration file"),
            "help": _(
                "Start Dosbox with the options specified in this file. \n"
                "It can have a section in which you can put commands "
                "to execute on startup. Read Dosbox's documentation "
                "for more information."
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Command arguments"),
            "help": _("Command line arguments used when launching DOSBox"),
            "validator": shlex.split,
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": _("Working directory"),
            "help": _(
                "The location where the game is run from.\n"
                "By default, Lutris uses the directory of the "
                "executable."
            ),
        },
    ]

    scaler_modes = [
        (_("none"), "none"),
        ("normal2x", "normal2x"),
        ("normal3x", "normal3x"),
        ("hq2x", "hq2x"),
        ("hq3x", "hq3x"),
        ("advmame2x", "advmame2x"),
        ("advmame3x", "advmame3x"),
        ("2xsai", "2xsai"),
        ("super2xsai", "super2xsai"),
        ("supereagle", "supereagle"),
        ("advinterp2x", "advinterp2x"),
        ("advinterp3x", "advinterp3x"),
        ("tv2x", "tv2x"),
        ("tv3x", "tv3x"),
        ("rgb2x", "rgb2x"),
        ("rgb3x", "rgb3x"),
        ("scan2x", "scan2x"),
        ("scan3x", "scan3x"),
    ]
    runner_options = [
        {
            "option":
            "scaler",
            "label":
            _("Graphic scaler"),
            "type":
            "choice",
            "choices":
            scaler_modes,
            "default":
            "normal3x",
            "help":
            _("The algorithm used to scale up the game's base "
              "resolution, resulting in different visual styles. "),
        },
        {
            "option": "exit",
            "label": _("Exit Dosbox with the game"),
            "type": "bool",
            "default": True,
            "help": _("Shut down Dosbox when the game is quit."),
        },
        {
            "option": "fullscreen",
            "label": _("Open game in fullscreen"),
            "type": "bool",
            "default": False,
            "help": _("Tells Dosbox to launch the game in fullscreen."),
        },
    ]

    def make_absolute(self, path):
        """Return a guaranteed absolute path"""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        if self.game_data.get("directory"):
            return os.path.join(self.game_data.get("directory"), path)
        return ""

    @property
    def main_file(self):
        return self.make_absolute(self.game_config.get("main_file"))

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return os.path.expanduser(option)
        if self.main_file:
            return os.path.dirname(self.main_file)
        return super(dosbox, self).working_dir

    def play(self):
        main_file = self.main_file
        if not system.path_exists(main_file):
            return {"error": "FILE_NOT_FOUND", "file": main_file}
        args = shlex.split(self.game_config.get("args") or "")

        command = [self.get_executable()]

        if main_file.endswith(".conf"):
            command.append("-conf")
            command.append(main_file)
        else:
            command.append(main_file)
        # Options
        if self.game_config.get("config_file"):
            command.append("-conf")
            command.append(self.make_absolute(self.game_config["config_file"]))

        scaler = self.runner_config.get("scaler")
        if scaler and scaler != "none":
            command.append("-scaler")
            command.append(self.runner_config["scaler"])

        if self.runner_config.get("fullscreen"):
            command.append("-fullscreen")

        if self.runner_config.get("exit"):
            command.append("-exit")

        if args:
            command.extend(args)

        return {"command": command}
