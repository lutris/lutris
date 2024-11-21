"""DuckStation Runner"""

import os.path
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger


class duckstation(Runner):
    human_name = _("DuckStation")
    description = _("PlayStation 1 Emulator")
    platforms = [_("Sony PlayStation")]
    runnable_alone = True
    runner_executable = "duckstation/DuckStation-x64.AppImage"
    flatpak_id = "org.duckstation.DuckStation"
    config_dir = os.path.expanduser("~/.local/share/duckstation/")
    config_file = os.path.join(config_dir, "settings.ini")
    download_url = "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "section": _("Graphics"),
            "help": _("Enters fullscreen mode immediately after starting."),
            "default": True,
        },
        {
            "option": "nofullscreen",
            "type": "bool",
            "label": _("No Fullscreen"),
            "section": _("Graphics"),
            "help": _("Prevents fullscreen mode from triggering if enabled."),
            "default": False,
        },
        {
            "option": "nogui",
            "type": "bool",
            "label": _("Batch Mode"),
            "section": _("Boot"),
            "help": _("Enables batch mode (exits after powering off)."),
            "default": True,
            "advanced": True,
        },
        {
            "option": "fastboot",
            "type": "bool",
            "label": _("Force Fastboot"),
            "section": _("Boot"),
            "help": _("Force fast boot."),
            "default": False,
        },
        {
            "option": "slowboot",
            "type": "bool",
            "label": _("Force Slowboot"),
            "section": _("Boot"),
            "help": _("Force slow boot."),
            "default": False,
        },
        {
            "option": "nocontroller",
            "type": "bool",
            "label": _("No Controllers"),
            "section": _("Controllers"),
            "help": _(
                "Prevents the emulator from polling for controllers. Try this option if you're "
                "having difficulties starting the emulator."
            ),
            "default": False,
        },
        {
            "option": "settings",
            "type": "file",
            "label": _("Custom configuration file"),
            "help": _(
                "Loads a custom settings configuration from the specified filename. "
                "Default settings applied if file not found."
            ),
            "default": config_file,
            "advanced": True,
        },
    ]

    # Duckstation uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        arguments = self.get_command()
        runner_flags = {
            "nogui": "-batch",
            "fastboot": "-fastboot",
            "slowboot": "-slowboot",
            "fullscreen": "-fullscreen",
            "nofullscreen": "-nofullscreen",
            "nocontroller": "-nocontroller",
        }
        for option, flag in runner_flags.items():
            if self.runner_config.get(option):
                arguments.append(flag)
        arguments += ["-settings", self.config_file, "--"]

        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)
        arguments.append(rom)
        logger.debug("DuckStation starting with args: %s", arguments)
        return {"command": arguments}
