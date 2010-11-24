# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009, 2010 Mathieu Comandon strycore@gmail.com
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

"""Class to control the user's desktop in many aspects

This class interacts with the window manager, xrandr, gconf, ...
"""

import os
import os.path
from subprocess import Popen, PIPE

# Don't force to import gconf, some users might not have it.
try:
    import gconf
    GCONF_CAPABLE = True
except ImportError:
    GCONF_CAPABLE = False

from lutris.gconfwrapper import GconfWrapper

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
                          stdout=PIPE).communicate()[0]
    resolution_list = []
    for line in xrandr_output.split("\n"):
        if line.startswith("  "):
            resolution_list.append(line.split()[0])
    return resolution_list

def get_current_resolution():
    """Return the current resolution for the desktop."""
    xrandr_output = Popen("xrandr", 
                          stdout=PIPE).communicate()[0]
    for line in xrandr_output.split("\n"):
        if line.startswith("  ") and "*" in line:
            return line.split()[0]
    return None

def change_resolution(resolution):
    """change desktop resolution"""
    if resolution not in get_resolutions():
        return False
    Popen("xrandr -s %s" % resolution, 
          shell=True).communicate()[0]
    return True

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
    Change some settings in gconf that are useful to provide a good gaming experience
    """
    def __init__(self):
        self.default_resolution = None
        self.gconf = GconfWrapper()
        if GCONF_CAPABLE:
            self.gconf_path = os.path.join(os.path.expanduser("~"), ".gconf")
            self.client = gconf.client_get_default ()

    ### Compiz ###

    def set_compiz_fullscreen(self, class_=None, title=None):
        """Set a fullscreen rule for the plugin Window Rules"""
        rule = make_compiz_rule(class_, title)
        if rule is False:
            return False
        compiz_root = "/apps/compiz/plugins"
        key = compiz_root + "/winrules/screen0/options/fullscreen_match"
        self.gconf.set_key(key, rule, True)
        return True

    def set_compiz_nodecoration(self, class_=None, title=None):
        """Remove the decorations for the game's window"""
        window_rule = make_compiz_rule(class_, title)
        if window_rule is False:
            return False
        rule = "(any) & !(%s)" % window_rule
        compiz_root = "/apps/compiz/plugins"
        key = compiz_root + "/decoration/allscreens/options/decoration_match"
        self.gconf.set_key(key, rule, True)
        return True

    ### Gnome ###

    def hide_panels(self, hide = True):
        """
        Hide any panel that exists on the Gnome desktop.

        This is useful with some games, mostly running with Wine,
        won't hide the panels in fullscreen mode.
        """
        base_dir = "/apps/panel/toplevels/"
        panels = self.all_dirs(base_dir)
        for panel in panels:
            if hide:
                print "Hiding %s" % panel
            else:
                print "Showing %s" % panel
            gconf_key = base_dir + panel + "/auto_hide"
            self.change_gconf_key(gconf_key, "boolean", hide)

    def set_keyboard_repeat(self, gconf_value = False):
        """Desactivate key repeats.
        
        This is needed, for example in Wolfenstein (2009)
        """
        gconf_key = "/desktop/gnome/peripherals/keyboard/repeat"
        key_type = "Boolean"
        self.change_gconf_key(gconf_key, key_type, gconf_value)

    ### Gconf ###

    def change_gconf_key(self, gconf_key, gconf_type, gconf_value):
        """Change the value of a Gconf key."""
        if not hasattr(self, "client"):
            return
        if gconf_type.lower() == "string":
            self.client.set_string(gconf_key, gconf_value)
        if gconf_type.lower() == "boolean" or gconf_type.lower() == "bool":
            self.client.set_bool(gconf_key, gconf_value)

    def get_gconf_key(self, key_type, gconf_key):
        """Return the value of a Gconf key."""
        if not hasattr(self, "client"):
            return
        if key_type == "boolean":
            return self.client.get_bool(gconf_key)
        if key_type == "string":
            return self.client.get_string(gconf_key)

    def all_dirs(self, base_dir):
        """Equivalent to gconftool --all-dirs <dir>"""
        if base_dir[0] == "/":
            base_dir = base_dir[1:]
        path = os.path.join(self.gconf_path, base_dir)
        dirs = os.listdir(path)
        dirs.remove("%gconf.xml")
        return dirs

    ### Misc ###

    def reset_desktop(self):
        """Restore the desktop to its original state."""
        #Restore panels
        self.hide_panels(False)

        #Restore resolution
        if self.default_resolution is None:
            #os.popen("xrandr -s 1")
            os.popen("xrandr -s 0")
        else:
            #os.popen("xrandr -s 1")
            os.popen("xrandr -s %s" % self.default_resolution)

        #Restore gamma
        os.popen("xgamma -gamma 1.0")

