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

"""Runner for the Steam platform"""
import os
import subprocess

from gi.repository import Gdk

from lutris.gui.dialogs import DirectoryDialog
from lutris.runners.wine import wine
from lutris.util.log import logger
from lutris.util import system
from lutris.config import LutrisConfig


def get_name(steam_file):
    """Get game name from some weird steam file"""
    data = steam_file.read(1000)
    if "name" in data:
        index_of_name = str.find(data, "name")
        index = index_of_name + 5
        char = "0"
        name = ""
        while ord(char) != 0x0:
            char = data[index]
            index += 1
            name = name + char
        return name[:-1]


def get_appid_from_filename(filename):
    """Get appid name from some weird steam file"""
    if filename.endswith(".vdf"):
        appid = filename[filename.find("_") + 1:filename.find(".")]
    elif filename.endswith('.pkv'):
        appid = filename[:filename.find("_")]
    else:
        raise ValueError("Bad filename")
    return appid


def vdf_parse(steam_config_file, config):
    line = " "
    while line:
        line = steam_config_file.readline()
        if not line or line.strip() == "}":
            return config
        line_elements = line.strip().split("\"")
        if len(line_elements) == 3:
            key = line_elements[1]
            steam_config_file.readline()  # skip '{'
            config[key] = vdf_parse(steam_config_file, {})
        else:
            config[line_elements[1]] = line_elements[3]
    return config


def is_running():
    return bool(system.get_pid('Steam.exe'))


def shutdown():
    """ Shutdown Steam in a clean way.
        TODO: Detect wine binary
    """
    pid = system.get_pid('Steam.exe')
    if not pid:
        return False
    cwd = system.get_cwd(pid)
    cmdline = system.get_command_line(pid)
    steam_exe = os.path.join(cwd, cmdline)
    system.execute(['wine', steam_exe, '-shutdown'])


def kill():
    system.kill_pid(system.get_pid('Steam.exe'))


# pylint: disable=C0103
class winesteam(wine):

    #installer_url = "http://cdn.steampowered.com/download/SteamInstall.msi"
    installer_url = "http://lutris.net/files/runners/SteamInstall.msi"

    """Runs Steam games with Wine"""
    def __init__(self, settings=None):
        super(winesteam, self).__init__(settings)
        self.executable = "Steam.exe"
        self.platform = "Steam (Windows)"
        config = LutrisConfig(runner=self.__class__.__name__)
        self.game_path = config.get_path()
        self.arguments = []
        self.game_options = [
            {'option': 'appid', 'type': 'string', 'label': 'appid'},
            {'option': 'args', 'type': 'string', 'label': 'arguments'},
            {'option': 'prefix', 'type': 'directory_chooser',
             'label': 'Prefix'}
        ]
        self.settings = settings

    def install(self, installer_path=None):
        if installer_path:
            self.msi_exec(installer_path, quiet=True)
        Gdk.threads_enter()
        dlg = DirectoryDialog('Where is located Steam ?')
        self.game_path = dlg.folder
        Gdk.threads_leave()
        config = LutrisConfig(runner='winesteam')
        config.runner_config = {'system': {'game_path': self.game_path}}
        config.save(config_type='runner')

    def is_installed(self):
        """ Checks if wine is installed and if the steam executable is on the
            harddrive.
        """
        if not self.check_depends() or not self.game_path:
            return False
        exe_path = os.path.join(self.game_path, self.executable)
        return self.game_path and os.path.exists(exe_path)

    @property
    def launch_args(self):
        return [self.get_wine_path(),
                '%s' % os.path.join(self.game_path, self.executable),
                '-no-dwrite']

    def get_steam_config(self):
        config_filename = os.path.join(self.game_path, 'config/config.vdf')
        if not os.path.exists(config_filename):
            return
        with open(config_filename, "r") as steam_config_file:
            config = vdf_parse(steam_config_file, {})
        return config['InstallConfigStore']['Software']['Valve']['Steam']

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        config = self.get_steam_config()
        if config:
            apps = config['apps']
            return apps.keys()

    def get_game_data_path(self, appid):
        steam_config = self.get_steam_config()
        if not steam_config:
            return False
        game_config = steam_config["apps"].get(appid)
        if not game_config:
            return False
        if game_config.get('HasAllLocalContent'):
            installdir = game_config['installdir'].replace("\\\\", "/")
            logger.debug("Raw installdir %s" % installdir)
            if installdir.startswith('C'):
                logger.debug("Inside wineprefix")
                installdir = os.path.join(os.path.expanduser('~'),
                                          '.wine/drive_c',
                                          installdir[3:])
            else:
                installdir = installdir[2:]
            logger.debug("Steam game found at %s" % installdir)
            if os.path.exists(installdir):
                return installdir
            elif os.path.exists(installdir.replace('steamapps', 'SteamApps')):
                return installdir.replace('steamapps', 'SteamApps')
            else:
                logger.debug("Path %s not found" % installdir)
        return False

    def install_game(self, appid):
        subprocess.Popen(self.launch_args + ["steam://install/%s" % appid])

    def validate_game(self, appid):
        subprocess.Popen(self.launch_args + ["steam://validate/%s" % appid])

    def play(self):
        appid = self.settings['game']['appid']
        if 'args' in self.settings['game']:
            self.args = self.settings['game']['args']
        else:
            self.args = ""
        logger.debug("Checking Steam installation")
        if not self.check_depends():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.depends}
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        self.prepare_launch()
        command = []
        prefix = self.settings['game'].get('prefix', "")
        if os.path.exists(prefix):
            command.append("WINEPREFIX=\"%s\" " % prefix)
        command += self.launch_args
        return {
            'command': command + ['-applaunch', appid, self.args]
        }
