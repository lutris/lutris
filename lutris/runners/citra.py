# Standard Library
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class citra(Runner):
    human_name = _("Citra")
    description = _("Nintendo 3DS emulator")
    platforms = [_("Nintendo 3DS")]
    runnable_alone = True
    runner_executable = "citra/citra"
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


    # CITRA currently uses an AppImage, no need for the runtime.
    system_options_override = [{"option": "disable_runtime", "default": True}]

    def play(self):
        arguments = [self.get_executable()]

        if self.runner_config.get("fullscreen"):
            arguments.append("--fullscreen")
        if self.runner_config.get("full_boot"):
            arguments.append("--fullboot")
        if self.runner_config.get("nogui"):
            arguments.append("--nogui")
        if self.runner_config.get("config_file"):
            arguments.append("--cfg={}".format(self.runner_config["config_file"]))
        if self.runner_config.get("config_path"):
            arguments.append("--cfgpath={}".format(self.runner_config["config_path"]))

        iso = self.game_config.get("main_file") or ""
        if not system.path_exists(iso):
            return {"error": "FILE_NOT_FOUND", "file": iso}
        arguments.append(iso)
        return {"command": arguments}
