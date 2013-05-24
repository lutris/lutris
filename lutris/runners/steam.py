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

        config = LutrisConfig(runner='steam')
        config.runner_config = {'system': {'game_path': dlg.folder}}
        config.save(config_type='runner')

    def is_installed(self):
        """Checks if wine is installed and if the steam executable is on the
        harddrive
        """
        if not self.check_depends() or not self.game_path:
            return False
        print self.game_path
        print self.executable
        exe_path = os.path.join(self.game_path, self.executable)
        return self.game_path and os.path.exists(exe_path)

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        game_list = []
        os.chdir(os.path.join(self.game_path, "appcache"))
        max_counter = 10010
        files = []
        counter = 0
        for filename in os.listdir("."):
            counter = counter + 1
            if counter < max_counter:
                files.append(filename)
            else:
                break

        steam_apps = []
        for filename in files:
            if filename.endswith(".vdf"):
                test_file = open(filename, "rb")
                appid = get_appid_from_filename(filename)
                appname = get_name(test_file)
                if appname:
                    steam_apps.append((appid, appname, filename))
                test_file.close()

        steam_apps.sort()
        steam_apps_file = open(
            os.path.join(os.path.expanduser("~"), "steamapps.txt"), "w"
        )
        for steam_app in steam_apps:
            #steam_apps_file.write("%d\t%s\n" % (steam_app[0],steam_app[1]))
            #print ("%d\t%s\n" % (steam_app[0],steam_app[1]))
            game_list.append((steam_app[0], steam_app[1]))
        steam_apps_file.close()
        return game_list

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
