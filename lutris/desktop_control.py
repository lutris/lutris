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

"""Class to control the user's desktop in many aspects

This class interacts with the window manager, xrandr, gconf, ...
"""

import os.path

from subprocess import Popen, PIPE

from lutris.gconf import GConfSetting
from lutris.util.log import logger


def make_compiz_rule(class_=None, title=None):
    """Return a string formated for the Window Rules plugin"""
    if class_ is not None:
        rule = 'class=%s' % class_
    elif title is not None:
        rule = 'title=%s' % title
    else:
        rule = False
    return rule


def get_resolutions():
    """Return the list of supported screen resolutions."""
    xrandr_output = Popen("xrandr",
                          stdout=PIPE, stderr=PIPE).communicate()[0]
    resolution_list = []
    for line in xrandr_output.split("\n"):
        if line.startswith("  "):
            resolution_list.append(line.split()[0])
    return resolution_list


def get_current_resolution():
    """Return the current resolution for the desktop."""
    xrandr_output = Popen("xrandr", stdout=PIPE).communicate()[0]
    for line in xrandr_output.split("\n"):
        if line.startswith("  ") and "*" in line:
            return line.split()[0]
    return None


def change_resolution(resolution):
    """change desktop resolution"""
    if resolution not in get_resolutions():
        logger.warning("Resolution %s doesn't exist.")
    else:
        Popen("xrandr -s %s" % resolution, shell=True)


def check_joysticks():
    """Return list of connected joysticks."""
    number_joysticks = 0
    joysticks = []
    for device_number in range(0, 8):
        device_name = "/dev/input/js%d" % device_number
        if os.path.exists(device_name):
            number_joysticks = number_joysticks + 1
            joysticks.append(device_name)
    return joysticks


class LutrisDesktopControl():
    """
    Change some settings in gconf that are useful to provide a good gaming
    experience """
    def __init__(self):
        self.default_resolution = None
        self.panels_hidden = False

    def set_compiz_fullscreen(self, class_=None, title=None):
        """Set a fullscreen rule for the plugin Window Rules"""
        rule = make_compiz_rule(class_, title)
        if not rule:
            return False
        compiz_root = "/apps/compiz/plugins"
        key = compiz_root + "/winrules/screen0/options/fullscreen_match"
        setting = GConfSetting(key, bool)
        setting.set_value(rule)
        return True

    def set_compiz_nodecoration(self, class_=None, title=None):
        """Remove the decorations for the game's window"""
        window_rule = make_compiz_rule(class_, title)
        if not window_rule:
            return False
        rule = "(any) & !(%s)" % window_rule
        compiz_root = "/apps/compiz/plugins"
        key = compiz_root + "/decoration/allscreens/options/decoration_match"
        setting = GConfSetting(key, bool)
        setting.set_value(rule)
        return True

    def set_keyboard_repeat(self, value=False):
        """Desactivate key repeats.

        This is needed, for example, in Wolfenstein (2009)
        """
        key = "/desktop/gnome/peripherals/keyboard/repeat"
        setting = GConfSetting(key, bool)
        setting.set_key(key, value)
        return True

    def reset_desktop(self):
        """Restore the desktop to its original state."""
        #Restore panels
        self.hide_panels(False)
        #Restore resolution
        if self.default_resolution is None:
            os.popen("xrandr -s 0")
        else:
            os.popen("xrandr -s %s" % self.default_resolution)
        #Restore gamma
        os.popen("xgamma -gamma 1.0")
