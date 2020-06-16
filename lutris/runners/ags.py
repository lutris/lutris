
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class ags(Runner):
    human_name = _("Adventure Game Studio")
    description = _("Graphics adventure engine")
    platforms = [_("Linux")]
    runner_executable = "ags/ags.sh"
    game_options = [{"option": "main_file", "type": "file", "label": _("Game executable or directory")}]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "filter",
            "type": "choice",
            "label": _("Graphics filter"),
            "choices": [
                (_("None"), "none"),
                (_("Standard scaling"), "stdscale"),
                (_("HQ2x"), "hq2x"),
                (_("HQ3x"), "hq3x"),
            ],
        },
    ]

    def play(self):
        """Run the game."""

        main_file = self.game_config.get("main_file") or ""
        if not system.path_exists(main_file):
            return {"error": "FILE_NOT_FOUND", "file": main_file}

        arguments = [self.get_executable()]
        if self.runner_config.get("fullscreen", True):
            arguments.append("--fullscreen")
        else:
            arguments.append("--windowed")
        if self.runner_config.get("filter"):
            arguments.append("--gfxfilter")
            arguments.append(self.runner_config["filter"])

        arguments.append(main_file)
        return {"command": arguments}
