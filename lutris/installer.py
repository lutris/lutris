import os
import logging
import urllib
import urllib2
import subprocess
import shutil
import yaml
import platform
from lutris.config import LutrisConfig
import lutris.constants
from distutils.command.install_data import install_data

class Installer():
    def __init__(self, game):
        self.supported_protocol_version = 1

        self.lutris_config = LutrisConfig()
        self.website_url = lutris.constants.installer_prefix
        self.installer_cache = lutris.constants.cache_path
        self.gameName = game
        self.game_info = {}
        #FIXME : The thing that should not be
        self.gamesDir = "/media/seagate300/games/"
        self.gameDir = os.path.join(self.gamesDir, self.gameName)
        if not os.path.exists(self.gameDir):
            os.mkdir(self.gameDir)
        self.lutrisConfigDir = lutris.constants.lutris_config_path
        self.installer_dest_path = os.path.join(self.installer_cache, self.gameName + ".yml")
        #WTF ?
        self.totalDownloaded = 0

    def install(self):
        self.save_installer_content()
        success = self.parseconfig()
        if success:
            self.writeConfig()
        else:
            print "Installer failed"

    def save_installer_content(self):
        print 'downloading installer for ' + self.gameName
        full_url = self.website_url + self.gameName + '.yml'
        request = urllib2.Request(url = full_url)
        f = urllib2.urlopen(request)

        installer_file = open(self.installer_dest_path, "w")
        installer_file.write(f.read())
        installer_file.close()
        #TODO : Check size

    def parseconfig(self):
        self.install_data = yaml.load(file(self.installer_dest_path, 'r').read())

        #Checking protocol
        protocol_version = self.install_data['protocol']
        if protocol_version != self.supported_protocol_version:
            print "Wrong protocol version (Expected %d, got %d)" % (self.supported_protocol_version, protocol_version)
            return False

        #Script version
        self.game_info['version'] = self.install_data['version']
        #Runner
        self.game_info['runner'] = self.install_data['runner']
        #Name
        self.game_info['name'] = self.install_data['name']
        files = self.install_data['files']
        self.gamefiles = {}
        for gamefile in files:
            file_id = gamefile.keys()[0]
            dest_path = self.download(gamefile[file_id])
            self.gamefiles[file_id] = dest_path
        installer_actions = self.install_data['installer']

        #FIXME ?
        os.chdir(self.gameDir)

        for action in installer_actions:
            action_name = action.keys()[0]
            action_data = action[action_name]
            mappings = {
                'check_md5': self.check_md5,
                'extract' : self.extract,
                'move' : self.move
            }
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)
#                    
#                    extIndex = 
#                    extension = destFile[destFile.rfind("."):]
#                    if extension == ".zip":
#                        self.unzip(destFile)
#                    elif extension == ".rar":
#                        self.unrar(destFile)
#                    elif extension == ".tgz" or extension == ".gz":
#                        self.untgz(destFile)
#                    elif extension == ".run" or extension == ".bin":
#                        self.runInstaller(destFile)
        #=======================================================================
        # if line.startswith("exec_x86") and platform.architecture()[0] == "32bit":
        #    self.game_info['exe'] = line[str.index(line, ":") + 1:].strip()
        # if line.startswith("exec_x64") and platform.architecture()[0] == "64bit":
        #    self.exe = line[str.index(line, ":") + 1:].strip()
        # if line.startswith('runner'):
        #    self.game_info['runner'] = line[str.index(line, ":") + 1:]
        #=======================================================================

    def writeConfig(self):
        config_filename = os.path.join(self.lutrisConfigDir, "games" , self.gameName + ".conf")
        config_file = open(config_filename, "w")
        config_file.write("[main]\n")
        config_file.write("path = " + self.gameDir + "\n")
        if('exe' in self.game_info):
            config_file.write("exe = " + self.game_info['exe'] + "\n")
        config_file.write("runner = " + self.game_info['runner'])
        config_file.close()

    def reporthook(self, arg1, bytes, totalSize):
        self.totalDownloaded = self.totalDownloaded + bytes
        print self.totalDownloaded / totalSize * 100.0

    def download(self, url):
        logging.debug('Downloading ' + url)
        destFile = os.path.join(self.gamesDir, self.gameName, url.split("/")[-1])
        if os.path.exists(destFile):
            return destFile
        if url.startswith("file://"):
            shutil.copy(url[7:], self.gameDir)
        else:
            urllib.urlretrieve(url, destFile, self.reporthook)
        return destFile

    def check_md5(self, data):
        print 'checking md5 for file ' + self.gamefiles[data['file']]
        print 'expecting ' + data['value']
        print "NOT IMPLEMENTED"
        return True

    def extract(self, data):
        print 'extracting ' + data['file']
        filename = self.gamefiles[data['file']]
        print "NOT IMPLEMENTED"
        extension = filename[filename.rfind(".") + 1:]

        if extension == "zip":
            self.unzip(filename)

    def move(self, data):
        src = data['src']
        destination_alias = data['dst']
        if destination_alias == 'gamedir':
            dst = self.gameDir;
        else:
            dst = '/tmp'
        print "Moving %s to %s" % (src, dst)
        shutil.move(src, dst)

    def unzip(self, file):
        subprocess.Popen(["unzip", file])

    def unrar(self, file):
        subprocess.Popen(["unrar", "x", file])

    def untgz(self, file):
        subprocess.Popen(["tar", "xzf", file])

    def runInstaller(self, file):
        subprocess.Popen(["chmod", "+x", file])
        subprocess.Popen([file])


if __name__ == "__main__":
    quakeInstall = LutrisInstaller("quake")
    quakeInstall.install()
