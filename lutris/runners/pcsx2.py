# Standard Library
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.upstream import ReleaseSource


class pcsx2(Runner):
    human_name = _("PCSX2")
    description = _("PlayStation 2 emulator")
    platform_dict = Runner.to_platform_dict([_("Sony PlayStation 2")])
    runnable_alone = True
    runner_executable = "pcsx2/PCSX2.AppImage"
    system_executable = "pcsx2-qt"
    upstream = ReleaseSource("PCSX2/pcsx2", r"^pcsx2-.*-linux-appimage-x64-Qt\.AppImage$")
    upstream_arch = "x86_64"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
        }
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": False,
        },
        {"option": "full_boot", "type": "bool", "label": _("Fullboot"), "default": False},
        {"option": "nogui", "type": "bool", "label": _("No GUI"), "default": False},
    ]

    def play(self):
        arguments = self.get_command()

        if self.runner_config.get("fullscreen"):
            arguments.append("-fullscreen")
        if self.runner_config.get("full_boot"):
            arguments.append("-slowboot")
        if self.runner_config.get("nogui"):
            arguments.append("-nogui")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            raise MissingGameExecutableError(filename=iso)
        arguments.append(iso)
        return {"command": arguments}
