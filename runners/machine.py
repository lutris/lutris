from lutris.config import LutrisConfig
import subprocess


class machine:
    def __init__(self,settings):
        self.executable = ""

    def load(self,game):
        self.game = game
    def config(self):
        subprocess.Popen([self.configscript],stdout=subprocess.PIPE).communicate()[0]
    def play(self):
        pass
    def isInstalled(self):
        cmdline = "which " + self.executable
        cmdline = str.split(cmdline," ")
        result = subprocess.Popen(cmdline,stdout=subprocess.PIPE).communicate()[0]
        if result == '' :
            result = "not installed"
        return result
    
    def installDebPackage(self):
        result = subprocess.Popen(["gksu","apt-get","install",self.package],stdout=subprocess.PIPE).communicate()[0]
        
    def write_config(self,id,name,fullpath):
        """Writes game config to settings directory"""
        system = self.__class__.__name__
        index= fullpath.rindex("/")
        exe = fullpath[index+1:]
        path = fullpath[:index]
        if path.startswith("file://"):
            path = path[7:]
        gameConfig = LutrisConfig()
        values = {"main":{ "path":path, "exe":exe, "realname" : name, "system":system }}
        gameConfig.write_game_config(id, values)
        