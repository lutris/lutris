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
from gi.repository import Gtk

from lutris.gui.dialogs import QuestionDialog, DirectoryDialog
from lutris.runners.wine import wine
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


# pylint: disable=C0103
class steam(wine):
    """Runs Steam games with Wine"""
    def __init__(self, settings=None):
        super(steam, self).__init__(settings)
        self.executable = "Steam.exe"
        self.platform = "Steam (Windows)"
        config = LutrisConfig(runner=self.__class__.__name__)
        self.game_path = config.get_path()
        self.arguments = []
        self.game_options = [
            {'option': 'appid', 'type': 'string', 'label': 'appid'},
            {'option': 'args', 'type': 'string', 'label': 'arguments'}
        ]
        self.settings = settings

    def install(self):
        dlg = QuestionDialog({
            'title': 'Installing Steam',
            'question': 'Do you already have Steam on your computer ?'
        })
        if dlg.result == Gtk.ResponseType.NO:
            return

        dlg = DirectoryDialog('Where is located Steam ?')
        self.game_path = dlg.folder
        config = LutrisConfig(runner='steam')
        config.runner_config = {'system': {'game_path': self.game_path}}
        config.save(config_type='runner')

    def is_installed(self):
        """Checks if wine is installed and if the steam executable is on the
        harddrive
        """
        if not self.check_depends() or not self.game_path:
            return False
        exe_path = os.path.join(self.game_path, self.executable)
        return self.game_path and os.path.exists(exe_path)

    def get_steam_config(self):
        if not self.game_path:
            self.install()
        config_filename = os.path.join(self.game_path, "config/config.vdf")
        with open(config_filename, "r") as steam_config_file:
            config = vdf_parse(steam_config_file, {})
        return config["InstallConfigStore"]["Software"]["Valve"]["Steam"]

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        config = self.get_steam_config()
        apps = config["apps"]
        return apps.keys()

    def get_game_data_path(self, appid):
        steam_config = self.get_steam_config()
        game_config = steam_config["apps"].get(appid)
        if not game_config:
            return False
        if game_config.get('HasAllLocalContent'):
            installdir = game_config['installdir'].replace("\\\\", "/")[2:]
            if os.path.exists(installdir):
                return installdir
        return False

    def install_game(self, appid):
        #print "Q2", apps["2320"]
        #print "Shadow", apps["238070"]
        subprocess.call(
            ["wine", '"%s"' % os.path.join(self.game_path, self.executable),
             "-no-drwite", "steam://install/%s" % appid]
        )

    def play(self):
        appid = self.settings['game']['appid']
        if 'args' in self.settings['game']:
            self.args = self.settings['game']['args']
        else:
            self.args = ""
        if not self.check_depends():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.depends}
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}

        steam_full_path = os.path.join(self.game_path, self.executable)
        command = ['wine', '"%s"' % steam_full_path, '-no-dwrite',
                   '-applaunch', appid, self.args]
        return {'command': command}
