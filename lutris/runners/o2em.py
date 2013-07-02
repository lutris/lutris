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

""" Runner for Odyssey2 games """

from lutris.runners.runner import Runner
import os.path


# pylint: disable=C0103
class o2em(Runner):
    """Magnavox Oyssey² Emulator"""

    def __init__(self, settings=None):
        """Constructor"""
        super(o2em, self).__init__()
        self.package = "o2em"
        self.executable = "o2em"
        self.platform = "Odyssey 2"
        #o2em is not yet available as a package  in Debian and Ubuntu,
        #it requires some packaging
        self.bios_path = os.path.join(os.path.expanduser("~"), ".o2em/bios/")

        bios_choices = [
            ("Odyssey² bios", "o2rom"),
            ("French odyssey² Bios", "c52"),
            ("VP+ Bios", "g7400"),
            ("French VP+ Bios", "jopac")
        ]
        controller_choices = [
            ("Disable", "0"),
            ("Arrows keys and right shift", "1"),
            ("W,S,A,D,SPACE", "2"),
            ("Joystick", "3")
        ]
        self.game_options = [{
            "option": "rom",
            "type": "file_chooser",
            "label": "Rom File"
        }]
        self.runner_options = [
            {
                "option": "bios",
                "type": "one_choice",
                "choices": bios_choices,
                "label": "Bios"
            },
            {
                "option": "first_controller",
                "type": "one_choice",
                "choices": controller_choices,
                "label": "First controller"
            },
            {
                "option": "second_controller",
                "type": "one_choice",
                "choices": controller_choices,
                "label": "Second controller"
            },
            {
                "option": "fullscreen",
                "type": "bool",
                "label": "Fullscreen"
            },
            {
                "option": "scanlines",
                "type": "bool",
                "label": "Scanlines"
            }
        ]

        self.arguments = ["-biosdir=\"%s\"" % self.bios_path]
        if settings:
            if "fullscreen" in settings["o2em"]:
                if settings["o2em"]["fullscreen"]:
                    self.arguments = self.arguments + ["-fullscreen"]
            if "scanlines" in settings["o2em"]:
                if settings["o2em"]["scanlines"]:
                    self.arguments = self.arguments + ["-scanlines"]
            if "first_controller" in settings["o2em"]:
                self.arguments += ["-s1=%s" %
                                   settings["o2em"]["first_controller"]]
            if "second_controller" in settings["o2em"]:
                self.arguments += ["-s2=%s" %
                                   settings["o2em"]["second_controller"]]
            romdir = os.path.dirname(settings["game"]["rom"])
            romfile = os.path.basename(settings["game"]["rom"])
            self.arguments = self.arguments + ["-romdir=\"%s\"/" % romdir]
            self.arguments = self.arguments + ["\"%s\"" % romfile]

    def play(self):
        """Run Odyssey 2 game"""
        command = [self.executable] + self.arguments
        return {'command': command}
