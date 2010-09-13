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

from lutris.config import LutrisConfig
from lutris.runners.runner import Runner
import ConfigParser
import os

class cedega(Runner):
    def __init__(self,settings = None):
        self.executable = "cedega"
        self.description = "Runs Windows games with Cedega"
        self.machine = "Windows games"
        self.is_installable = False
        self.game_options = [{"option":"shortcut",
                              "type": "string",
                              "label": "Shortcut"},
                             {"option":"folder",
                              "type": "string",
                              "label": "Folder"}]
        self.runner_options = []
        if settings:
            self.folder=settings["game"]["folder"]
            self.game = settings["game"]["shortcut"]

    def import_games(self):
        if not self.is_installed():
            return "Cedega is not installed"
        cedega_settings_dir = os.path.join(os.path.expanduser('~'),".cedega")
        if (os.path.exists(cedega_settings_dir)):
            os.chdir(cedega_settings_dir)
            dirs = os.listdir(cedega_settings_dir)
            for game_folder in dirs:
                if not game_folder.startswith(".") and  game_folder != "configuration_profiles":
                    shortcuts = self.get_cedega_shortcuts(os.path.join(cedega_settings_dir,
                                                                       game_folder))
                    for shortcut in shortcuts:
                        print "Importing %s - %s" % (game_folder, shortcut)
                        self.add_game(game_folder,shortcut)
            return True
        else:
            return "No Cedega directory"

    def get_cedega_shortcuts(self,path):
        os.chdir(path)
        if os.path.exists("./games.ini"):
            cedega_config = ConfigParser.ConfigParser()
            cedega_config.read("./games.ini")
            shortcuts = cedega_config.sections()
            return shortcuts

    def add_game(self,folder,shortcut):
        lutris_config = LutrisConfig()
        lutris_config.config = {"runner": "cedega",
                                "realname": shortcut,
                                "game": {"folder": folder, "shortcut": shortcut}}
        lutris_config.save(type="game")
        
    def play(self):
        return [self.executable,
                "--run",
                "\"" + self.folder + "\"",
                "\"" + self.game + "\""]

