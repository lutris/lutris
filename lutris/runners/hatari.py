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

""" Runner for Atari ST computers """

from lutris.runners.runner import Runner
import os


# pylint: disable=C0103
class hatari(Runner):
    '''Atari ST computers'''
    def __init__(self, settings=None):
        '''Constructor'''
        super(hatari, self).__init__()
        self.package = "hatari"
        self.executable = "hatari"
        self.machine = "Atari ST computers"
        self.settings = settings
        self.game_options = [
            {"option": "disk-a", "type":"single", "label": "Floppy Disk A"},
            {"option": "disk-b", "type":"single", "label": "Floppy Disk B"}
        ]
        joystick_choices = [
            ('None', 'none'),
            ('Keyboard', 'keys'),
            ('Joystick', 'real')
        ]

        self.runner_options = [
            {
                "option": "bios_file",
                "type":"file_chooser",
                "label": "Bios File (TOS.img)"
            },
            {
                "option": "fullscreen",
                "type":"bool",
                "label": "Fullscreen"
            },
            {
                "option": "zoom",
                "type": "bool",
                "label": "Double ST low resolution"
            },
            {
                "option": "borders",
                "type": "bool",
                'label': 'Add borders to display'
            },
            {
                "option": "status",
                "type": "bool",
                'label': 'Display status bar'
            },
            {
                "option": "joy1",
                "type": "one_choice",
                "label": "Joystick 1",
                "choices": joystick_choices
            },
            {
                "option": "joy2",
                "type": "one_choice",
                "label": "Joystick 2",
                "choices": joystick_choices
            }
        ]

    def play(self):
        settings = self.settings['hatari']
        game_settings = self.settings['game']
        if "fullscreen" in settings and settings["fullscreen"]:
            self.arguments = self.arguments + ["--fullscreen"]
        else:
            self.arguments = self.arguments + ["--window"]

        if "zoom" in settings and settings["zoom"]:
            self.arguments = self.arguments + ["--zoom 2"]
        else:
            self.arguments = self.arguments + ["--zoom 1"]

        if 'borders' in settings and settings["borders"]:
            self.arguments = self.arguments + ['--borders true']
        else:
            self.arguments = self.arguments + ['--borders false']

        if 'status' in settings and settings["status"]:
            self.arguments = self.arguments + ['--statusbar true']
        else:
            self.arguments = self.arguments + ['--statusbar false']
        if "joy1" in settings:
            self.arguments = self.arguments + ["--joy0 " + settings['joy1']]
        if "joy2" in settings:
            self.arguments = self.arguments + ["--joy1 " + settings['joy2']]

        if "bios_file" in settings:
            if os.path.exists(settings['bios_file']):
                self.arguments = self.arguments +\
                    ["--tos " + settings["bios_file"]]
            else:
                return {
                    'error': 'FILE_NOT_FOUND',
                    'file': settings['bios_file']
                }
        else:
            return {'error': 'NO_BIOS'}
        if "disk-a" in game_settings:
            diska = game_settings['disk-a']
        self.arguments = self.arguments + ["--disk-a \"%s\"" % diska]
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}
        if not os.path.exists(diska):
            return {'error': 'FILE_NOT_FOUND', 'file': diska}
        command = [self.executable] + self.arguments

        return {"command": command}
