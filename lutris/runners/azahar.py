from gettext import gettext as _

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system

VER_STR = "2121.2"


class azahar(Runner):
    human_name = _("Azahar")
    platforms = [_("Nintendo 3DS")]
    description = _("Nintendo 3DS Emulator")
    runnable_alone = True
    runner_executable = "azahar/azahar.AppImage"
    flatpak_id = "org.azahar_emu.Azahar"
    download_url = f"https://github.com/azahar-emu/azahar/releases/download/{VER_STR}/azahar.AppImage"

    # Azahar uses an AppImage, runtime causes QT  platform plugins issues.
    system_options_override = [{"option": "disable_runtime", "default": True}]
    game_options = [
        {
            "option": "main_file",
            "label": _("The game data, commonly called a ROM image."),
            "type": "file",
            "default_path": "game_path",
        },
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
        arguments = self.get_command()
        rom = self.game_config.get("main_file") or ""

        if not system.path_exists(rom):
            raise MissingGameExecutableError(filename=rom)

        fullscreen = self.runner_config.get("fullscreen") or ""

        if fullscreen:
            arguments.append("-f")
        # Don't pass '-w' here if `fullscreen' is not set to avoid interfering
        # with (possible) present of future emulator caching of last used mode.
        # Like that we avoid complications of having both `fullscreen' and
        # `windowed' options to handle.

        arguments.append(rom)
        return {"command": arguments}
