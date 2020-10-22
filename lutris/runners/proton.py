"""Runner for Proton"""
# Standard Library
import os
import stat

# Lutris Modules
from lutris.runners.runner import Runner
from lutris.util import system


class proton(Runner):
    description = "Runs Windows games in Valve's Proton"
    human_name  = "Proton"
    platforms   = "Windows"
    multiple_versions = True
    entry_point_option = "exe"

    game_options = [
        {
            "option": "exe",
            "type": "file",
            "label": "Executable",
            "help": "The game's main EXE file",
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": "Working directory",
            "help": 
                "The location where the game is run from.\n"
                "By default, Lutris uses the directory of the "
                "executable.",
        },
        {
            "option": "compatdata",
            "type": "directory_chooser",
            "label": "Proton compat data",
            "help": 
                'The compatdata directory used by Proton.\n'
                "It's a directory containing a wine prefix "
                "and extra Proton specific files",
        },
    ]

    def __init__(self, config=None):
        super(proton, self).__init__(config)

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
        return super(proton, self).working_dir

    def is_installed(self):
        return True


    def play(self):
        launch_info = {}


        if not self.game_exe or not system.path_exists(self.game_exe):
            return {"error": "FILE_NOT_FOUND", "file": self.game_exe}

        # Quit if the file is not executable
        mode = os.stat(self.game_exe).st_mode
        if not mode & stat.S_IXUSR:
            return {"error": "NOT_EXECUTABLE", "file": self.game_exe}

        if not system.path_exists(self.game_exe):
            return {"error": "FILE_NOT_FOUND", "file": self.game_exe}



        command = [(self.runner_config.get("proton_exe"))]
        command.append("run")
        command.append(self.game_config.get("exe"))

        launch_info["command"] = command
        return launch_info


