#!/usr/bin/python
# -*- coding:Utf-8 -*-
""" Module that actually runs the games. """
import os
import time
import shutil

from gi.repository import Gtk, GLib

from lutris import pga
from lutris.runners import import_runner
from lutris.util.log import logger
from lutris.util import audio
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread
from lutris.gui.dialogs import QuestionDialog, ErrorDialog

from lutris import desktop_control


def show_error_message(message):
    """ Display an error message based on the runner's output. """
    if "RUNNER_NOT_INSTALLED" == message['error']:
        ErrorDialog('Error the runner is not installed')
    elif "NO_BIOS" == message['error']:
        ErrorDialog("A bios file is required to run this game")
    elif "FILE_NOT_FOUND" == message['error']:
        ErrorDialog("The file %s could not be found" % message['file'])


def get_game_list(filter_installed=False):
    return [Game(game['slug']) for game in pga.get_games()]


class Game(object):
    """" This class takes cares about loading the configuration for a game
         and running it.
    """
    def __init__(self, slug):
        self.slug = slug
        self.game_thread = None
        self.heartbeat = None
        self.game_config = None

        game_data = pga.get_game_by_slug(slug)
        self.runner_name = game_data['runner']
        self.directory = game_data['directory']
        self.name = game_data['name']
        self.is_installed = bool(game_data['installed'])

        self.load_config()

    def get_runner(self):
        """ Return the runner's name """
        return self.game_config['runner']

    def load_config(self):
        """ Load the game's configuration. """
        self.game_config = LutrisConfig(game=self.slug)
        if self.is_installed:
            if not self.game_config.is_valid():
                logger.error("Invalid game config for %s" % self.slug)
            else:
                runner_class = import_runner(self.runner_name)
                self.runner = runner_class(self.game_config)

    def remove(self, from_library=False, from_disk=False):
        if from_disk:
            if os.path.exists(self.directory):
                shutil.rmtree(self.directory)
        if from_library:
            pga.delete_game(self.slug)
        else:
            pga.set_uninstalled(self.slug)
        self.game_config.remove()

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

        if hasattr(self.runner, 'prelaunch'):
            success = self.runner.prelaunch()
            return success
        return True

    def play(self):
        """ Launch the game. """
        if not self.prelaunch():
            return False
        gameplay_info = self.runner.play()
        logger.debug("Launching %s: %s" % (self.name, gameplay_info))
        if isinstance(gameplay_info, dict):
            if 'error' in gameplay_info:
                show_error_message(gameplay_info)
                return False
            launch_arguments = gameplay_info['command']
        else:
            logger.error("Old method used for returning gameplay infos")
            launch_arguments = gameplay_info

        resolution = self.game_config.get_system('resolution')
        if resolution:
            desktop_control.change_resolution(resolution)

        if self.game_config.get_system('reset_pulse'):
            desktop_control.reset_pulse()

        if self.game_config.get_system('hide_panels'):
            self.desktop.hide_panels()

        oss_wrapper = self.game_config.get_system("oss_wrapper")
        if oss_wrapper:
            launch_arguments.insert(0, audio.get_oss_wrapper(oss_wrapper))

        ld_preload = gameplay_info.get('ld_preload')
        if ld_preload:
            launch_arguments.insert(0, 'LD_PRELOAD="{}"'.format(ld_preload))

        ld_library_path = gameplay_info.get('ld_library_path')
        if ld_library_path:
            launch_arguments.insert(
                0, 'LD_LIBRARY_PATH="{}"'.format(ld_library_path)
            )

        killswitch = self.game_config.get_system('killswitch')
        self.heartbeat = GLib.timeout_add(5000, self.poke_process)
        self.game_thread = LutrisThread(" ".join(launch_arguments),
                                        path=self.runner.get_game_path(),
                                        killswitch=killswitch)
        if hasattr(self.runner, 'stop'):
            self.game_thread.set_stop_command(self.runner.stop)
        self.game_thread.start()
        if 'joy2key' in gameplay_info:
            self.joy2key(gameplay_info['joy2key'])
        xboxdrv_config = self.game_config.get_system('xboxdrv')
        if xboxdrv_config:
            self.xboxdrv(xboxdrv_config)

    def joy2key(self, config):
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
        joy2key_thread = LutrisThread(command)
        self.game_thread.attach_thread(joy2key_thread)
        joy2key_thread.start()

    def xboxdrv(self, config):
        command = ("pkexec xboxdrv --daemon --detach-kernel-driver "
                   "--dbus session --silent %s"
                   % config)
        logger.debug("xboxdrv command: %s", command)
        thread = LutrisThread(command)
        thread.start()

    def poke_process(self):
        """ Watch game's process. """
        if not self.game_thread.pid:
            self.quit_game()
            return False
        return True

    def quit_game(self):
        """ Quit the game and cleanup. """
        self.heartbeat = None
        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("game has quit at %s" % quit_time)

        if self.game_config.get_system('resolution'):
            desktop_control.reset_desktop()

        if self.game_config.get_system('xboxdrv'):
            logger.debug("Shutting down xboxdrv")
            os.system("pkexec xboxdrvctl --shutdown")

        if self.game_thread:
            self.game_thread.stop()
