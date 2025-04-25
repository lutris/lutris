import os
import shutil
from gettext import gettext as _

from lutris import settings
from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.log import logger

REL_STR = "2120.3"
VER_STR = f"azahar-{REL_STR}-linux-appimage"


class azahar(Runner):
    human_name = _("Azahar")
    platforms = [_("Nintendo 3DS")]
    description = _("Nintendo 3DS Emulator")
    runnable_alone = True
    runner_executable = f"azahar/{VER_STR}/azahar.AppImage"
    flatpak_id = "org.azahar_emu.Azahar"
    download_url = f"https://github.com/azahar-emu/azahar/releases/download/{REL_STR}/{VER_STR}.tar.gz"

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

    def __init__(self, config=None):
        super().__init__(config)

    def extract_icon(self, runner_dir):
        icon_src = os.path.join(os.path.join(runner_dir, VER_STR), "dist/azahar.png")
        icon_dst = os.path.join(os.path.join(settings.RUNTIME_DIR, "icons"), "azahar.png")
        if not os.path.exists(icon_dst):
            try:
                shutil.copyfile(icon_src, icon_dst)
                logger.debug(f"Installed runner icon: {icon_dst}")
            except Exception as e:
                logger.debug(f"Failed to copy {icon_src} to {icon_dst} for runner Azahar. exc: {e}")

    def download_and_extract(self, url, dest=None, **opts):
        super().download_and_extract(url, dest, **opts)
        self.extract_icon(runner_dir=dest)

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
