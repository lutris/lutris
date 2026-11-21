"""DuckStation Runner"""

from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger
from lutris.util.upstream import ReleaseSource


class duckstation(Runner):
    human_name = _("DuckStation")
    description = _("PlayStation 1 Emulator")
    platform_dict = Runner.to_platform_dict([_("Sony PlayStation")])
    runnable_alone = True
    runner_executable = "duckstation/DuckStation-x64.AppImage"
    system_executable = "duckstation-qt"
    upstream = ReleaseSource("stenzek/duckstation", r"^DuckStation-x64\.AppImage$")
    upstream_arch = "x86_64"

    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ROM file"),
        }
    ]

    def play(self):
        arguments = self.get_command()

        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)
        arguments.append(rom)
        logger.debug("DuckStation starting with args: %s", arguments)
        return {"command": arguments}
