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

from lutris.config_vbox import ConfigVBox
from lutris.desktop_control import LutrisDesktopControl

class SystemConfigVBox(ConfigVBox):
    """VBox for system configuration, to be inserted in main preferences, runner preferences
    and game preferences""" 
    
    def __init__(self,lutris_config):
        """VBox init"""
        ConfigVBox.__init__(self,"system")
        self.lutris_config = lutris_config
        self.lutris_config.config_type = "system"
        
        #TODO : Move the list of window manager somewhere else, in lutris_desktop_control for example.
        #TODO : Auto detect the installed WMs on the user's machine
        #TODO : If the user_wm has not yet been set, detect the WM currently running
        wm_list = [("Compiz","compiz"),("OpenBox","openbox"),("KWin","kwin"),
        ("Metacity","metacity"),("Metacity (Composited)","metacity_composited")]

        #TODO : Same thing for OSS Wrappers
        oss_list = [("None (don't use OSS)","none"),("aoss (OSS Wrapper for Alsa)","aoss"),("padsp (OSS Wrapper for PulseAudio)","padsp")]
        
        self.options = [{"option":"game_path","type":"directory_chooser","label":"Default game path"},
                        {"option":"user_wm","type":"one_choice","label":"Desktop Window Manager","choices":wm_list},
                        {"option":"game_wm","type":"one_choice","label":"Gaming Window Manager","choices":wm_list},
                        {"option":"oss_wrapper","type":"one_choice","label":"OSS Wrapper","choices":oss_list},
                        {"option":"reset_pulse","type":"bool","label":"Reset PulseAudio"},
                        {"option":"hide_panels","type":"bool","label":"Hide Gnome Panels"}]
        
        self.generate_widgets()
