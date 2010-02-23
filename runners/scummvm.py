'''
Created on May 5, 2009

@author: strider
'''

import os
import subprocess
from runner import Runner
from ConfigParser import ConfigParser
from lutris.config import LutrisConfig
from lutris.constants import *

class scummvm(Runner):
    def __init__(self,settings=None):
        self.scummvm_config_file = os.path.join(os.path.expanduser("~"),".scummvmrc")
        self.executable = "scummvm"
        self.package = "scummvm"
        self.is_installable = False
        self.description = "Runs LucasArts games based on the Scumm engine"
        self.machine = "LucasArts point and click games"
        self.gfxmode = "--gfx-mode=normal"
        self.fullscreen = "-f"      # -F for windowed
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

    def add_game(self,name,realname):
        lutris_config = LutrisConfig()
        #settings = {"runner":"scummvm", "realname":realname, "name": name }
        #name = "ScummVM-" + name
        lutris_config.config = {"runner":"scummvm", "realname":realname, "name": name }
        lutris_config.save("game")

    def get_game_list(self):
        gameList = subprocess.Popen([self.executable,"-z"],stdout=subprocess.PIPE).communicate()[0]
        gameList = str.split(gameList,"\n")
        gameArray = []
        gameListStart = False
        for game in gameList:
            if gameListStart:
                if len(game) > 1:
                    dirLimit=game.index(" ")
                else : 
                    dirLimit == None
                if dirLimit != None:
                    gameDir = game[0:dirLimit]
                    gameName = game[dirLimit+1:len(game)].strip()
                    gameArray.append([gameDir,gameName])
            if game.startswith("-----"):
                gameListStart = True
        return gameArray
        
        