'''
Created on Apr 25, 2009

@author: strider
'''
from runner import Runner
import os
import lutris.constants

class wine(Runner):
    def __init__(self,settings = None):
        self.executable = "wine"
        self.package = "wine"
        self.machine = "Windows games"
        self.description = "Run Windows games with Wine"
        self.game_options = [ {"option": "exe", "type":"single", "label":"Executable"},
                              {"option": "args", "type": "string", "label": "Arguments" }]
        mouse_warp_choices = [("Enable","enable"),("Disable","disable"),("Force","force")]
        self.runner_options = [{"option": "cdrom_path", "label":"CDRom mount point", "type": "directory_chooser"},
                               {"option":"mousewarp","label":"Mouse Warp Override","type":"one_choice","choices":mouse_warp_choices}]

        if settings:
            self.gameExe = settings["game"]["exe"]
            if "args" in settings.config["game"]:
                self.args = settings["game"]["args"]
            else:
                self.args = None
            if "wine" in settings.config:
                if "mousewarp" in settings.config["wine"]:
                    self.set_regedit("HKEY_CURRENT_USER\Software\Wine\DirectInput", "MouseWarpOverride", settings.config["wine"]["mousewarp"])
        
    
    def set_regedit(self,path,key,value):
        """Plays with the windows registry
        path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
        """
        
        os.chdir(lutris.constants.tmp_path)
        #Make temporary reg file
        reg_file = open("wine_tmp.reg","w")
        reg_file.write("""REGEDIT4
[%s]
"%s"="%s"
""" % (path,key,value))
        reg_file.close()
        os.popen(self.executable + " regedit " + os.path.join(lutris.constants.tmp_path,"wine_tmp.reg"))
        
        
    def kill(self):
        """The kill command runs wineserver -k"""
        pass

    def play(self):
        self.game_path = os.path.dirname(self.gameExe)
        game_exe = os.path.basename(self.gameExe)
        
        command = [self.executable,"\""+game_exe+"\""]
        if self.args:
            for arg in self.args.split():
                command.append(arg)
        return command

