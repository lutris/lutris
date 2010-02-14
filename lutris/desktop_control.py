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
import subprocess
import logging
#Dumb Debian Lenny,they don't even have python-gconf !
try:
    import gconf
    gconf_capable = True
except ImportError:
    gconf_capable = False

class LutrisDesktopControl():
    """
    Change some settings in gconf that are useful to provide a good gaming experience
    """
    def __init__(self):
        self.default_resolution = None
        if gconf_capable:
            self.gconf_path = os.path.join(os.path.expanduser("~"),".gconf")
            self.client = gconf.client_get_default ()
        
    def set_keyboard_repeat(self, gconf_value = False):
        """
        Desactivate key repeats, this is needed in Wolfenstein (2009) for example
        """
        gconf_key = "/desktop/gnome/peripherals/keyboard/repeat"
        type= "Boolean"
        self.change_gconf_key(gconf_key,type,gconf_value)
        
    def hide_panels(self, hide = True):
        """
        Hide any panel that exists on the Gnome desktop
        This is useful because some games, mainly with Wine
        don't hide the panels in fullscreen.
        """
        base_dir = "/apps/panel/toplevels/"
        panels = self.all_dirs(base_dir)
        for panel in panels:
            if hide:
                print "Hiding %s" % panel
            else:
                print "Showing %s" % panel
            gconf_key = base_dir+panel+"/auto_hide"
            self.change_gconf_key(gconf_key,"boolean",hide)

    def change_gconf_key(self,gconf_key,gconf_type,gconf_value):
        if not hasattr(self,"client"):
            return
        if gconf_type.lower() == "string":
            self.client.set_string(gconf_key,gconf_value)
        if gconf_type.lower() == "boolean" or gconf_type.lower() == "bool":
            self.client.set_bool(gconf_key,gconf_value)

    def get_gconf_key(self,type,gconf_key):
        if not hasattr(self,"client"):
            return
        if type == "boolean":
            return self.client.get_bool(gconf_key)
        if type == "string":
            return self.client.get_string(gconf_key)

    def all_dirs(self,base_dir):
        """The same thing as gconftool --all-dirs <dir>"""
        
        if base_dir[0] =="/":
            base_dir = base_dir[1:]
        path = os.path.join(self.gconf_path, base_dir)
        dirs = os.listdir(path)
        dirs.remove("%gconf.xml")
        return dirs
    
    def change_resolution(self,resolution):
        """change desktop resolution"""
        if resolution not in self.get_resolutions():
            return False
        subprocess.Popen("xrandr -s %s" % resolution,shell = True).communicate()[0]
        return True

    def get_resolutions(self):
        xrandr_output = subprocess.Popen("xrandr",stdout=subprocess.PIPE).communicate()[0]
        resolution_list = []
        for line in xrandr_output.split("\n"):
            if line.startswith("  "):
                resolution_list.append(line.split()[0])
        return resolution_list

    def get_current_resolution(self):
        xrandr_output = subprocess.Popen("xrandr",stdout=subprocess.PIPE).communicate()[0]
        for line in xrandr_output.split("\n"):
            if line.startswith("  ") and "*" in line:
                return line.split()[0]
        return None

    def reset_desktop(self):
        #Restore panels
        #FIXME : Restore only with panels where shown before starting game
        self.hide_panels(False)

        #Restore resolution
        if self.default_resolution is None:
            os.popen("xrandr -s 1")
            os.popen("xrandr -s 0")
        else:
            os.popen("xrandr -s 1")
            os.popen("xrandr -s %s" % self.default_resolution)

        #Restore gamma
        os.popen("xgamma -gamma 1.0")
        

        
        