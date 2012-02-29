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

import os
import gtk

from lutris.gui.common import QuestionDialog, DirectoryDialog
from lutris.runners.wine import wine
from lutris.config import LutrisConfig

class steam(wine):
    """Runner for the Steam platform."""

    def __init__(self,settings=None):
        super(steam, self).__init__(settings)
        self.executable = "Steam.exe"
        self.package = None
        self.description = "Runs Steam games with Wine"
        self.machine = "Steam Platform"
        #TODO : Put Steam Path in config file
        config = LutrisConfig(runner=self.__class__.__name__)
        self.game_path = config.get_path()
        self.game_exe = "steam.exe"
        self.arguments = []
        self.depends = "wine"
        self.is_installable = False
        self.appid = "26800"
        self.game_options = [
                {'option': 'appid', 'type': 'string', 'label': 'appid'},
                {'option': 'args', 'type': 'string', 'label': 'arguments'}
        ]
        if settings:
            self.appid = settings['game']['appid']
            if 'args' in settings['game']:
                self.args = settings['game']['args']
            else:
                self.args = ""

    def install(self):
        q = QuestionDialog({
            'title': 'Installing Steam',
            'question': 'Do you already have Steam on your computer ?'
            })
        if q.result == gtk.RESPONSE_NO:
            print "!!! NOT IMPLEMENTED !!!"

        d = DirectoryDialog('Where is located Steam ?')

        config = LutrisConfig(runner='steam')
        config.runner_config = {'system': {'game_path': d.folder }}
        config.save(type='runner')

    def is_installed(self):
        """Checks if wine is installed and
        if the steam executable is on the harddrive

        """
        if not self.check_depends():
            return False
        if not self.game_path or \
           not os.path.exists(os.path.join(self.game_path, self.game_exe)):
            return False
        else:
            return True

    def get_name(self, steam_file):
        data = steam_file.read(1000)
        if "name" in data:
            index_of_name = str.find(data, "name")
            index = index_of_name + 5
            char = "0"
            name = ""
            while ord(char) != 0x0:
                char = data[index]
                index = index + 1
                name = name + char
            return name[:-1]

    def get_appid_from_filename(self, filename):
        if filename.endswith(".vdf"):
            appid = filename[filename.find("_") + 1:filename.find(".")]
        elif filename.endswith('.pkv'):
            appid = filename[:filename.find("_")]
        return  appid

    def get_appid_list(self):
        self.game_list = []
        os.chdir(os.path.join(self.game_path,"appcache"))
        max_counter = 10010
        files = []
        counter = 0
        for file in os.listdir("."):
            counter = counter + 1
            if counter < max_counter:
                files.append(file)
            else:
                break

        steam_apps = []
        for file in files:
            if file.endswith(".vdf"):
                test_file = open(file,"rb")
                appid = self.get_appid_from_filename(file)
                appname = self.get_name(test_file)
                if appname:
                    steam_apps.append((appid,appname,file))
                test_file.close()

        steam_apps.sort()
        steam_apps_file = open(
                os.path.join(os.path.expanduser("~"),"steamapps.txt"),"w"
            )
        for steam_app in steam_apps:
            #steam_apps_file.write("%d\t%s\n" % (steam_app[0],steam_app[1]))
            #print ("%d\t%s\n" % (steam_app[0],steam_app[1]))
            self.game_list.append((steam_app[0],steam_app[1]))
        steam_apps_file.close()

    def play(self):
        if not self.check_depends():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.depends }
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}

        self.check_regedit_keys() #From parent wine runner

        print self.game_path
        print self.game_exe
        steam_full_path = os.path.join(self.game_path, self.game_exe)
        command = ['wine', '"' + steam_full_path + '"', '-applaunch', self.appid, self.args]
        return {'command': command }

