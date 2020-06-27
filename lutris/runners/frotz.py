# It is pitch black. You are likely to be eaten by a grue.

from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class frotz(Runner):
    human_name = _("Frotz")
    description = _("Z-code emulator for text adventure games such as Zork.")
    platforms = [_("Z-Machine")]
    runner_executable = "frotz/frotz"
    entry_point_option = "story"

    game_options = [
        {
            "option":
            "story",
            "type":
            "file",
            "label":
            _("Story file"),
            "help": _(
                "The Z-Machine game file.\n"
                'Usally ends in ".z*", with "*" being a number from 1 '
                "to 6 representing the version of the Z-Machine that "
                "the game was written for."
            ),
        }
    ]
    system_options_override = [{"option": "terminal", "default": True}]

    def play(self):
        story = self.game_config.get("story") or ""
        if not self.is_installed():
            return {"error": "RUNNER_NOT_INSTALLED"}
        if not system.path_exists(story):
            return {"error": "FILE_NOT_FOUND", "file": story}
        command = [self.get_executable(), story]
        return {"command": command}
