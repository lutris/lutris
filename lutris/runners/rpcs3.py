# Standard Library
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.upstream import ReleaseSource


class rpcs3(Runner):
    human_name = _("RPCS3")
    description = _("PlayStation 3 emulator")
    platform_dict = Runner.to_platform_dict([_("Sony PlayStation 3")])
    runnable_alone = True
    runner_executable = "rpcs3/rpcs3.AppImage"
    system_executable = "rpcs3"
    upstream = ReleaseSource("RPCS3/rpcs3-binaries-linux", r"^rpcs3-.*_linux64\.AppImage$")
    upstream_arch = "x86_64"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Path to EBOOT.BIN"),
        }
    ]
    runner_options = [{"option": "nogui", "type": "bool", "label": _("No GUI"), "default": False}]

    def play(self):
        arguments = self.get_command()

        if self.runner_config.get("nogui"):
            arguments.append("--no-gui")

        eboot = self.game_config.get("main_file") or ""
        if not system.path_exists(eboot):
            raise MissingGameExecutableError(filename=eboot)
        arguments.append(eboot)
        return {"command": arguments}
