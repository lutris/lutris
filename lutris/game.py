#!/usr/bin/python
# -*- coding:Utf-8 -*-
"""Module that actually runs the games."""
import os
import time

from gi.repository import GLib

from lutris import pga
from lutris import settings
from lutris.runners import import_runner, InvalidRunner
from lutris.util.log import logger
from lutris.util import audio, display, system
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread, HEARTBEAT_DELAY
from lutris.gui import dialogs


def show_error_message(message):
    """Display an error message based on the runner's output."""
    if "RUNNER_NOT_INSTALLED" == message['error']:
        dialogs.ErrorDialog('Error the runner is not installed')
    elif "NO_BIOS" == message['error']:
        dialogs.ErrorDialog("A bios file is required to run this game")
    elif "FILE_NOT_FOUND" == message['error']:
        dialogs.ErrorDialog("The file %s could not be found" % message['file'])
    elif "NOT_EXECUTABLE" == message['error']:
        dialogs.ErrorDialog("The file %s is not executable" % message['file'])


def get_game_list(filter_installed=False):
    return [Game(game['slug'])
            for game in pga.get_games(filter_installed=filter_installed)]


class Game(object):
    """This class takes cares about loading the configuration for a game
       and running it.
    """
    STATE_IDLE = 'idle'
    STATE_STOPPED = 'stopped'
    STATE_RUNNING = 'running'

    def __init__(self, slug):
        self.slug = slug
        self.runner = None
        self.game_thread = None
        self.heartbeat = None
        self.config = None
        self.killswitch = None
        self.state = self.STATE_IDLE
        self.game_log = ''

        game_data = pga.get_game_by_slug(slug)
        self.runner_name = game_data.get('runner') or ''
        self.directory = game_data.get('directory') or ''
        self.name = game_data.get('name') or ''
        self.is_installed = bool(game_data.get('installed')) or False
        self.year = game_data.get('year') or ''

        self.load_config()
        self.resolution_changed = False
        self.original_outputs = None

    def __repr__(self):
        return self.__unicode__()

    def __unicode__(self):
        value = self.name
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    def get_browse_dir(self):
        """Return the path to open with the Browse Files action."""
        return self.runner.browse_dir

    def load_config(self):
        """Load the game's configuration."""
        self.config = LutrisConfig(game=self.slug)
        if not self.is_installed:
            return
        if not self.runner_name:
            logger.error('Incomplete data for %s', self.slug)
            return
        try:
            runner_class = import_runner(self.runner_name)
        except InvalidRunner:
            logger.error("Unable to import runner %s for %s",
                         self.runner_name, self.slug)
        self.runner = runner_class(self.config)

    def remove(self, from_library=False, from_disk=False):
        if from_disk:
            self.runner.remove_game_data(game_path=self.directory)
        if from_library:
            pga.delete_game(self.slug)
            self.config.remove()
        else:
            pga.set_uninstalled(self.slug)

    def save(self):
        self.config.save()
        pga.add_or_update(
            name=self.name,
            runner=self.runner_name,
            slug=self.slug,
            directory=self.directory,
            installed=self.is_installed
        )

    def prelaunch(self):
        """Verify that the current game can be launched."""
        if not self.runner.is_installed():
            installed = self.runner.install_dialog()
            if not installed:
                return False

        if hasattr(self.runner, 'prelaunch'):
            return self.runner.prelaunch()
        return True

    def use_runtime(self, system_config):
        disable_runtime = system_config.get('disable_runtime')
        env_runtime = os.getenv('LUTRIS_RUNTIME')
        if env_runtime and env_runtime.lower() in ('0', 'off'):
            disable_runtime = True
        return not disable_runtime

    def play(self):
        """Launch the game."""
        if not self.runner:
            dialogs.ErrorDialog("Invalid game configuration: Missing runner")
            return False
        if not self.prelaunch():
            return False

        system_config = self.runner.system_config
        self.original_outputs = display.get_outputs()
        gameplay_info = self.runner.play()
        logger.debug("Launching %s: %s" % (self.name, gameplay_info))
        if 'error' in gameplay_info:
            show_error_message(gameplay_info)
            return False

        launch_arguments = gameplay_info['command']

        restrict_to_display = system_config.get('display')
        if restrict_to_display:
            display.turn_off_except(restrict_to_display)
            time.sleep(3)
            self.resolution_changed = True

        resolution = system_config.get('resolution')
        if resolution:
            display.change_resolution(resolution)
            time.sleep(3)
            self.resolution_changed = True

        if system_config.get('reset_pulse'):
            audio.reset_pulse()

        primusrun = system_config.get('primusrun')
        if primusrun and system.find_executable('primusrun'):
            launch_arguments.insert(0, 'primusrun')

        prefix_command = system_config.get("prefix_command", '').strip()
        if prefix_command:
            launch_arguments.insert(0, prefix_command)
        env = os.environ.copy()
        game_env = gameplay_info.get('env') or {}
        env.update(game_env)

        ld_preload = gameplay_info.get('ld_preload')
        if ld_preload:
            env["LD_PRELOAD"] = ld_preload

        ld_library_path = []
        if self.use_runtime(system_config):
            runtime64_path = os.path.join(settings.RUNTIME_DIR, "lib64")
            if os.path.exists(runtime64_path):
                ld_library_path.append(runtime64_path)
            runtime32_path = os.path.join(settings.RUNTIME_DIR, "lib32")
            if os.path.exists(runtime32_path):
                ld_library_path.append(runtime32_path)

        game_ld_libary_path = gameplay_info.get('ld_library_path')
        if game_ld_libary_path:
            ld_library_path.append(game_ld_libary_path)

        if ld_library_path:
            ld_full = ':'.join(ld_library_path)
            env["LD_LIBRARY_PATH"] = "{}:$LD_LIBRARY_PATH".format(ld_full)

        self.killswitch = system_config.get('killswitch')
        if self.killswitch and not os.path.exists(self.killswitch):
            # Prevent setting a killswitch to a file that doesn't exists
            self.killswitch = None

        self.game_thread = LutrisThread(launch_arguments,
                                        runner=self.runner, env=env,
                                        rootpid=gameplay_info.get('rootpid'))
        self.state = self.STATE_RUNNING
        if hasattr(self.runner, 'stop'):
            self.game_thread.set_stop_command(self.runner.stop)
        self.game_thread.start()
        if 'joy2key' in gameplay_info:
            self.joy2key(gameplay_info['joy2key'])
        xboxdrv_config = system_config.get('xboxdrv')
        if xboxdrv_config:
            self.xboxdrv_start(xboxdrv_config)
        if self.runner.is_watchable:
            # Create heartbeat every
            self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.beat)

    def joy2key(self, config):
        """Run a joy2key thread."""
        if not system.find_executable('joy2key'):
            logger.error("joy2key is not installed")
            return
        win = "grep %s" % config['window']
        if 'notwindow' in config:
            win += ' | grep -v %s' % config['notwindow']
        wid = "xwininfo -root -tree | %s | awk '{print $1}'" % win
        buttons = config['buttons']
        axis = "Left Right Up Down"
        rcfile = os.path.expanduser("~/.joy2keyrc")
        rc_option = '-rcfile %s' % rcfile if os.path.exists(rcfile) else ''
        command = "sleep 5 "
        command += "&& joy2key $(%s) -X %s -buttons %s -axis %s" % (
            wid, rc_option, buttons, axis
        )
        joy2key_thread = LutrisThread(command)
        self.game_thread.attach_thread(joy2key_thread)
        joy2key_thread.start()

    def xboxdrv_start(self, config):
        command = ("pkexec xboxdrv --daemon --detach-kernel-driver "
                   "--dbus session --silent %s"
                   % config)
        logger.debug("xboxdrv command: %s", command)
        self.xboxdrv_thread = LutrisThread(command)
        self.xboxdrv_thread.set_stop_command(self.xboxdrv_stop)
        self.xboxdrv_thread.start()

    def xboxdrv_stop(self):
        os.system("pkexec xboxdrvctl --shutdown")

    def beat(self):
        """Watch game's process."""
        killswitch_engage = self.killswitch and \
            not os.path.exists(self.killswitch)
        if not self.game_thread.is_running or killswitch_engage:
            self.on_game_quit()
            return False
        return True

    def stop(self):
        self.game_thread.stop(killall=True)

    def on_game_quit(self):
        """Restore some settings and cleanup after game quit."""
        self.heartbeat = None
        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("game has quit at %s" % quit_time)
        self.state = self.STATE_STOPPED
        self.game_log = self.game_thread.stdout
        if self.resolution_changed\
           or self.runner.system_config.get('reset_desktop'):
            display.change_resolution(self.original_outputs)

        if self.runner.system_config.get('restore_gamma'):
            display.restore_gamma()

        if self.runner.system_config.get('xboxdrv'):
            self.xboxdrv_thread.stop()

        if self.game_thread:
            self.game_thread.stop()
