"""Runner for Linux games"""
# Standard Library
import os
import stat
from gettext import gettext as _

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.strings import split_arguments


class linux(Runner):
    human_name = _("Linux")
    description = _("Runs native games")
    platforms = [_("Linux")]

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
            "option":
            "working_dir",
            "type":
            "directory_chooser",
            "label":
            _("Working directory"),
            "help": _(
                "The location where the game is run from.\n"
                "By default, Lutris uses the directory of the "
                "executable."
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
            "option":
            "ld_library_path",
            "type":
            "directory_chooser",
            "label":
            _("Add directory to LD_LIBRARY_PATH"),
            "advanced":
            True,
            "help": _(
                "A directory where libraries should be searched for "
                "first, before the standard set of directories; this is "
                "useful when debugging a new library or using a "
                "nonstandard library for special purposes."
            ),
        },
    ]

    def __init__(self, config=None):
        super(linux, self).__init__(config)
        self.ld_preload = None

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        exe = self.game_config.get("exe")
        if not exe:
            return
        if os.path.isabs(exe):
            return exe
        if self.game_path:
            return os.path.join(self.game_path, exe)
        return system.find_executable(exe)

    def get_relative_exe(self):
        """Return a relative path if a working dir is set in the options
        Some games such as Unreal Gold fail to run if given the absolute path
        """
        exe_path = self.game_exe
        working_dir = self.game_config.get("working_dir")
        if working_dir:
            parts = exe_path.split(os.path.expanduser(working_dir))
            if len(parts) == 2:
                return "." + parts[1]
        return exe_path

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return os.path.expanduser(option)
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        return super(linux, self).working_dir

    def is_installed(self):
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def play(self):
        """Run native game."""
        launch_info = {}

        if not self.game_exe or not system.path_exists(self.game_exe):
            return {"error": "FILE_NOT_FOUND", "file": self.game_exe}

        # Quit if the file is not executable
        mode = os.stat(self.game_exe).st_mode
        if not mode & stat.S_IXUSR:
            return {"error": "NOT_EXECUTABLE", "file": self.game_exe}

        if not system.path_exists(self.game_exe):
            return {"error": "FILE_NOT_FOUND", "file": self.game_exe}

        ld_preload = self.game_config.get("ld_preload")
        if ld_preload:
            launch_info["ld_preload"] = ld_preload

        ld_library_path = self.game_config.get("ld_library_path")
        if ld_library_path:
            launch_info["ld_library_path"] = os.path.expanduser(ld_library_path)

        command = [self.get_relative_exe()]

        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)
        launch_info["command"] = command
        return launch_info
