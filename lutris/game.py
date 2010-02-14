import os
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



import subprocess
import gobject
import logging
import os,time
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread
from lutris.desktop_control import LutrisDesktopControl
from runners import *
from lutris.constants import *

class LutrisGame():
    """"This class takes cares about loading the configuration for a game
    and running it."""
    def __init__(self,name):
        self.name = name
        self.pid = 0
        self.runner = None
        self.subprocess = None
        self.game_thread = None
        self.lutris_desktop_control = LutrisDesktopControl()
        self.load_success = self.load_config()

    def load_config(self):
        #Load the game's configuration
        self.game_config = LutrisConfig(game=self.name)
        if "realname" in self.game_config.config:
            self.real_name = self.game_config["realname"]
        else: 
            self.real_name = self.name
        try:
            self.runner_name = self.game_config["runner"]
        except KeyError:
            print "Error in %s config file : No runner" % self.name
            return False           
        try:
            self.machine = eval(self.runner_name+"."+self.runner_name+"(self.game_config)")
        except AttributeError:
            print "Malformed configuration file : %s" % self.name
            return False
        return True
          
    def play(self):
        config = self.game_config.config
        self.hide_panels = False
        oss_wrapper = None
        if "system" in config and config["system"] is not None:
            if "hide_panels" in config["system"]:
                if config["system"]["hide_panels"]:
                    #Hide Gnome panels
                    self.lutris_desktop_control.hide_panels()
                    self.hide_panels = True
            if "resolution" in config["system"]:
                #Change resolution before starting game
                success = self.lutris_desktop_control.change_resolution(config["system"]["resolution"])
                if success:
                    logging.debug("Resolution changed to %s"% config["system"]["resolution"])
                else:
                    logging.debug("Failed to set resolution %s" % config["system"]["resolution"])
                    
            if "oss_wrapper" in config["system"]:
                oss_wrapper = config["system"]["oss_wrapper"]                
                
            if "reset_pulse" in config["system"]:
                if config["system"]["reset_pulse"]:
                    print "Restarting PulseAudio"
                    subprocess.Popen("pulseaudio --kill && sleep 1 && pulseaudio --start",shell = True)
                    print "PulseAudio restarted"
                    
        game_run_args = self.machine.play()

        path = None
        if hasattr(self.machine,"game_path"):
            path = self.machine.game_path

        command =  " ".join(game_run_args)
        #OSS Wrapper
        if oss_wrapper and oss_wrapper != "none":
            command = oss_wrapper + " " + command

        logging.debug(command)
        if game_run_args:
            self.timer_id = gobject.timeout_add(5000, self.poke_process)
            self.game_thread = LutrisThread(command,path)
            self.game_thread.start()
            
    def write_conf(self,settings):
        self.lutris_config.write_game_config(self.name,settings)

    def poke_process(self):
        if self.game_thread.pid:
            os.system("gnome-screensaver-command --poke")
        else:
            self.quit_game()
            return False
        return True

    def quit_game(self):
        logging.debug("game has quit at %s" % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime() ) )
        if self.game_thread is not None and self.game_thread.pid:
            if self.game_thread.cedega:
                for pid in self.game_thread.pid:
                    os.popen("kill -9 %s" % pid)
            else:
                self.game_thread.game_process.terminate()
        self.lutris_desktop_control.reset_desktop()
        pathname = os.path.dirname(sys.argv[0])
        os.chdir(os.path.abspath(pathname))