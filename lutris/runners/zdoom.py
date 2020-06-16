# Standard Library
import os
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import display, system
from lutris.util.log import logger
from lutris.util.strings import split_arguments


class zdoom(Runner):
    # http://zdoom.org/wiki/Command_line_parameters
    description = _("ZDoom DOOM Game Engine")
    human_name = _("ZDoom")
    platforms = [_("Linux")]
    runner_executable = "zdoom/zdoom"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("WAD file"),
            "help": _("The game data, commonly called a WAD file."),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game."),
        },
        {
            "option": "files",
            "type": "multiple",
            "label": _("PWAD files"),
            "help": _("Used to load one or more PWAD files which generally contain "
                      "user-created levels."),
        },
        {
            "option": "warp",
            "type": "string",
            "label": _("Warp to map"),
            "help": _("Starts the game on the given map."),
        },
        {
            "option": "savedir",
            "type": "directory_chooser",
            "label": _("Save path"),
            "help": _("User-specified path where save files should be located."),
        },
    ]
    runner_options = [
        {
            "option": "2",
            "label": _("Pixel Doubling"),
            "type": "bool",
            "default": False
        },
        {
            "option": "4",
            "label": _("Pixel Quadrupling"),
            "type": "bool",
            "default": False
        },
        {
            "option": "nostartup",
            "label": _("Disable Startup Screens"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "skill",
            "label": _("Skill"),
            "type": "choice",
            "default": "",
            "choices": {
                (_("None"), ""),
                (_("I'm Too Young To Die (1)"), "1"),
                (_("Hey, Not Too Rough (2)"), "2"),
                (_("Hurt Me Plenty (3)"), "3"),
                (_("Ultra-Violence (4)"), "4"),
                (_("Nightmare! (5)"), "5"),
            },
        },
        {
            "option":
            "config",
            "label":
            _("Config file"),
            "type":
            "file",
            "help": _(
                "Used to load a user-created configuration file. If specified, "
                "the file must contain the wad directory list or launch will fail."
            ),
        },
    ]

    def get_executable(self):
        executable = super(zdoom, self).get_executable()
        executable_dir = os.path.dirname(executable)
        if not system.path_exists(executable_dir):
            return executable
        if not system.path_exists(executable):
            gzdoom_executable = os.path.join(executable_dir, "gzdoom")
            if system.path_exists(gzdoom_executable):
                return gzdoom_executable
        return executable

    def prelaunch(self):
        if not system.LINUX_SYSTEM.get_soundfonts():
            logger.warning("FluidSynth is not installed, you might not have any music")
        return True

    def play(self):  # noqa: C901
        command = [self.get_executable()]

        resolution = self.runner_config.get("resolution")
        if resolution:
            if resolution == "desktop":
                width, height = display.DISPLAY_MANAGER.get_current_resolution()
            else:
                width, height = resolution.split("x")
            command.append("-width")
            command.append(width)
            command.append("-height")
            command.append(height)

        # Append any boolean options.
        bool_options = ["2", "4", "nostartup"]
        for option in bool_options:
            if self.runner_config.get(option):
                command.append("-%s" % option)

        # Append the skill level.
        skill = self.runner_config.get("skill")
        if skill:
            command.append("-skill")
            command.append(skill)

        # Append directory for configuration file, if provided.
        config = self.runner_config.get("config")
        if config:
            command.append("-config")
            command.append(config)

        # Append the warp arguments.
        warp = self.game_config.get("warp")
        if warp:
            command.append("-warp")
            for warparg in warp.split(" "):
                command.append(warparg)

        # Append directory for save games, if provided.
        savedir = self.game_config.get("savedir")
        if savedir:
            command.append("-savedir")
            command.append(savedir)

        # Append the wad file to load, if provided.
        wad = self.game_config.get("main_file")
        if wad:
            command.append("-iwad")
            command.append(wad)

        # Append the pwad files to load, if provided.
        files = self.game_config.get("files") or []
        pwads = [f for f in files if f.lower().endswith(".wad") or f.lower().endswith(".pk3")]
        deh = [f for f in files if f.lower().endswith(".deh")]
        bex = [f for f in files if f.lower().endswith(".bex")]
        if deh:
            command.append("-deh")
            command.append(deh[0])
        if bex:
            command.append("-bex")
            command.append(bex[0])
        if pwads:
            command.append("-file")
            for pwad in pwads:
                command.append(pwad)

        # Append additional arguments, if provided.
        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)

        return {"command": command}
