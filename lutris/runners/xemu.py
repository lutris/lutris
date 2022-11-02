from gettext import gettext as _

from lutris.runners.runner import Runner
from lutris.util import system


class xemu(Runner):
    human_name = _("xemu")
    platforms = [_("Xbox")]
    description = _("Xbox emulator")
    runnable_alone = True
    runner_executable = "xemu/xemu"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("ISO file"),
            "help": _("DVD image in iso format"),
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "label": _("Fullscreen"),
            "type": "bool",
            "default": True,
        },
    ]

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]

        fullscreen = self.runner_config.get("fullscreen")
        if fullscreen:
            arguments.append("-full-screen")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        arguments += ["-dvd_path", iso]
        return {"command": arguments}
