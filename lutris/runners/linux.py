# -*- coding: utf-8 -*-
import os
import shlex
import stat
from lutris.runners.runner import Runner


class linux(Runner):
    """Runs native games"""
    human_name = "Linux"

    game_options = [
        {
            "option": "exe",
            "type": "file",
            "default_path": "game_path",
            "label": "Executable",
            'help': "The game's main executable file"
        },
        {
            "option": "args",
            "type": "string",
            "label": "Arguments",
            'help': "Command line arguments used when launching the game"
        },
        {
            "option": "working_dir",
            "type": "directory_chooser",
            "label": "Working directory",
            'help': ("The location where the game is run from.\n"
                     "By default, Lutris uses the directory of the "
                     "executable.")
        },
        {
            "option": "ld_preload",
            "type": "file",
            "label": "Preload library",
            'advanced': True,
            'help': ("A library to load before running the game's executable.")
        },
        {
            "option": "ld_library_path",
            "type": "directory_chooser",
            "label": "Add directory to LD_LIBRARY_PATH",
            'advanced': True,
            'help': ("A directory where libraries should be searched for "
                     "first, before the standard set of directories; this is "
                     "useful when debugging a new library or using a "
                     "nonstandard library for special purposes.")
        }
    ]

    def __init__(self, config=None):
        super(linux, self).__init__(config)
        self.platform = "Linux games"
        self.ld_preload = None

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        exe = self.game_config.get('exe')
        if exe:
            if os.path.isabs(exe):
                exe_path = exe
            else:
                exe_path = os.path.join(self.game_path, exe)
            return exe_path

    def get_relative_exe(self):
        """Return a relative path if a working dir is set in the options
        Some games such as Unreal Gold fail to run if given the absolute path
        """
        exe_path = self.game_exe
        working_dir = self.game_config.get('working_dir')
        if working_dir:
            parts = exe_path.split(os.path.expanduser(working_dir))
            if len(parts) == 2:
                return "." + parts[1]
        return exe_path

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get('working_dir')
        if option:
            return os.path.expanduser(option)
        if self.game_exe:
            return os.path.dirname(self.game_exe)
        else:
            return super(linux, self).working_dir

    def is_installed(self):
        """Well of course Linux is installed, you're using Linux right ?"""
        return True

    def play(self):
        """Run native game."""
        launch_info = {}

        if not os.path.exists(self.game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': self.game_exe}

        # Quit if the file is not executable
        mode = os.stat(self.game_exe).st_mode
        if not mode & stat.S_IXUSR:
            return {'error': 'NOT_EXECUTABLE', 'file': self.game_exe}

        if not os.path.exists(self.game_exe):
            return {'error': 'FILE_NOT_FOUND', 'file': self.game_exe}

        ld_preload = self.game_config.get('ld_preload')
        if ld_preload:
            launch_info['ld_preload'] = ld_preload

        ld_library_path = self.game_config.get('ld_library_path')
        if ld_library_path:
            launch_info['ld_library_path'] = os.path.expanduser(ld_library_path)

        command = [self.get_relative_exe()]

        args = self.game_config.get('args') or ''
        for arg in shlex.split(args):
            command.append(arg)
        launch_info['command'] = command
        return launch_info
