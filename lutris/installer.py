import os
import logging
import urllib
import urllib2
import subprocess
import shutil
import time
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

        mandatory_fields = ['version', 'runner', 'name']
        optional_fields = ['exe']
        for field in mandatory_fields:
            self.game_info[field] = self.install_data[field]
        for field in optional_fields:
            if field in self.install_data:
                self.game_info[field] = self.install_data[field]
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
                'move' : self.move,
                'delete': self.delete
            }
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)
        return True
    def writeConfig(self):
        config_filename = os.path.join(self.lutrisConfigDir,
                "games" , self.game_info['runner'] + "-" + self.gameName + ".yml")
        config_file = open(config_filename, "w")
        config_data = {
                'game': {},
                'realname': self.game_info['name'],
                'runner': self.game_info['runner']
        }

        if('exe' in self.game_info):
            config_data['game']['exe'] = os.path.join(self.gameDir, self.game_info['exe'])
            
        yaml_config = yaml.dump(config_data, default_flow_style=False)
        file(config_filename, "w").write(yaml_config)

    def reporthook(self, arg1, bytes, totalSize):
        self.totalDownloaded = self.totalDownloaded + bytes
        #print self.totalDownloaded / totalSize * 100.0

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
        src = os.path.join(self.gameDir, data['src'])
        if not os.path.exists(src):
            time.sleep(1)
        if not os.path.exists(src):
            return False
        destination_alias = data['dst']
        if destination_alias == 'gamedir':
            dst = self.gameDir;
        else:
            dst = '/tmp'
        print "Moving %s to %s" % (src, dst)
        shutil.move(src, dst)

    def unzip(self, file):
        subprocess.call(["unzip", '-o', '-qq', file])

    def unrar(self, file):
        subprocess.Popen(["unrar", "x", file])

    def untgz(self, file):
        subprocess.Popen(["tar", "xzf", file])

    def runInstaller(self, file):
        subprocess.Popen(["chmod", "+x", file])
        subprocess.Popen([file])
    def delete(self, data):
        print "let's not delete anything right now, m'kay ?"

if __name__ == "__main__":
    quakeInstall = LutrisInstaller("quake")
    quakeInstall.install()
