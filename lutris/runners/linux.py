"""Runner for Linux games"""

# Standard Library
import os
import stat
from gettext import gettext as _
from typing import Callable

# Lutris Modules
from lutris.exceptions import GameConfigError, MissingGameExecutableError
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.strings import split_arguments


class linux(Runner):
    human_name = _("Linux")
    description = _("Runs native games")
    platforms = [_("Linux")]
    entry_point_option = "exe"

    game_options = [
        {
            "option": "exe",
            "type": "file",
            "default_path": "game_path",
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

    def __init__(self, config=None):
        super().__init__(config)
        self.ld_preload = None

    @property
    def game_exe(self):
        """Return the game's executable's path. The file may not exist, but
        this returns None if the exe path is not defined."""
        exe = self.game_config.get("exe")
        if not exe:
            return None
        exe = os.path.expanduser(exe)  # just in case!
        if os.path.isabs(exe):
            return exe
        if self.game_path:
            return os.path.join(self.game_path, exe)
        return system.find_executable(exe)

    def resolve_game_path(self):
        return super().resolve_game_path() or os.path.dirname(self.game_exe or "")

    def get_relative_exe(self, exe_path, working_dir):
        """Return a relative path if a working dir is provided
        Some games such as Unreal Gold fail to run if given the absolute path
        """
        if exe_path and working_dir:
            relative = os.path.relpath(exe_path, start=working_dir)
            if not relative.startswith("../"):
                # We can't use the working dir implicitly to start a command
                # so we make it explicit with "./"
                if not os.path.isabs(relative):
                    relative = "./" + relative
                return relative
        return exe_path

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return os.path.expanduser(option)
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        return super().working_dir

    @property
    def nvidia_shader_cache_path(self):
        """Linux programs should get individual shader caches if possible."""
        return self.game_path or self.shader_cache_dir

    def is_installed(self, flatpak_allowed: bool = True) -> bool:
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def can_uninstall(self):
        return False

    def uninstall(self, uninstall_callback: Callable[[], None]) -> None:
        raise RuntimeError("Linux shouldn't be installed.")

    def get_launch_config_command(self, gameplay_info, launch_config):
        # The linux runner has no command (by default) beyond the 'exe' itself;
        # so the command in gameplay_info is discarded.
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

    def get_command(self):
        # There's no command for a Linux game; the game executable
        # is the first thing in the game's command line, not any runner thing.
        return []

    def play(self):
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

        command = [self.get_relative_exe(exe, self.working_dir)]

        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)
        launch_info["command"] = command
        return launch_info
