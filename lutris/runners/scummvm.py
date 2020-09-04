# Standard Library
import os
import subprocess
from gettext import gettext as _

# Lutris Modules
from lutris import settings
from lutris.runners.runner import Runner
from lutris.util import system
from lutris.util.strings import split_arguments


class scummvm(Runner):
    description = _("Runs various 2D point-and-click adventure games.")
    human_name = _("ScummVM")
    platforms = [_("Linux")]
    runnable_alone = True
    runner_executable = "scummvm/bin/scummvm"
    game_options = [
        {
            "option": "game_id",
            "type": "string",
            "label": _("Game identifier")
        },
        {
            "option": "path",
            "type": "directory_chooser",
            "label": _("Game files location")
        },
        {
            "option": "subtitles",
            "label": _("Enable subtitles (if the game has voice)"),
            "type": "bool",
            "default": False,
        },
        {
            "option": "args",
            "type": "string",
            "label": _("Arguments"),
            "help": _("Command line arguments used when launching the game"),
        },
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "label": _("Fullscreen mode"),
            "type": "bool",
            "default": False,
        },
        {
            "option":
            "aspect",
            "label":
            _("Aspect ratio correction"),
            "type":
            "bool",
            "default":
            True,
            "help": _(
                "Most games supported by ScummVM were made for VGA "
                "display modes using rectangular pixels. Activating "
                "this option for these games will preserve the 4:3 "
                "aspect ratio they were made for."
            ),
        },
        {
            "option":
            "gfx-mode",
            "label":
            _("Graphic scaler"),
            "type":
            "choice",
            "default":
            "3x",
            "choices": [
                ("1x", "1x"),
                ("2x", "2x"),
                ("3x", "3x"),
                ("hq2x", "hq2x"),
                ("hq3x", "hq3x"),
                ("advmame2x", "advmame2x"),
                ("advmame3x", "advmame3x"),
                ("2xsai", "2xsai"),
                ("super2xsai", "super2xsai"),
                ("supereagle", "supereagle"),
                ("tv2x", "tv2x"),
                ("dotmatrix", "dotmatrix"),
            ],
            "help":
            _("The algorithm used to scale up the game's base "
              "resolution, resulting in different visual styles. "),
        },
        {
            "option": "datadir",
            "label": _("Data directory"),
            "type": "directory_chooser",
            "help": _("Defaults to share/scummvm if unspecified."),
            "advanced": True,
        },
    ]

    @property
    def game_path(self):
        return self.game_config.get("path")

    @property
    def libs_dir(self):
        path = os.path.join(settings.RUNNER_DIR, "scummvm/lib")
        return path if system.path_exists(path) else ""

    def get_command(self):
        return [
            self.get_executable(),
            "--extrapath=%s" % self.get_scummvm_data_dir(),
            "--themepath=%s" % self.get_scummvm_data_dir(),
        ]

    def get_scummvm_data_dir(self):
        data_dir = self.runner_config.get("datadir")

        if data_dir is None:
            root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
            data_dir = os.path.join(root_dir, "share/scummvm")

        return data_dir

    def get_run_data(self):
        env = {"LD_LIBRARY_PATH": "%s;$LD_LIBRARY_PATH" % self.libs_dir}
        return {"env": env, "command": self.get_command()}

    def play(self):
        command = self.get_command()

        # Options
        if self.runner_config.get("aspect"):
            command.append("--aspect-ratio")

        if self.game_config.get("subtitles"):
            command.append("--subtitles")

        if self.runner_config.get("fullscreen"):
            command.append("--fullscreen")
        else:
            command.append("--no-fullscreen")

        mode = self.runner_config.get("gfx-mode")
        if mode:
            command.append("--gfx-mode=%s" % mode)
        # /Options
        command.append("--path=%s" % self.game_path)
        args = self.game_config.get("args") or ""
        for arg in split_arguments(args):
            command.append(arg)
        command.append(self.game_config.get("game_id"))
        launch_info = {"command": command, "ld_library_path": self.libs_dir}

        return launch_info

    def get_game_list(self):
        """Return the entire list of games supported by ScummVM."""
        scumm_output = subprocess.Popen([self.get_executable(), "--list-games"],
                                        stdout=subprocess.PIPE).communicate()[0]
        game_list = str.split(scumm_output, "\n")
        game_array = []
        game_list_start = False
        for game in game_list:
            if game_list_start:
                if len(game) > 1:
                    dir_limit = game.index(" ")
                else:
                    dir_limit = None
                if dir_limit is not None:
                    game_dir = game[0:dir_limit]
                    game_name = game[dir_limit + 1:len(game)].strip()
                    game_array.append([game_dir, game_name])
            # The actual list is below a separator
            if game.startswith("-----"):
                game_list_start = True
        return game_array
