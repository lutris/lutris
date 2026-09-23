"""Xenia Runner"""

from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger


class xenia(Runner):
    human_name = _("Xenia")
    description = _("Xbox 360 Emulator")
    platform_dict = Runner.to_platform_dict([_("Microsoft Xbox 360")])
    runnable_alone = True
    runner_executable = "xenia/xenia_canary_linux.AppImage"
    download_url = "https://github.com/xenia-canary/xenia-canary/releases/latest/download/xenia_canary_linux.AppImage"
    entry_point_option = "main_file"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Game file"),
            "help": _("Path to .xex or .iso file"),
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
    ]

    # Xenia uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        """Launch an Xbox 360 game through Xenia."""
        arguments = self.get_command()

        if self.runner_config.get("fullscreen"):
            arguments.append("--fullscreen")

        game_path = self.game_config.get("main_file") or ""
        if not system.path_exists(game_path):
            raise MissingGameExecutableError(filename=game_path)
        arguments.append(game_path)

        logger.debug("Xenia starting with args: %s", arguments)
        return {"command": arguments}
