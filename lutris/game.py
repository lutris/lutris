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

import subprocess
import gobject
import os
import os.path
import time
import gtk
from signal import SIGKILL

from lutris.runners import import_runner
from lutris.util.log import logger
from lutris.gui.common import QuestionDialog, ErrorDialog
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread
from lutris.desktop_control import LutrisDesktopControl, change_resolution
from lutris.constants import *


def show_error_message(message, info=None):
    if "RUNNER_NOT_INSTALLED" == message['error']:
        q = QuestionDialog({'title': 'Error the runner is not installed',
            'question': '%s is not installed, \
                    do you want to install it now ?' % message['runner']})
        if gtk.RESPONSE_YES == q.result:
            # FIXME : This is not right at all!
            # Call the runner's install method
            subprocess.Popen(['software-center', message['runner']])
    elif "NO_BIOS" == message['error']:
        ErrorDialog("A bios file is required to run this game")
    elif "FILE_NOT_FOUND" == message['error']:
        ErrorDialog("The file %s doesn't exists" % message['file'])


def get_list():
    """Get the list of all installed games"""
    game_list = []
    for filename in os.listdir(GAME_CONFIG_PATH):
        if filename.endswith(CONFIG_EXTENSION):
            game_name = filename[:len(filename) - len(CONFIG_EXTENSION)]
            print "Loading %s ..." % game_name
            Game = LutrisGame(game_name)
            if not Game.load_success:
                message = "Error loading configuration for %s" % game_name

                #error_dialog = gtk.MessageDialog(parent=None, flags=0,
                #                                 type=gtk.MESSAGE_ERROR,
                #                                 buttons=gtk.BUTTONS_OK,
                #                                 message_format=message)
                #error_dialog.run()
                #error_dialog.destroy()
                print message
            else:
                game_list.append({"name": Game.real_name,
                                  "runner": Game.runner_name,
                                  "id": game_name})
    return game_list


class LutrisGame(object):
    """"This class takes cares about loading the configuration for a game
    and running it."""
    def __init__(self, name):
        self.name = name
        self.pid = 0
        self.runner = None
        self.subprocess = None
        self.game_thread = None
        self.desktop = LutrisDesktopControl()
        self.load_success = self.load_config()

    def load_config(self):
        """
        Load the game's configuration.
        """
        self.game_config = LutrisConfig(game=self.name)
        if self.game_config.is_valid():
            self.runner_name = self.game_config["runner"]
            if "realname" in self.game_config.config:
                self.real_name = self.game_config["realname"]
            else:
                self.real_name = self.name
        else:
            return False

        try:
            runner_module = __import__("lutris.runners.%s" % self.runner_name,
                    globals(), locals(),
                    [self.runner_name], -1)
            runner_cls = getattr(runner_module, self.runner_name)
            self.machine = runner_cls(self.game_config)
        except ImportError, msg:
            logger.error("Invalid runner %s" % self.runner_name)
            logger.error(msg)
        except AttributeError, msg:
            logger.error("Invalid configuration file (Attribute Error) : %s"\
                         % self.name)
            logger.error(msg)
            return False
        except KeyError, msg:
            logger.error("Invalid configuration file (Key Error) : %s"\
                         % self.name)
            logger.error(msg)
            return False
        return True

    def play(self):
        if not self.machine.is_installed():
            question = "The required runner is not installed,\
                        do you wish to install it now ?"
            install_runner_dialog = QuestionDialog({'question': question,
                'title': "Required runner unavailable"})
            if gtk.RESPONSE_YES == install_runner_dialog.result:
                runner_class = import_runner(self.runner_name)
                runner = runner_class()
                runner.install()
            return False
        config = self.game_config.config
        logger.debug("get ready for %s " % config['realname'])
        self.hide_panels = False
        oss_wrapper = None
        gameplay_info = self.machine.play()

        if type(gameplay_info) == dict:
            if 'error' in gameplay_info:
                show_error_message(gameplay_info)
                return False
            game_run_args = gameplay_info["command"]
        else:
            game_run_args = gameplay_info
            logger.debug("Old method used for returning gameplay infos")

        if "system" in config and config["system"] is not None:
            #Hide Gnome panels
            if "hide_panels" in config["system"]:
                if config["system"]["hide_panels"]:
                    self.desktop.hide_panels()
                    self.hide_panels = True

            #Change resolution before starting game
            if "resolution" in config["system"]:
                success = change_resolution(config["system"]["resolution"])
                if success:
                    logger.debug("Resolution changed to %s"
                            % config["system"]["resolution"])
                else:
                    logger.debug("Failed to set resolution %s"
                            % config["system"]["resolution"])

                    #Setting OSS Wrapper
            if "oss_wrapper" in config["system"]:
                oss_wrapper = config["system"]["oss_wrapper"]

            #Reset Pulse Audio
            if "reset_pulse" in config["system"] and config["system"]["reset_pulse"]:
                subprocess.Popen("pulseaudio --kill && sleep 1 && pulseaudio --start",
                                 shell=True)
                logger.debug("PulseAudio restarted")

            # Set compiz fullscreen windows
            # TODO : Check that compiz is running
            if "compiz_nodecoration" in config['system']:
                self.desktop.set_compiz_nodecoration(title=config['system']['compiz_nodecoration'])
            if "compiz_fullscreen" in config['system']:
                self.desktop.set_compiz_fullscreen(title=config['system']['compiz_fullscreen'])

            if "killswitch" in config['system']:
                killswitch = config['system']['killswitch']
            else:
                killswitch = None

        if hasattr(self.machine, 'game_path'):
            path = self.machine.game_path
        else:
            path = None

        #print game_run_args
        command = " " . join(game_run_args)
        # Set OSS Wrapper
        if oss_wrapper and oss_wrapper != 'none':
            command = oss_wrapper + " " + command

        if game_run_args:
            self.timer_id = gobject.timeout_add(5000, self.poke_process)
            logger.debug("Running : " + command)
            self.game_thread = LutrisThread(command, path, killswitch)
            self.game_thread.start()
            if 'joy2key' in gameplay_info:
                self.run_joy2key(gameplay_info['joy2key'])

    def run_joy2key(self, config):
        win = "grep %s" % config['window']
        if 'notwindow' in config:
            win = win + ' | grep -v %s' % config['notwindow']
        wid = "xwininfo -root -tree | %s | awk '{print $1}'" % win
        buttons = config['buttons']
        axis = "Left Right Up Down"
        command = "sleep 5 && joy2key $(%s) -X -rcfile ~/.joy2keyrc -buttons %s -axis %s" % (
                wid, buttons, axis
                )
        self.joy2key_thread = LutrisThread(command, "/tmp")
        self.joy2key_thread.start()

    def write_conf(self, settings):
        self.lutris_config.write_game_config(self.name, settings)

    def poke_process(self):
        if not self.game_thread.pid:
            self.quit_game()
            return False
        else:
            return True

    def quit_game(self):
        self.timer_id = None
        logger.debug("game has quit at %s" % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime()))
        if self.game_thread is not None and self.game_thread.pid:
            os.kill(self.game_thread.pid + 1, SIGKILL)
        if 'reset_desktop' in self.game_config.config['system']:
            if self.game_config.config['system']['reset_desktop']:
                self.desktop.reset_desktop()
