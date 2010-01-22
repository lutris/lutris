__author__="strider"
__date__ ="$21 nov. 2009 21:07:14$"

from runners.runner import Runner

class vavoom(Runner):
    def __init__(self,settings=None):
        self.executable = "vavoom"
        self.package = None
        self.description = "Runs games based on the Doom engine like Doom, Hexen, Heretic"
        self.machine = "Games based on the Doom engine"
        if settings:
            self.wad = settings["main"]["wad"]

        
    
    def play(self):
        return [self.executable,self.gfxmode,self.wad]