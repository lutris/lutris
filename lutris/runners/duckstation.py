"""DuckStation Runner"""

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
    download_url = "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
            "default_path": "game_path",
        }
    ]

    # Duckstation uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        arguments = self.get_command()

        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)
        arguments.append(rom)
        logger.debug("DuckStation starting with args: %s", arguments)
        return {"command": arguments}
