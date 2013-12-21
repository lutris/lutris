# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

""" Runner for point and click adventure games. """

import os
import subprocess

from lutris import settings
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.util.system import find_executable
from lutris.runners.runner import Runner
from lutris.config import LutrisConfig
from ConfigParser import ConfigParser

SCUMMVM_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".scummvmrc")


def add_game(game_id, realname):
    """Add scummvm from the auto-import"""
    lutris_config = LutrisConfig()
    lutris_config.config = {"runner": "scummvm",
                            "realname": realname,
                            "name": slugify(realname),
                            'game': {
                                'game_id': game_id
                            }}
    lutris_config.save("game")


def import_games():
    """Parse the scummvm config file and imports the games in Lutris config
    files."""
    logger.info("Importing ScummVM games.")
    imported_games = []
    if not os.path.exists(SCUMMVM_CONFIG_FILE):
        logger.info("No ScummVM config found")
        return None
    config_parser = ConfigParser()
    config_parser.read(SCUMMVM_CONFIG_FILE)
    config_sections = config_parser.sections()
    if "scummvm" in config_sections:
        config_sections.remove("scummvm")
    for section in config_sections:
        realname = config_parser.get(section, "description")
        logger.info("Found ScummVM game %s", realname)
        add_game(section, realname)
        imported_games.append({'id': slugify(realname),
                               'name': realname,
                               'runner': 'scummvm'})
    return imported_games


# pylint: disable=C0103
class scummvm(Runner):
    """Runs LucasArts games based on the Scumm engine"""
    def __init__(self, settings=None):
        super(scummvm, self).__init__()
        self.executable = "scummvm"
        self.package = "scummvm"
        self.platform = "LucasArts point and click games"
        self.game_options = [
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
        self.runner_options = [
            {
                "option": "windowed",
                "label": "Windowed",
                "type": "bool"
            },
            {
                "option": "gfx-mode",
                "label": "Graphics scaler",
                "type": "one_choice",
                "choices": scaler_modes
            }
        ]
        self.settings = settings

    def install(self):
        self.download_and_extract("scummvm.x86.tar.gz")

    def is_installed(self):
        return bool(self.get_executable())

    def get_executable(self):
        scummvm_path = os.path.join(settings.DATA_DIR,
                                    'runners/scummvm/scummvm')
        if not os.path.exists(scummvm_path):
            return find_executable("scummvm")

    def get_game_path(self):
        return self.settings['game']['path']

    def play(self):
        """Run ScummVM game"""
        gfxmode = "--gfx-mode=normal"
        fullscreen = "-f"  # -F for windowed
        config = self.settings.config
        if "scummvm" in self.settings.config:
            if "windowed" in config["scummvm"]:
                if self.settings.config["scummvm"]["windowed"] is True:
                    fullscreen = "-F"
            if "gfx-mode" in self.settings.config["scummvm"]:
                mode = self.settings.config["scummvm"]["gfx-mode"]
                gfxmode = "--gfx-mode=%s" % mode
        game = self.settings["game"]["game_id"]

        launch_info = {'command': [
            self.get_executable(),
            "--path=\"%s\"" % self.settings['game']['path'],
            fullscreen, gfxmode, game
        ]}

        lib_dir = os.path.join(settings.DATA_DIR, 'runners/scummvm/lib')
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
