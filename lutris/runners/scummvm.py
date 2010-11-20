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

from lutris.runners.runner import Runner
from lutris.config import LutrisConfig
from lutris.constants import *
from ConfigParser import ConfigParser
import os
import subprocess

class scummvm(Runner):
    def __init__(self,settings=None):
        self.scummvm_config_file = os.path.join(os.path.expanduser("~"),".scummvmrc")
        self.executable = "scummvm"
        self.package = "scummvm"
        self.is_installable = True
        self.description = "Runs LucasArts games based on the Scumm engine"
        self.machine = "LucasArts point and click games"
        self.gfxmode = "--gfx-mode=normal"
        self.fullscreen = "-f"      # -F for windowed
        self.installer_options = [{'option': 'foo','type': "label",
                                    'label': "Click on install to launch ScummVM and install the game"}]
        self.game_options = []
        scaler_modes = [("2x","2x"),
                        ("3x","3x"),
                        ("2xsai","2xsai"),
                        ("advmame2x","advmame2x"),
                        ("advmame3x","advmame3x"),
                        ("dotmatrix","dotmatrix"),
                        ("hq2x","hq2x"),
                        ("hq3x","hq3x"),
                        ("normal","normal"),
                        ("super2xsai","super2xsai"),
                        ("supereagle","supereagle"),
                        ("tv2x","tv2x")]
        self.runner_options = [ \
            {"option":"fullscreen", "label":"Fullscreen", "type":"bool"},
            {"option":"gfx-mode", "label": "Graphics scaler", "type":"one_choice", "choices":scaler_modes}]

        if isinstance(settings, LutrisConfig):
            config = settings.config
            if "scummvm" in config:
                if "fullscreen" in config["scummvm"]:
                    if config["scummvm"]["fullscreen"] == False:
                        self.fullscreen = "-F"
                if "gfx-mode" in config["scummvm"]:
                    self.gfxmode = "--gfx-mode="+config["scummvm"]["gfx-mode"]
            self.game = settings["name"]

    def play(self):
        return [self.executable,self.fullscreen,self.gfxmode,self.game]

    def import_games(self):
        """
        Parse the scummvm config file and imports
        the games in Lutris config files.
        """
        if os.path.exists(self.scummvm_config_file):
            config_parser = ConfigParser()
            config_parser.read(self.scummvm_config_file)
            config_sections = config_parser.sections()
            if "scummvm" in config_sections:
                config_sections.remove("scummvm")
            for section in config_sections:
                realname = config_parser.get(section, "description")
                self.add_game(section, realname)

    def get_install_command(self):
        command = "%s" % (self.executable)
        return command

    def add_game(self,name,realname):
        lutris_config = LutrisConfig()
        lutris_config.config = {"runner":"scummvm", "realname":realname, "name": name }
        lutris_config.save("game")

    def get_game_list(self):
        """
        Return the entire list of games supported by ScummVM
        """
        scumm_output = subprocess.Popen(
                [self.executable, "-z"],
                stdout=subprocess.PIPE).communicate()[0]
        game_list = str.split(scumm_output, "\n")
        game_array = []
        game_list_start = False
        for game in game_list:
            if game_list_start:
                if len(game) > 1:
                    dir_limit = game.index(" ")
                else :
                    dir_limit = None
                if dir_limit is not  None:
                    game_dir = game[0:dir_limit]
                    game_name = game[dir_limit+1:len(game)].strip()
                    game_array.append([game_dir,game_name])
            # The actual list is below a separator
            if game.startswith("-----"):
                game_list_start = True

        return game_array

