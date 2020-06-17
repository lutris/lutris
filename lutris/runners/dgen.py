# Standard Library
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class dgen(Runner):
    human_name = _("DGen")
    description = _("Sega Genesis emulator")
    platforms = [_("Sega Genesis")]
    runner_executable = "dgen/bin/dgen"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "help": _("The game data, commonly called a ROM image."),
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "pal",
            "type": "bool",
            "label": _("PAL"),
            "default": False,
            "advanced": True,
        },
        {
            "option": "region",
            "type": "choice",
            "label": _("Region"),
            "choices": [
                (_("America (NTSC)"), "U"),
                (_("Japan (NTSC)"), "J"),
                (_("Japan (PAL)"), "X"),
                (_("Europe (PAL)"), "E"),
            ],
            "default": "off",
            "advanced": True,
        },
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        if self.runner_config.get("fullscreen", True):
            arguments.append("-f")
        if self.runner_config.get("pal", True):
            arguments.append("-P")
        if self.runner_config.get("region") != "off":
            arguments.append("-R" + self.runner_config.get("region"))
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        arguments.append(rom)
        return {"command": arguments}
