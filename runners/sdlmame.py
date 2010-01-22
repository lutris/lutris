'''
Created on Apr 25, 2009

@author: strider
'''

import os
import subprocess
from runner import Runner

class sdlmame(Runner):
    def __init__(self,settings=None):
        self.executable = "sdlmame"
        self.package = "sdlmame"
        self.description = "Runs arcade games with SDLMame"
        self.machine = "Arcade"

        self.game_options = [{"option": "file", "type":"single", "name":"rom", "label":"Rom file"}]
        self.runner_options = []
        
        if settings:
            self.romdir = settings["path"]
            self.rom = settings["rom"]
            self.mameconfigdir = os.path.join(os.path.expanduser("~"),".mame")
            if not os.path.exists(os.path.join(self.mameconfigdir,"mame.ini")):
                try:
                    os.makedirs(self.mameconfigdir)
                except OSError:
                    print "mame directory already exists"
                os.chdir(self.mameconfigdir)
                subprocess.Popen([self.executable,"-createconfig"],stdout=subprocess.PIPE).communicate()[0]
        
    
    def play(self):
        os.chdir(self.romdir)
        return [self.executable,"-inipath",self.mameconfigdir,"-skip_gameinfo","-rompath",self.romdir,self.rom]