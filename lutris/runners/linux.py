"""Runner for Linux games"""

import os
import stat
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING

from lutris.exceptions import GameConfigError, MissingGameExecutableError
from lutris.runners.runner import GamePlayInfoDict, Runner, RunnerOptionDict
from lutris.util import system
from lutris.util.steam.runtime import NO_STEAM_RUNTIME, STEAM_RUNTIME_CHOICES, get_runtime_command
from lutris.util.strings import split_arguments

if TYPE_CHECKING:
    from lutris.config import LaunchConfigDict


class linux(Runner):
    human_name = _("Linux")
    description = _("Runs native games")
    platform_dict = Runner.to_platform_dict([_("Linux")])
    entry_point_option = "exe"
    runner_options: list[RunnerOptionDict] = [
        {
            "option": "steam_linux_runtime",
            "type": "choice",
            "label": _("Steam Linux Runtime"),
            "choices": STEAM_RUNTIME_CHOICES,
            "default": NO_STEAM_RUNTIME,
            "help": _(
                "Run the game with a Steam Linux Runtime installed by Steam or umu. "
                "Scout also requires Soldier. Choose None to use system libraries."
            ),
        },
    ]
    system_options_override = [
        {"option": "disable_runtime", "available": False},
        {"option": "prefer_system_libs", "available": False},
        {"option": "use_sniper_runtime", "available": False},
    ]

    game_options = [
        {
            "option": "exe",
            "type": "file",
            "label": _("Executable"),
            "help": _("The game's main executable file"),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game"),
        },
        {
            "option": "working_dir",
            "type": "directory",
            "label": _("Working directory"),
            "help": _(
                "The location where the game is run from.\nBy default, Lutris uses the directory of the executable."
            ),
        },
        {
            "option": "ld_preload",
            "type": "file",
            "label": _("Preload library"),
            "advanced": True,
            "help": _("A library to load before running the game's executable."),
        },
        {
            "option": "ld_library_path",
            "type": "directory",
            "label": _("Add directory to LD_LIBRARY_PATH"),
            "advanced": True,
            "help": _(
                "A directory where libraries should be searched for "
                "first, before the standard set of directories; this is "
                "useful when debugging a new library or using a "
                "nonstandard library for special purposes."
            ),
        },
    ]

    @property
    def game_exe(self) -> str | None:
        """Return the game's executable's path. The file may not exist, but
        this returns None if the exe path is not defined."""
        exe = self.game_config.get("exe")
        if not exe:
            return None
        exe = os.path.expanduser(exe)
        if os.path.isabs(exe):
            return exe
        if self.game_path:
            return os.path.join(self.game_path, exe)
        return system.find_executable(exe)

    def resolve_game_path(self) -> str:
        return super().resolve_game_path() or os.path.dirname(self.game_exe or "")

    def get_relative_exe(self, exe_path: str, working_dir: str) -> str:
        """Return a relative path if a working dir is provided
        Some games such as Unreal Gold fail to run if given the absolute path
        """
        if exe_path and working_dir:
            relative = os.path.relpath(exe_path, start=working_dir)
            if not relative.startswith("../"):
                # Use an explicit relative path to launch from the working directory
                if not os.path.isabs(relative):
                    relative = "./" + relative
                return relative
        return exe_path

    @property
    def has_working_dir(self) -> bool:
        return bool(self.game_config.get("working_dir") or self.game_exe or super().has_working_dir)

    @property
    def working_dir(self) -> str:
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return os.path.expanduser(option)
        if game_exe := self.game_exe:
            return os.path.dirname(game_exe)
        return super().working_dir

    @property
    def nvidia_shader_cache_path(self) -> str:
        """Linux programs should get individual shader caches if possible."""
        return self.game_path or self.shader_cache_dir

    def is_installed(self, flatpak_allowed: bool = True) -> bool:
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def can_uninstall(self) -> bool:
        return False

    def uninstall(
        self,
        uninstall_callback: Callable[[], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        raise RuntimeError("Linux shouldn't be installed.")

    def get_launch_config_command(self, gameplay_info: GamePlayInfoDict, launch_config: LaunchConfigDict) -> list[str]:
        # Alternate configurations replace the executable and arguments
        if "command" in launch_config:
            command = split_arguments(launch_config["command"])
        else:
            command = []

        working_dir = os.path.expanduser(launch_config.get("working_dir") or self.working_dir)

        if "exe" in launch_config:
            config_exe = os.path.expanduser(launch_config["exe"] or "")
            command.append(self.get_relative_exe(config_exe, working_dir))
        elif len(command) == 0:
            raise GameConfigError(_("The runner could not find a command or exe to use for this configuration."))

        if launch_config.get("args"):
            command += split_arguments(launch_config["args"])

        return command

    def get_command(self) -> list[str]:
        return []

    def use_runtime(self) -> bool:
        return False

    def prepare_game_command(self, command: list[str], env: dict[str, str]) -> list[str]:
        runtime = self.runner_config.get("steam_linux_runtime") or NO_STEAM_RUNTIME
        runtime_command = get_runtime_command(str(runtime), env)
        if not runtime_command:
            return command

        # Pass game library overrides inside the container and keep Valve's library paths
        library_path = env.pop("LD_LIBRARY_PATH", "")
        preload = env.pop("LD_PRELOAD", "")
        if library_path or preload:
            script = (
                'if [ -n "$1" ]; then export LD_LIBRARY_PATH="$1${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; fi\n'
                'if [ -n "$2" ]; then export LD_PRELOAD="$2${LD_PRELOAD:+:$LD_PRELOAD}"; fi\n'
                'shift 2\nexec "$@"'
            )
            command = ["sh", "-c", script, "sh", library_path, preload, *command]
        return runtime_command + command

    def play(self) -> GamePlayInfoDict:
        """Run native game."""
        launch_info = {}

        exe = self.game_exe
        if not exe or not system.path_exists(exe):
            raise MissingGameExecutableError(filename=exe)

        # Quit if the file is not executable
        mode = os.stat(exe).st_mode
        if not mode & stat.S_IXUSR:
            raise GameConfigError(_("The file %s is not executable") % exe)

        ld_preload = self.game_config.get("ld_preload")
        if ld_preload:
            launch_info["ld_preload"] = ld_preload

        ld_library_path = self.game_config.get("ld_library_path")
        if ld_library_path:
            launch_info["ld_library_path"] = os.path.expanduser(ld_library_path)

        args = split_arguments(self.game_config.get("args") or "")
        launch_info["command"] = [self.get_relative_exe(exe, self.working_dir), *args]
        return launch_info
