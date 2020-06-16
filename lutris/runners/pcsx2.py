# Standard Library
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class pcsx2(Runner):
    human_name = _("PCSX2")
    description = _("PlayStation 2 emulator")
    platforms = [_("Sony PlayStation 2")]
    runnable_alone = True
    runner_executable = "pcsx2/PCSX2"
    game_options = [{
        "option": "main_file",
        "type": "file",
        "label": _("ISO file"),
        "default_path": "game_path",
    }]

    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": False,
        },
        {
            "option": "full_boot",
            "type": "bool",
            "label": _("Fullboot"),
            "default": False
        },
        {
            "option": "nogui",
            "type": "bool",
            "label": _("No GUI"),
            "default": False
        },
        {
            "option": "config_file",
            "type": "file",
            "label": _("Custom config file"),
            "advanced": True,
        },
        {
            "option": "config_path",
            "type": "directory_chooser",
            "label": _("Custom config path"),
            "advanced": True,
        },
    ]

    def play(self):
        arguments = [self.get_executable()]

        if self.runner_config.get("fullscreen"):
            arguments.append("--fullscreen")
        if self.runner_config.get("full_boot"):
            arguments.append("--fullboot")
        if self.runner_config.get("nogui"):
            arguments.append("--nogui")
        if self.runner_config.get("config_file"):
            arguments.append("--cfg=%s", self.runner_config["config_file"])
        if self.runner_config.get("config_path"):
            arguments.append("--cfgpath=%s", self.runner_config["config_path"])

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        arguments.append(iso)
        return {"command": arguments}
