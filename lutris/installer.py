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

""" Here is your docstring ... """

import os
import yaml
import shutil
import urllib
import urllib2
import logging
import subprocess

import lutris.constants
from lutris.config import LutrisConfig

def unzip(filename):
    """Unzips a file"""

    subprocess.Popen(["_unzip", 'o', filename])

def unrar(filename):
    """Unrar a file"""

    subprocess.Popen(["_unrar", "x", filename])

def untgz(filename):
    """Untgz a file"""

    subprocess.Popen(["tar", "xzf", filename])

def run_installer(filename):
    """Run an installer of .sh or .run type"""

    subprocess.Popen(["chmod", "+x", filename])
    subprocess.Popen([filename])

def reporthook(arg1, received_bytes, total_size):
    """Follows the progress of a download"""
    print "What is this ? : %d " % arg1
    print "received_bytes : %d " % received_bytes
    print "total_size : %d" % total_size

def check_md5(data):
    """ Calculates the checksum of a file and validates it. """

    print 'checking md5 for file ' + self.gamefiles[data['file']]
    print 'expecting ' + data['value']
    print "NOT IMPLEMENTED"
    return True

class Installer():
    """ Lutris installer """

    def __init__(self, game):

        self.lutris_config = LutrisConfig()
        self.game_name = game
        self.installer_dest_path = os.path.join(lutris.constants.cache_path,
                                                self.game_name + ".yml")
        # Stores a list of actions that will be sent back to the user 
        # in order to complete the installation
        self.installer_user_actions = []

        # Actions that the installer has to run 
        # in order to complete the install.
        self.installer_actions = []

        # List of errors that occurred while installing the game
        self.installer_errors = []

        # ???
        self.install_data = []

        # Essential game information to create Lutris launcher
        self.game_info = {}

        # Dictionary of the files needed to install the game
        self.gamefiles = {}


    def set_games_dir(self, path):
        """ Set the base path where the game will be installed """

        self.games_dir = path

    def pre_install(self):
        """Reads the installer and checks everything is OK 
        before beginning the install process
        """

        success = self.save_installer_content()
        if not success:
            return False
        success = self.parseconfig()
        self.games_dir = self.lutris_config.get_path(
                                            runner=self.game_info['runner'])
        if not self.games_dir:
            self.installer_user_actions.append("ask_games_dir")

        self.game_dir = os.path.join(self.games_dir, self.game_name)
        if not os.path.exists(self.game_dir):
            os.mkdir(self.game_dir)

        return success

    def install(self):
        """ Runs the actions to complete the install. """

        os.chdir(self.game_dir)

        for action in self.installer_actions:
            action_name = action.keys()[0]
            action_data = action[action_name]
            mappings = {
                'check_md5': check_md5,
                'extract' : self._extract,
                'move' : self._move
            }
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)

        self.write_config()

    def save_installer_content(self):
        """ Save the downloaded installer to disk. """

        print 'downloading installer for ' + self.game_name

        full_url = lutris.constants.installer_prefix + self.game_name + '.yml'
        request = urllib2.Request(url=full_url)
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError:
            print "Server is unreachable"
            self.installer_errors.append("SERVER_UNREACHABLE")
            success = False
        else:
            installer_file = open(self.installer_dest_path, "w")
            installer_file.write(response.read())
            installer_file.close()
            success = True
        finally:
            return success

    def parseconfig(self):
        """ Reads the installer file. """

        self.install_data = yaml.load(file(self.installer_dest_path,
                                           'r').read())

        #Checking protocol
        protocol_version = self.install_data['protocol']
        if protocol_version != lutris.constants.protocol_version:
            print("Wrong protocol version (Expected %d, got %d)" %
                  (lutris.constants.protocol_version, protocol_version))
            return False

        #Script version
        self.game_info['version'] = self.install_data['version']
        #Runner
        self.game_info['runner'] = self.install_data['runner']
        #Name
        self.game_info['name'] = self.install_data['name']
        files = self.install_data['files']

        for gamefile in files:
            file_id = gamefile.keys()[0]
            dest_path = self._download(gamefile[file_id])
            self.gamefiles[file_id] = dest_path
        self.installer_actions = self.install_data['installer']

    def write_config(self):
        """ Writes the game configration as a Lutris launcher. """
        config_filename = os.path.join(lutris.constants.lutris_config_path, "games",
                                       self.game_name + ".conf")
        config_file = open(config_filename, "w")
        config_file.write("[main]\n")
        config_file.write("path = " + self.game_dir + "\n")
        if('exe' in self.game_info):
            config_file.write("exe = " + self.game_info['exe'] + "\n")
        config_file.write("runner = " + self.game_info['runner'])
        config_file.close()



    def _download(self, url):
        """ Downloads a file. """

        logging.debug('Downloading ' + url)
        dest_dir = os.path.join(lutris.constants.tmp_path, self.game_name)
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        dest_file = os.path.join(dest_dir, url.split("/")[-1])
        if os.path.exists(dest_file):
            return dest_file
        if url.startswith("file://"):
            shutil.copy(url[7:], self.game_dir)
        else:
            urllib.urlretrieve(url, dest_file, reporthook)
        return dest_file



    def _extract(self, data):
        """ Extracts a file, guessing the compression method """

        print 'extracting ' + data['file']
        filename = self.gamefiles[data['file']]
        print "NOT IMPLEMENTED"
        extension = filename[filename.rfind(".") + 1:]

        if extension == "zip":
            unzip(filename)

    def _move(self, data):
        """ Moves a file. """
        src = data['src']
        destination_alias = data['dst']
        if destination_alias == 'gamedir':
            dst = self.game_dir
        else:
            dst = '/tmp'

        print "Moving %s to %s" % (src, dst)

        try:
            shutil.move(src, dst)
        except ValueError:
            print "Could not move the file, destination already exists ?"

