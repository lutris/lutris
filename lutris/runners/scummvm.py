# -*- coding: utf-8 -*-
import os
import subprocess

from lutris import settings
from lutris.runners.runner import Runner

SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".scummvmrc")


class scummvm(Runner):
    """Runs various 2D point-and-click adventure games."""
    platform = "2D point-and-click games"
    game_options = [
        {
            'option': 'game_id',
            'type': 'string',
            'label': "Game identifier"
        },
        {
            'option': 'path',
            'type': 'directory_chooser',
            'label': "Path for the game"
        },
        {
            "option": "subtitles",
            "label": "Enable subtitles (if the game has voice)",
            "type": "bool"
        }
    ]

    scaler_modes = [
        ("2x", "2x"),
        ("3x", "3x"),
        ("2xsai", "2xsai"),
        ("advmame2x", "advmame2x"),
        ("advmame3x", "advmame3x"),
        ("dotmatrix", "dotmatrix"),
        ("hq2x", "hq2x"),
        ("hq3x", "hq3x"),
        ("normal", "normal"),
        ("super2xsai", "super2xsai"),
        ("supereagle", "supereagle"),
        ("tv2x", "tv2x")
    ]
    runner_options = [
        {
            "option": "windowed",
            "label": "Windowed",
            "type": "bool"
        },
        {
            "option": "aspect",
            "label": "Aspect ratio correction",
            "type": "bool"
        },
        {
            "option": "gfx-mode",
            "label": "Graphics scaler",
            "type": "choice",
            "choices": scaler_modes
        }
    ]

    tarballs = {
        'x64': "scummvm-1.7.0-x86_64.tar.gz",
    }

    @property
    def game_path(self):
        return self.settings['game']['path']

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'scummvm/bin/scummvm')

    def get_scummvm_data_dir(self):
        root_dir = os.path.dirname(os.path.dirname(self.get_executable()))
        return os.path.join(root_dir, 'share/scummvm')

    def play(self):
        command = [
            self.get_executable(),
            "--extrapath=\"%s\"" % self.get_scummvm_data_dir(),
            "--themepath=\"%s\"" % self.get_scummvm_data_dir(),
        ]

        # Options
        if self.runner_config.get("aspect"):
            command.append("--aspect-ratio")

        if self.settings['game'].get("subtitles"):
            command.append("--subtitles")

        if self.runner_config.get("windowed"):
            command.append("--no-fullscreen")
        else:
            command.append("--fullscreen")

        mode = self.runner_config.get("gfx-mode")
        if mode:
            command.append("--gfx-mode=%s" % mode)
        # /Options

        command.append("--path=\"%s\"" % self.game_path)
        command.append(self.settings["game"]["game_id"])

        launch_info = {'command': command}

        # Additionnal libraries needed by ScummVM may be stored there.
        lib_dir = os.path.join(settings.RUNNER_DIR, 'scummvm/lib')
        if os.path.exists(lib_dir):
            launch_info['ld_library_path'] = lib_dir

        return launch_info

    def get_game_list(self):
        """ Return the entire list of games supported by ScummVM """
        scumm_output = subprocess.Popen(
            [self.get_executable(), "--list-games"], stdout=subprocess.PIPE
        ).communicate()[0]
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
