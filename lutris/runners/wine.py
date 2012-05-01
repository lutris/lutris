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

import os
import subprocess
import logging

from os.path import exists

from lutris.runners.runner import Runner
from lutris.constants import TMP_PATH
from lutris.settings import CACHE_DIR


class wine(Runner):
    def __init__(self, settings=None):
        self.executable = 'wine'
        self.package = 'wine'
        self.machine = 'Windows games'
        self.description = 'Run Windows games with Wine'

        self.prefix = None

        self.is_installable = True

        self.installer_options = [{
            'option': 'installer',
            'type': 'single',
            'label': 'Executable'
        }]
        self.game_options = [
            {
                'option': 'exe',
                'type': 'single',
                'label': 'Executable'
            },
            {
                'option': 'args',
                'type': 'string',
                'label': 'Arguments'
            },
            {
                'option': 'prefix',
                'type': 'directory_chooser',
                'label': 'Prefix'
            }
        ]

        mouse_warp_choices = [('Disable', 'disable'),
                              ('Enable', 'enable'),
                              ('Force', 'force')]
        orm_choices = [('BackBuffer', 'backbuffer'),
                       ('FBO', 'fbo'),
                       ('PBuffer', 'pbuffer')]
        rtlm_choices = [('Auto', 'auto'),
                        ('Disabled', 'disabled'),
                        ('ReadDraw', 'readdraw'),
                        ('ReadTex', 'readtex'),
                        ('TexDraw', 'texdraw'),
                        ('TexTex', 'textex')]
        multisampling_choices = [('Enabled', 'enabled'),
                                 ("Disabled", "disabled")]
        audio_choices = [('Alsa', 'alsa'),
                         ('OSS', 'oss'),
                         ('Jack', 'jack')]
        desktop_choices = [('Yes', 'Default'),
                           ('No', 'None')]
        self.runner_options = [
            {'option': 'cdrom_path',
            'label': 'CDRom mount point',
            'type': 'directory_chooser'},
            {'option': 'MouseWarpOverride',
            'label': 'Mouse Warp Override',
            'type': 'one_choice',
            'choices': mouse_warp_choices},
            {'option': 'Multisampling',
            'label': 'Multisampling',
            'type': 'one_choice',
            'choices': multisampling_choices},
            {'option': 'OffscreenRenderingMode',
            'label': 'Offscreen Rendering Mode',
            'type': 'one_choice',
            'choices': orm_choices},
            {'option': 'RenderTargetLockMode',
            'label': 'Render Target Lock Mode',
            'type': 'one_choice',
            'choices': rtlm_choices},
            {'option': 'Audio',
            'label': 'Audio driver',
            'type': 'one_choice',
            'choices': audio_choices},
            {'option': 'Desktop',
            'label': 'Virtual desktop',
            'type': 'one_choice',
            'choices': desktop_choices}
        ]

        reg_prefix = "HKEY_CURRENT_USER\Software\Wine"
        self.reg_keys = {
            "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
            "Audio": r"%s\Drivers" % reg_prefix,
            "MouseWarpOverride": r"%s\DirectInput" % reg_prefix,
            "Multisampling": r"%s\Direct3D" % reg_prefix,
            "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
            "OffscreenRenderingMode": r"%s\Direct3D" % reg_prefix,
            "DirectDrawRenderer": r"%s\Direct3D" % reg_prefix,
            "Version": r"%s" % reg_prefix,
            "Desktop": r"%s\Explorer" % reg_prefix
        }

        if settings:
            if 'exe' in settings['game']:
                self.gameExe = settings['game']['exe']
            if 'args' in settings.config['game']:
                self.args = settings['game']['args']
            else:
                self.args = None
            if self.__class__.__name__ in settings.config:
                logging.debug('loading wine specific settings')
                self.wine_config = settings.config[self.__class__.__name__]
            else:
                self.wine_config = None

    def set_regedit(self, path, key, value):
        """Plays with the windows registry

        path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
        """

        logging.debug("Setting wine registry key : %s\\%s to %s" %
                      (path, key, value))
        reg_path = os.path.join(TMP_PATH, 'winekeys.reg')
        #Make temporary reg file
        reg_file = open(reg_path, "w")
        reg_file.write("""REGEDIT4

[%s]
"%s"="%s"

""" % (path, key, value))
        reg_file.close()
        subprocess.call(["wine", "regedit", reg_path])
        os.remove(reg_path)

    def kill(self):
        """The kill command runs wineserver -k"""
        os.popen("winserver -k")

    def get_install_command(self, exe=None, iso=None):
        """Return the installer command, either from an exe or an iso"""
        if exe:
            command = "%s %s" % (self.executable, exe)
        else:
            print "Need an executable file"
            return False
        return command

    def check_regedit_keys(self):
        for key in self.reg_keys.keys():
            if key in self.wine_config:
                self.set_regedit(self.reg_keys[key], key,
                                 self.wine_config[key])

    def play(self):
        self.game_path = os.path.dirname(self.gameExe)
        game_exe = os.path.basename(self.gameExe)
        if not exists(self.game_path):
            return {"error": "FILE_NOT_FOUND", "file": self.game_path}
        command = []
        if self.prefix and exists(self.prefix):
            command.append("WINEPREFIX=%s ", self.prefix)
        command.append(self.executable)
        command.append("\"" + game_exe + "\"")
        if self.args:
            for arg in self.args.split():
                command.append(arg)
        self.check_regedit_keys()
        return {'command': command}
