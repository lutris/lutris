# Standard Library
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class ppsspp(Runner):
    human_name = _("PPSSPP")
    description = _("Sony PSP emulator")
    platforms = [_("Sony PlayStation Portable")]
    runner_executable = "ppsspp/PPSSPPSDL"
    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": _("ISO file"),
        "default_path": "game_path",
    }]

    runner_options = [{
        "option": "fullscreen",
        "type": "bool",
        "label": _("Fullscreen"),
        "default": False,
    }]

    def play(self):
        arguments = [self.get_executable()]

        if self.runner_config.get("fullscreen"):
            arguments.append("--fullscreen")

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        arguments.append(iso)
        return {"command": arguments}
