# Standard Library
import os
import shlex
from gettext import gettext as _

from lutris import settings
from lutris.exceptions import MissingGameExecutableError

# Lutris Modules
from lutris.runners.commands.dosbox import dosexec, makeconfig  # NOQA pylint: disable=unused-import
from lutris.runners.runner import Runner
from lutris.util import system


class dosbox(Runner):
    human_name = _("DOSBox")
    description = _("MS-DOS emulator")
    platforms = [_("MS-DOS")]
    runnable_alone = True
    runner_executable = "dosbox/dosbox"
    flatpak_id = "io.github.dosbox-staging"
    game_options = [
        {
            "option": "main_file",
            "type": "file",
            "label": _("Main file"),
            "help": _(
                "The CONF, EXE, COM or BAT file to launch.\n"
                "If the executable is managed in the config file, this should be the config file, "
                "instead specifying it in 'Configuration file'."
            ),
        },
        {
            "option": "config_file",
            "type": "file",
            "label": _("Configuration file"),
            "help": _(
                "Start DOSBox with the options specified in this file. \n"
                "It can have a section in which you can put commands "
                "to execute on startup. Read DOSBox's documentation "
                "for more information."
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Command line arguments"),
            "help": _("Command line arguments used when launching DOSBox"),
            "validator": shlex.split,
        },
        {
            "option": "working_dir",
            "type": "directory",
            "label": _("Working directory"),
            "warn_if_non_writable_parent": True,
            "help": _(
                "The location where the game is run from.\nBy default, Lutris uses the directory of the executable."
            ),
        },
    ]

    runner_options = [
        {
            "option": "fullscreen",
            "section": _("Graphics"),
            "label": _("Open game in fullscreen"),
            "type": "bool",
            "default": False,
            "help": _("Tells DOSBox to launch the game in fullscreen."),
        },
        {
            "option": "exit",
            "label": _("Exit DOSBox with the game"),
            "type": "bool",
            "default": True,
            "help": _("Shut down DOSBox when the game is quit."),
        },
    ]

    def make_absolute(self, path):
        """Return a guaranteed absolute path"""
        if not path:
            return ""
        path = os.path.expanduser(path)
        if os.path.isabs(path):
            return path
        directory = self.game_data.get("directory")
        if directory:
            directory = os.path.expanduser(directory)
            return os.path.join(directory, path)
        return ""

    @property
    def main_file(self):
        return self.make_absolute(self.game_config.get("main_file"))

    @property
    def libs_dir(self):
        path = os.path.join(settings.RUNNER_DIR, "dosbox/lib")
        return path if system.path_exists(path) else ""

    def get_run_data(self):
        env = self.get_env()
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [self.libs_dir, env.get("LD_LIBRARY_PATH")]))
        return {"env": env, "command": self.get_command()}

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        option = self.game_config.get("working_dir")
        if option:
            return os.path.expanduser(option)
        if self.main_file:
            return os.path.dirname(self.main_file)
        return super().working_dir

    def play(self):
        main_file = self.main_file
        if not system.path_exists(main_file):
            raise MissingGameExecutableError(filename=main_file)
        args = shlex.split(self.game_config.get("args") or "")
        command = self.get_command()

        if main_file.endswith(".conf"):
            command.append("-conf")
            command.append(main_file)
        else:
            command.append(main_file)
        # Options
        if self.game_config.get("config_file"):
            command.append("-conf")
            command.append(self.make_absolute(self.game_config["config_file"]))

        if self.runner_config.get("fullscreen"):
            command.append("-fullscreen")

        if self.runner_config.get("exit"):
            command.append("-exit")

        if args:
            command.extend(args)

        return {"command": command, "ld_library_path": self.libs_dir}
