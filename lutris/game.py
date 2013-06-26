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
""" Module that actually runs the games. """

import os
import sys
import time
import subprocess

from signal import SIGKILL
from os.path import join
from gi.repository import Gtk, GLib

from lutris.runners import import_runner
from lutris.util.log import logger
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread
from lutris.gui.dialogs import QuestionDialog, ErrorDialog
from lutris.settings import CONFIG_DIR
from lutris import pga
import lutris.desktop_control


class ConfigurationException(Exception):
    """ Dummy exception for bad config files """
    def __init__(self):
        super(ConfigurationException, self).__init__()


def show_error_message(message):
    """ Display an error message based on the runner's output. """
    if "RUNNER_NOT_INSTALLED" == message['error']:
        ErrorDialog('Error the runner is not installed')
    elif "NO_BIOS" == message['error']:
        ErrorDialog("A bios file is required to run this game")
    elif "FILE_NOT_FOUND" == message['error']:
        ErrorDialog("The file %s could not be found" % message['file'])


def get_list():
    """Get the list of all installed games"""
    game_list = []
    return pga.get_games()
    for filename in os.listdir(join(CONFIG_DIR, "games")):
        if filename.endswith(".yml"):
            game_name = filename[:len(filename) - 4]
            logger.info("Loading %s ...", game_name)
            try:
                game = LutrisGame(game_name)
            except ConfigurationException:
                message = "Error loading configuration for %s" % game_name

                #error_dialog = Gtk.MessageDialog(parent=None, flags=0,
                #                                 type=Gtk.MessageType.ERROR,
                #                                 buttons=Gtk.ButtonsType.OK,
                #                                 message_format=message)
                #error_dialog.run()
                #error_dialog.destroy()
                print(message)
            else:
                game_list.append({"name": game.get_real_name(),
                                  "runner": game.get_runner(),
                                  "id": game_name})
    return game_list


def reset_pulse():
    """ Reset pulseaudio. """
    pulse_reset = "pulseaudio --kill && sleep 1 && pulseaudio --start"
    subprocess.Popen(pulse_reset, shell=True)
    logger.debug("PulseAudio restarted")


def setup_padsp(setting, command):
    command = command.split()[0]
    if setting == 'padsp32':
        launch_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(launch_dir, 'padsp32')
    elif setting == 'padsp':
        return 'padsp'


class LutrisGame(object):
    """"This class takes cares about loading the configuration for a game
    and running it."""
    def __init__(self, name):
        self.name = name
        self.runner = None
        self.game_thread = None
        self.heartbeat = None
        self.game_config = None
        self.load_config()

    def get_real_name(self):
        """ Return the real game's name if available. """
        return self.game_config['realname'] \
            if "realname" in self.game_config.config else self.name

    def get_runner(self):
        """ Return the runner's name """
        return self.game_config['runner']

    def load_config(self):
        """ Load the game's configuration. """
        self.game_config = LutrisConfig(game=self.name)
        if not self.game_config.is_valid():
            logger.error("Invalid game config for %s" % self.name)
        else:
            runner_class = import_runner(self.get_runner())
            self.runner = runner_class(self.game_config)

    def prelaunch(self):
        """ Verify that the current game can be launched. """
        if not self.runner.is_installed():
            question = ("The required runner is not installed.\n"
                        "Do you wish to install it now ?")
            install_runner_dialog = QuestionDialog(
                {'question': question,
                 'title': "Required runner unavailable"})
            if Gtk.ResponseType.YES == install_runner_dialog.result:
                self.runner.install()
            return False
        return True

    def play(self):
        """ Launch the game. """
        if not self.prelaunch():
            return False
        logger.debug("get ready for %s " % self.get_real_name())
        gameplay_info = self.runner.play()
        logger.debug("gameplay_info: %s" % gameplay_info)
        if isinstance(gameplay_info, dict):
            if 'error' in gameplay_info:
                show_error_message(gameplay_info)
                return False
            game_run_args = gameplay_info["command"]
        else:
            logger.warning("Old method used for returning gameplay infos")
            game_run_args = gameplay_info

        resolution = self.game_config.get_system("resolution")
        if resolution:
            lutris.desktop_control.change_resolution(resolution)

        _reset_pulse = self.game_config.get_system("reset_pulse")
        if _reset_pulse:
            reset_pulse()

        hide_panels = self.game_config.get_system("hide_panels")
        if hide_panels:
            self.desktop.hide_panels()

        nodecoration = self.game_config.get_system("compiz_nodecoration")
        if nodecoration:
            lutris.desktop_control.set_compiz_nodecoration(title=nodecoration)

        fullscreen = self.game_config.get_system("compiz_fullscreen")
        if fullscreen:
            lutris.desktop_control.set_compiz_fullscreen(title=fullscreen)

        killswitch = self.game_config.get_system("killswitch")

        path = self.runner.get_game_path()
        command = " " . join(game_run_args)
        oss_wrapper = setup_padsp(self.game_config.get_system("oss_wrapper"),
                                  command)
        if oss_wrapper:
            command = oss_wrapper + " " + command

        self.heartbeat = GLib.timeout_add(5000, self.poke_process)
        logger.debug("Running : %s", command)
        self.game_thread = LutrisThread(command, path, killswitch)
        self.game_thread.start()
        if 'joy2key' in gameplay_info:
            self.run_joy2key(gameplay_info['joy2key'])

    def run_joy2key(self, config):
        """ Run a joy2key thread. """
        win = "grep %s" % config['window']
        if 'notwindow' in config:
            win = win + ' | grep -v %s' % config['notwindow']
        wid = "xwininfo -root -tree | %s | awk '{print $1}'" % win
        buttons = config['buttons']
        axis = "Left Right Up Down"
        rcfile = "~/.joy2keyrc"
        command = "sleep 5 "
        command += "&& joy2key $(%s) -X -rcfile %s -buttons %s -axis %s" % (
            wid, rcfile, buttons, axis
        )
        joy2key_thread = LutrisThread(command, "/tmp")
        self.game_thread.attach_thread(joy2key_thread)
        joy2key_thread.start()

    def poke_process(self):
        """ Watch game's process. """
        if not self.game_thread.pid:
            self.quit_game()
            return False
        else:
            return True

    def quit_game(self):
        """ Quit the game and cleanup. """
        self.heartbeat = None
        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("game has quit at %s" % quit_time)
        if self.game_thread is not None and self.game_thread.pid:
            for child in self.game_thread:
                child.kill()
            os.kill(self.game_thread.pid + 1, SIGKILL)
        if self.game_config.get_system('reset_desktop'):
            lutris.desktop_control.reset_desktop()
