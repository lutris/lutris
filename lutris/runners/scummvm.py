# -*- coding: utf-8 -*-
import os
import subprocess

from lutris import settings
from lutris.util.system import find_executable
from lutris.runners.runner import Runner

SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".scummvmrc")


class scummvm(Runner):
    """Runs LucasArts games based on the Scumm engine"""
    executable = "scummvm"
    package = "scummvm"
    platform = "LucasArts point and click games"
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
            "option": "gfx-mode",
            "label": "Graphics scaler",
            "type": "choice",
            "choices": scaler_modes
        }
    ]

    def install(self):
        self.download_and_extract("scummvm-1.6.0-i386.tar.gz")

    def get_executable(self):
        scummvm_path = os.path.join(settings.RUNNER_DIR, 'scummvm/scummvm')
        if not os.path.exists(scummvm_path):
            return find_executable("scummvm")
        else:
            return scummvm_path

    def get_game_path(self):
        return self.settings['game']['path']

    def play(self):
        if self.runner_config.get("windowed"):
            fullscreen = "-F"
        else:
            fullscreen = "-f"
        mode = self.runner_config.get("gfx-mode")
        if mode:
            gfxmode = "--gfx-mode=%s" % mode
        else:
            gfxmode = "--gfx-mode=normal"
        game = self.settings["game"]["game_id"]

        launch_info = {'command': [
            self.get_executable(),
            "--path=\"%s\"" % self.settings['game']['path'],
            fullscreen, gfxmode, game
        ]}

        lib_dir = os.path.join(settings.DATA_DIR,
                               'runners/scummvm/usr/lib/i386-linux-gnu')
        if os.path.exists(lib_dir):
            launch_info['ld_library_path'] = lib_dir

        return launch_info

    def get_game_list(self):
        """ Return the entire list of games supported by ScummVM """
        scumm_output = subprocess.Popen(
            ["scummvm", "-z"], stdout=subprocess.PIPE
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
