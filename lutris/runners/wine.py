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

"""Wine runner"""

import os
import subprocess
import logging

from os.path import exists

from lutris.util.log import logger
from lutris.settings import CACHE_DIR
from lutris.runners.runner import Runner


def set_regedit(path, key, value):
    """Plays with the windows registry

    path is something like HKEY_CURRENT_USER\Software\Wine\Direct3D
    """

    logging.debug("Setting wine registry key : %s\\%s to %s",
                    path, key, value)
    reg_path = os.path.join(CACHE_DIR, 'winekeys.reg')
    #Make temporary reg file
    reg_file = open(reg_path, "w")
    reg_file.write("""REGEDIT4

[%s]
"%s"="%s"

""" % (path, key, value))
    reg_file.close()
    subprocess.call(["wine", "regedit", reg_path])
    os.remove(reg_path)


def create_prefix(*args, **kwargs):
    logger.debug("Creating prefix")
    print args
    print kwargs
    logger.debug("prefix created")


def installer(*args, **kwargs):
    print args
    print kwargs


def kill():
    """The kill command runs wineserver -k"""
    os.popen("winserver -k")


# pylint: disable=C0103
class wine(Runner):
    '''Run Windows games with Wine'''
    def __init__(self, settings=None):
        super(wine, self).__init__()
        self.executable = 'wine'
        self.machine = 'Windows games'
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
        self.settings = settings
        reg_prefix = "HKEY_CURRENT_USER\Software\Wine"
        self.reg_keys = {
            "RenderTargetLockMode": r"%s\Direct3D" % reg_prefix,
            "Audio": r"%s\Drivers" % reg_prefix,
            "MouseWarpOverride": r"%s\DirectInput" % reg_prefix,
            "Multisampling": r"%s\Direct3D" % reg_prefix,
            "OffscreenRenderingMode": r"%s\Direct3D" % reg_prefix,
            "DirectDrawRenderer": r"%s\Direct3D" % reg_prefix,
            "Version": r"%s" % reg_prefix,
            "Desktop": r"%s\Explorer" % reg_prefix
        }

    def get_install_command(self, exe=None):
        """Return the installer command, either from an exe or an iso"""
        if exe:
            command = "%s %s" % (self.executable, exe)
        else:
            print "Need an executable file"
            return False
        return command

    def check_regedit_keys(self, wine_config):
        """Resets regedit keys according to config"""
        for key in self.reg_keys.keys():
            if key in wine_config:
                set_regedit(self.reg_keys[key], key, wine_config[key])

    def play(self):
        settings = self.settings
        if 'exe' in settings['game']:
            game_exe = settings['game']['exe']
        if 'args' in settings.config['game']:
            arguments = settings['game']['args']
        else:
            arguments = None
        if self.__class__.__name__ in settings.config:
            logging.debug('loading wine specific settings')
            wine_config = settings.config[self.__class__.__name__]
        game_path = os.path.dirname(game_exe)
        game_exe = os.path.basename(game_exe)
        if not exists(game_path):
            return {"error": "FILE_NOT_FOUND", "file": game_path}
        command = []
        if "prefix" in wine_config and exists(wine_config['prefix']):
            logger.debug("using WINEPREFIX %s", wine_config["prefix"])
            command.append("WINEPREFIX=%s ", wine_config['prefix'])
        command.append(self.executable)
        command.append("\"" + game_exe + "\"")
        if arguments:
            for arg in arguments.split():
                command.append(arg)
        self.check_regedit_keys(wine_config)
        return {'command': command}
