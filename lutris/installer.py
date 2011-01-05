#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

""" This is where takes place the whole install process for games

TODO: The gui frontend
"""

import os
import yaml
import shutil
import urllib
import urllib2
import logging
import subprocess

import lutris.constants
from lutris.config import LutrisConfig

def unzip(filename, dest=None):
    """Unzips a file"""
    command = ["unzip", '-o', filename]
    if dest:
        command = command + ['-d', dest]
    subprocess.call(command)

def unrar(filename):
    """Unrar a file"""

    subprocess.call(["unrar", "x", filename])

def untgz(filename):
    """Untgz a file"""

    subprocess.call(["tar", "xzf", filename])

def run_installer(filename):
    """Run an installer of .sh or .run type"""

    subprocess.call(["chmod", "+x", filename])
    subprocess.call([filename])

def reporthook(piece, received_bytes, total_size):
    """Follows the progress of a download"""

    print "%d %%" % ((piece * received_bytes) * 100 / total_size)


class Installer():
    """ Lutris installer """

    def __init__(self, game):

        self.lutris_config = None
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
        self.games_dir = self.lutris_config.get_path()
        if not self.games_dir:
            self.installer_user_actions.append("ask_games_dir")
            logging.debug('Install dir missing')
            return False

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
            mappings = {'check_md5': self.check_md5,
                        'extract' : self._extract,
                        'move' : self._move,
                        'delete': self.delete,
                        'request_media': self._request_media,
                        'run': self._run}
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)
        self.write_config()

    def save_installer_content(self):
        """ Save the downloaded installer to disk. """

        full_url = lutris.constants.installer_prefix + self.game_name + '.yml'
        request = urllib2.Request(url=full_url)
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError:
            logging.debug("Server is unreachable")
            self.installer_errors.append("INSTALLER_UNREACHABLE")
            success = False
        else:
            logging.debug("downloading %s" % full_url)
            installer_file = open(self.installer_dest_path, "w")
            installer_file.write(response.read())
            installer_file.close()
            success = True

        return success

    def parseconfig(self):
        """ Reads the installer file. """

        self.install_data = yaml.load(file(self.installer_dest_path, 'r').read())

        #Checking protocol
        protocol_version = self.install_data['protocol']
        if protocol_version != lutris.constants.protocol_version:
            print("Wrong protocol version (Expected %d, got %d)" %
                  (lutris.constants.protocol_version, protocol_version))
            return False

        mandatory_fields = ['version', 'runner', 'name']
        optional_fields = ['exe', 'iso', 'rom']
        for field in mandatory_fields:
            self.game_info[field] = self.install_data[field]
        for field in optional_fields:
            if field in self.install_data:
                self.game_info[field] = self.install_data[field]
        files = self.install_data['files']

        for gamefile in files:
            file_id = gamefile.keys()[0]
            # if download link is a dict, it contains the url (in the
            # 'url' key) and ouput filename (in 'ouput')
            if type(gamefile[file_id]) == type(dict()):
                url = gamefile[file_id]['url']
                output = gamefile[file_id]['ouput']
            else:
                url = gamefile[file_id]
                output = None
            dest_path = self._download(url, output)
            self.gamefiles[file_id] = dest_path
        self.installer_actions = self.install_data['installer']
        self.lutris_config = LutrisConfig(runner=self.game_info['runner'])
        return True

    def write_config(self):
        """ Writes the game configration as a Lutris launcher. """
        config_filename = os.path.join(lutris.constants.GAME_CONFIG_PATH,
                                       self.game_name + ".yml")

        config_data = {'game': {},
                       'realname': self.game_info['name'],
                       'runner': self.game_info['runner']}
        launchers = ['exe', 'iso', 'rom']

        for launcher in launchers:
            if(launcher in self.game_info):
                config_data['game'][launcher] = os.path.join(self.game_dir,
                                                             self.game_info[launcher])

        yaml_config = yaml.dump(config_data, default_flow_style=False)
        file(config_filename, "w").write(yaml_config)

    def check_md5(self, data):
        """ Calculates the checksum of a file and validates it. """

        print 'checking md5 for file ' + self.gamefiles[data['file']]
        print 'expecting ' + data['value']
        print "NOT IMPLEMENTED"
        return True

    def _download(self, url, output=None):
        """ Downloads a file. """

        logging.debug('Downloading ' + url)
        dest_dir = os.path.join(lutris.constants.tmp_path, self.game_name)
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        if not output:
            output = url.split('/')[-1]
        dest_file = os.path.join(dest_dir, output)
        if os.path.exists(dest_file):
            return dest_file
        if url.startswith("file://"):
            shutil.copy(url[7:], dest_dir)
        else:
            urllib.urlretrieve(url, dest_file, reporthook)

        return dest_file

    def delete(self, data):
        """ Deletes a file """
        print "will delete " + self.gamefiles[data['file']]
        print "let's not delete anything right now, m'kay ?"

    def _extract(self, data):
        """ Extracts a file, guessing the compression method """

        print 'extracting ' + data['file']
        filename = self.gamefiles[data['file']]
        print "NOT IMPLEMENTED"
        extension = filename[filename.rfind(".") + 1:]

        if extension == "zip":
            unzip(filename, self.game_dir)

    def _move(self, data):
        """ Moves a file. """
        src = data['src']
        if src in self.gamefiles.keys():
            src = self.gamefiles[src]
        destination_alias = data['dst']
        if data['dst'] == 'gamedir':
            dst = self.game_dir
        else:
            dst = data['dst'].replace('homedir', os.path.expanduser('~'))
            if not os.path.exists(dst):
                dst = '/tmp'

        print "Moving %s to %s" % (src, dst)

        if not os.path.exists(src):
            print "I cannot move what does not exist"
            return False
        try:
            shutil.move(src, dst)
        except shutil.Error:
            print "Could not move the file, destination already exists ?"
            return False
        return True

    def _request_media(self, data):
        if 'default' in data:
            path = data['default']
        if os.path.exists(os.path.join(path, data['contains'])):
            return True
        else:
            return False
    def _run(self, data):
        exec_path = os.path.join(lutris.constants.TMP_PATH, self.game_name,
                                 self.gamefiles[data['file']])
        os.popen('chmod +x %s' % exec_path)
        subprocess.call([exec_path])


