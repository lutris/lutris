"""ShadPS4 Runner"""

import os
from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system


class shadps4(Runner):
    human_name = _("ShadPS4")
    description = _("PlayStation 4 Emulator")
    platforms = [_("Sony PlayStation 4")]
    runnable_alone = True
    runner_executable = "shadps4/shadPS4QtLauncher-qt.AppImage"

    game_options = [
        {
            "option": "main_file",
            "type": "directory",
            "label": _("Game folder"),
            "help": _("Path to the game folder (e.g., CUSA00001)"),
            "default_path": "game_path",
        }
    ]

    runner_options = [
        {
            "option": "emulator",
            "type": "choice",
            "label": _("Emulator"),
            "choices": [
                (_("Bundled"), "bundled"),
                (_("Launcher default"), "default"),
                (_("Custom"), "custom"),
            ],
            "default": "bundled",
        },
        {
            "option": "custom_emulator_path",
            "type": "file",
            "label": _("Custom emulator path"),
            "help": _("Path to ShadPS4 SDL emulator (only used if 'Custom' is selected)"),
            "advanced": True,
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
    ]

    system_options_override = [{"option": "disable_runtime", "default": True}]

    def get_sdl_emulator_path(self):
        """Derive the SDL emulator path from the launcher path."""
        launcher = self.get_executable()
        launcher_dir = os.path.dirname(launcher)
        # Look for the SDL AppImage in the same directory
        for name in ("Shadps4-sdl.AppImage", "shadps4-sdl.AppImage", "shadPS4-sdl.AppImage"):
            sdl_path = os.path.join(launcher_dir, name)
            if system.path_exists(sdl_path):
                return sdl_path
        return None

    def play(self):
        arguments = self.get_command()

        # Emulator selection
        emu_choice = self.runner_config.get("emulator", "bundled")
        if emu_choice == "bundled":
            emu_path = self.get_sdl_emulator_path()
            if emu_path:
                arguments.extend(["-e", emu_path])
            else:
                arguments.append("-d")  # Fall back to launcher default
        elif emu_choice == "custom":
            custom_path = self.runner_config.get("custom_emulator_path")
            if custom_path:
                arguments.extend(["-e", custom_path])
            else:
                arguments.append("-d")
        else:  # default
            arguments.append("-d")

        # Game
        game_path = self.game_config.get("main_file") or ""
        if not system.path_exists(game_path):
            raise MissingGameExecutableError(filename=game_path)
        arguments.extend(["-g", game_path])

        # Emulator args after separator
        arguments.append("--")
        arguments.extend(["--fullscreen", "true" if self.runner_config.get("fullscreen") else "false"])

        return {"command": arguments}
