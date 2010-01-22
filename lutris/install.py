import os
import urllib
import subprocess
import shutil
import platform
from lutris.config import LutrisConfig

class LutrisInstaller():
    def __init__(self,gameName):
        self.lutris_config = LutrisConfig()
        self.gameName = gameName
        self.gamesDir = "/mnt/seagate/games/" 
        self.lutrisConfigDir = self.lutris_config.lutris_config_path
        self.totalDownloaded = 0    
        self.gameDir= os.path.join(self.gamesDir,self.gameName)   
        if not os.path.exists(self.gameDir):
            os.mkdir(self.gameDir)
        self.parseconfig()
        self.writeConfig()
        
    def parseconfig(self):
        installFile = open(self.gameName+".lutris","r")
        self.installData = installFile.readlines()
        for line in self.installData:
            if line.startswith("execlink=") or line.startswith("datalink") or line.startswith("sourcelink"):
                url = line[str.index(line,"=")+1:].strip()
                if url =="request":
                    print "Please add the files manually"
                else:
                    destFile = self.download(url)
                    os.chdir(self.gameDir)
                    extIndex = destFile.rfind(".")
                    extension = destFile[extIndex:]
                    if extension == ".zip":
                        self.unzip(destFile)
                    elif extension == ".rar":
                        self.unrar(destFile)
                    elif extension == ".tgz" or extension == ".gz":
                        self.untgz(destFile)
                    elif extension == ".run" or extension == ".bin":
                        self.runInstaller(destFile)
            if line.startswith("exec_x86") and platform.architecture()[0] == "32bit":
                self.exe = line[str.index(line,"=")+1:].strip()
            if line.startswith("exec_x64") and platform.architecture()[0] == "64bit":
                self.exe = line[str.index(line,"=")+1:].strip()
            if line.startswith("platform"):
                self.platform = line[str.index(line,"=")+1:]
        installFile.close()
        
    def writeConfig(self):
        config_filename = self.lutrisConfigDir+"games/"+self.gameName+".conf"
        config_file = open(config_filename,"w")
        config_file.write("[main]\n")
        config_file.write("path = "+self.gameDir+"\n")
        if(self.exe != None):
            config_file.write("exe = "+self.exe+"\n")
        config_file.write("system = "+self.platform)
        config_file.close()
        
    def reporthook(self,arg1,bytes,totalSize):
        self.totalDownloaded = self.totalDownloaded + bytes
        print self.totalDownloaded / totalSize * 100.0
    
    def download(self,url):
        url = url.strip()
        filename = url.split("/")[-1]
        destFile = self.gamesDir+self.gameName+"/"+filename
        if url.startswith("file://"):
            shutil.copy(url[7:],self.gameDir)
        else:
            urllib.urlretrieve(url, destFile, self.reporthook)
        return destFile
    
    def unzip(self,file):
        subprocess.Popen(["unzip",file])
    
    def unrar(self,file):
        subprocess.Popen(["unrar","x",file])
        
    def untgz(self,file):
        subprocess.Popen(["tar","xzf",file])
        
    def runInstaller(self,file):
        subprocess.Popen(["chmod","+x",file])
        subprocess.Popen([file])

        
if __name__ == "__main__":
    quakeInstall = LutrisInstaller("hexen")