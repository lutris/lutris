"""Citra runner"""
# Lutris Modules
from lutris.exceptions import UnavailableLibraries
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM


class citra(Runner):  # pylint: disable=invalid-name

    """Runner for Nintendo 3DS games using Citra"""
    human_name = "Citra"
    platforms = ["Nintendo 3DS"]
    require_libs = {"libQt5OpenGL.so.5", "libQt5Widgets.so.5", "libQt5Multimedia.so.5"}
    description = "Nintendo 3DS emulator"
    runner_executable = "citra/citra-qt"
    runnable_alone = True
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": "ROM file",
            "help": "The game data, commonly called a ROM image.",
        }
    ]

    def prelaunch(self):
        """Check all required libraries are installed"""
        available_libs = set()
        for lib in LINUX_SYSTEM.shared_libraries:
            if lib in self.require_libs:
                available_libs.add(lib)
        unavailable_libs = self.require_libs - available_libs
        if unavailable_libs:
            raise UnavailableLibraries(unavailable_libs)
        return True

    def play(self):
        """Run the game."""
        arguments = [self.get_executable()]
        rom = self.game_config.get("main_file") or ""
        if not system.path_exists(rom):
            return {"error": "FILE_NOT_FOUND", "file": rom}
        arguments.append(rom)
        return {"command": arguments}
