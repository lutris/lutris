'''
Created on Apr 25, 2009

@author: strider
'''

from wine import wine
import os

class nulldc(wine):
    def __init__(self,settings=None):
        self.description = "Runs Dreamcast games with nullDC emulator"
        self.machine = "Sega Dreamcast"
        self.requires = ["wine","joy2key"]
        self.nulldc_path = "/mnt/seagate/games/nullDC/"
        self.executable = "nullDC_1.0.3_mmu.exe"
        self.gamePath = "/mnt/seagate/games/Soul Calibur [NTSC-U]/"
        self.gameIso = "disc.gdi"
        self.args = ""
        self.game_options = [{"option": "file", "type":"single", "name":"iso", "label":"Disc image"}]
        self.runner_options = [{"option":"fullscreen","type":"bool","name":"fullscreen","label":"Fullscreen"}]

    def is_installed(self):
        return True


    def play(self):
        os.chdir(self.nulldc_path)
        #-config ImageReader:DefaultImage="[rompath]/[romfile]"

        path = self.gamePath+self.gameIso
        path = path.replace("/","\\")
        path = "Z:"+path

        command = ["WINEDEBUG=-all","wine",self.nulldc_path+self.executable,"-config",
        " ImageReader:DefaultImage=\""+path+"\"","-config","drkpvr:Fullscreen.Enabled=1"]
        
        return command