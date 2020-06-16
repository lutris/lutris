# Standard Library
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class virtualjaguar(Runner):
    description = _("Atari Jaguar emulator")
    human_name = _("Virtual Jaguar")
    platforms = [_("Atari Jaguar")]
    runnable_alone = True
    runner_executable = "virtualjaguar/virtualjaguar"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "default_path": "game_path",
            "label": _("ROM file"),
            "help": _("The game data, commonly called a ROM image.\n"
                      "Supported formats: J64 and JAG."),
        }
    ]

    runner_options = [{"option": "fullscreen", "type": "bool", "label": _("Fullscreen"), "default": "1"}]

    def play(self):
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        return {"command": [self.get_executable(), rom]}
