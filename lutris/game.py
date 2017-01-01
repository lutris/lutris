# -*- coding: utf-8 -*-
"""Module that actually runs the games."""
import os
import time
import subprocess

from gi.repository import GLib

from lutris import pga, shortcuts
from lutris import runtime
from lutris.runners import import_runner, InvalidRunner
from lutris.util import audio, display, jobs, system, strings
from lutris.util.log import logger
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread, HEARTBEAT_DELAY
from lutris.gui import dialogs


def show_error_message(message):
    """Display an error message based on the runner's output."""
    if "CUSTOM" == message['error']:
        message_text = message['file'].replace('&', '&amp;')
        dialogs.ErrorDialog(message_text)
    elif "RUNNER_NOT_INSTALLED" == message['error']:
        dialogs.ErrorDialog('Error the runner is not installed')
    elif "NO_BIOS" == message['error']:
        dialogs.ErrorDialog("A bios file is required to run this game")
    elif "FILE_NOT_FOUND" == message['error']:
        filename = message['file']
        if filename:
            message_text = "The file {} could not be found".format(
                filename.replace('&', '&amp;')
            )
        else:
            message_text = "No file provided"
        dialogs.ErrorDialog(message_text)

    elif "NOT_EXECUTABLE" == message['error']:
        message_text = message['file'].replace('&', '&amp;')
        dialogs.ErrorDialog("The file %s is not executable" % message_text)


class Game(object):
    """This class takes cares of loading the configuration for a game
       and running it.
    """
    STATE_IDLE = 'idle'
    STATE_STOPPED = 'stopped'
    STATE_RUNNING = 'running'

    def __init__(self, id=None):
        self.id = id
        self.runner = None
        self.game_thread = None
        self.heartbeat = None
        self.config = None
        self.killswitch = None
        self.state = self.STATE_IDLE
        self.game_log = ''
        self.exit_main_loop = False

        game_data = pga.get_game_by_field(id, 'id')
        self.slug = game_data.get('slug') or ''
        self.runner_name = game_data.get('runner') or ''
        self.directory = game_data.get('directory') or ''
        self.name = game_data.get('name') or ''
        self.is_installed = bool(game_data.get('installed')) or False
        self.year = game_data.get('year') or ''
        self.game_config_id = game_data.get('configpath') or ''
        self.steamid = game_data.get('steamid') or ''
        self.has_custom_banner = bool(game_data.get('has_custom_banner')) or False
        self.has_custom_icon = bool(game_data.get('has_custom_icon')) or False

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
        self.config = LutrisConfig(runner_slug=self.runner_name,
                                   game_config_id=self.game_config_id)
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
        else:
            self.runner = runner_class(self.config)

    def remove(self, from_library=False, from_disk=False):
        if from_disk and self.runner:
            logger.debug("Removing game %s from disk" % self.id)
            self.runner.remove_game_data(game_path=self.directory)

        # Do not keep multiple copies of the same game
        existing_games = pga.get_game_by_field(self.slug, 'slug', all=True)
        if len(existing_games) > 1:
            from_library = True

        if from_library:
            logger.debug("Removing game %s from library" % self.id)
            pga.delete_game(self.id)
        else:
            pga.set_uninstalled(self.id)
        self.config.remove()
        shortcuts.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        return from_library

    def save(self):
        self.config.save()
        self.id = pga.add_or_update(
            name=self.name,
            runner=self.runner_name,
            slug=self.slug,
            directory=self.directory,
            installed=self.is_installed,
            configpath=self.config.game_config_id,
            steamid=self.steamid,
            id=self.id
        )

    def prelaunch(self):
        """Verify that the current game can be launched."""
        if not self.runner.is_installed():
            installed = self.runner.install_dialog()
            if not installed:
                return False

        if self.runner.use_runtime():
            runtime_updater = runtime.RuntimeUpdater()
            if runtime_updater.is_updating():
                logger.warning("Runtime updates: {}".format(
                    runtime_updater.current_updates)
                )
                dialogs.ErrorDialog("Runtime currently updating",
                                    "Game might not work as expected")
        return True

    def play(self):
        """Launch the game."""
        if not self.runner:
            dialogs.ErrorDialog("Invalid game configuration: Missing runner")
            self.state = self.STATE_STOPPED
            return

        if not self.prelaunch():
            self.state = self.STATE_STOPPED
            return

        if hasattr(self.runner, 'prelaunch'):
            jobs.AsyncCall(self.runner.prelaunch, self.do_play)
        else:
            self.do_play(True)

    def do_play(self, prelaunched, _error=None):
        if not prelaunched:
            self.state = self.STATE_STOPPED
            return
        system_config = self.runner.system_config
        self.original_outputs = display.get_outputs()
        gameplay_info = self.runner.play()

        env = {}

        logger.debug("Launching %s: %s" % (self.name, gameplay_info))
        if 'error' in gameplay_info:
            show_error_message(gameplay_info)
            self.state = self.STATE_STOPPED
            return

        sdl_video_fullscreen = system_config.get('sdl_video_fullscreen') or ''
        env['SDL_VIDEO_FULLSCREEN_DISPLAY'] = sdl_video_fullscreen

        restrict_to_display = system_config.get('display')
        if restrict_to_display != 'off':
            display.turn_off_except(restrict_to_display)
            time.sleep(3)
            self.resolution_changed = True

        resolution = system_config.get('resolution')
        if resolution != 'off':
            display.change_resolution(resolution)
            time.sleep(3)
            self.resolution_changed = True

        if system_config.get('reset_pulse'):
            audio.reset_pulse()

        self.killswitch = system_config.get('killswitch')
        if self.killswitch and not os.path.exists(self.killswitch):
            # Prevent setting a killswitch to a file that doesn't exists
            self.killswitch = None

        # Command
        launch_arguments = gameplay_info['command']

        primusrun = system_config.get('primusrun')
        if primusrun and system.find_executable('primusrun'):
            launch_arguments.insert(0, 'primusrun')

        xephyr = system_config.get('xephyr') or 'off'
        if xephyr != 'off':
            if xephyr == '8bpp':
                xephyr_depth = '8'
            else:
                xephyr_depth = '16'
            xephyr_resolution = system_config.get('xephyr_resolution') or '640x480'
            xephyr_command = ['Xephyr', ':2', '-ac', '-screen',
                              xephyr_resolution + 'x' + xephyr_depth, '-glamor',
                              '-reset', '-terminate', '-fullscreen']
            xephyr_thread = LutrisThread(xephyr_command)
            xephyr_thread.start()
            time.sleep(3)
            env['DISPLAY'] = ':2'

        if system_config.get('use_us_layout'):
            setxkbmap_command = ['setxkbmap', '-model', 'pc101', 'us', '-print']
            xkbcomp_command = ['xkbcomp', '-', os.environ.get('DISPLAY', ':0')]
            xkbcomp = subprocess.Popen(xkbcomp_command, stdin=subprocess.PIPE)
            subprocess.Popen(setxkbmap_command,
                             env=os.environ,
                             stdout=xkbcomp.stdin).communicate()
            xkbcomp.communicate()

        pulse_latency = system_config.get('pulse_latency')
        if pulse_latency:
            env['PULSE_LATENCY_MSEC'] = '60'

        prefix_command = system_config.get("prefix_command") or ''
        if prefix_command.strip():
            launch_arguments.insert(0, prefix_command)

        single_cpu = system_config.get('single_cpu') or False
        if single_cpu:
            logger.info('The game will run on a single CPU core')
            launch_arguments.insert(0, '0')
            launch_arguments.insert(0, '-c')
            launch_arguments.insert(0, 'taskset')

        terminal = system_config.get('terminal')
        if terminal:
            terminal = system_config.get("terminal_app",
                                         system.get_default_terminal())
            if terminal and not system.find_executable(terminal):
                dialogs.ErrorDialog("The selected terminal application "
                                    "could not be launched:\n"
                                    "%s" % terminal)
                self.state = self.STATE_STOPPED
                return
        # Env vars
        game_env = gameplay_info.get('env') or {}
        env.update(game_env)
        system_env = system_config.get('env') or {}
        env.update(system_env)

        ld_preload = gameplay_info.get('ld_preload') or ''
        env["LD_PRELOAD"] = ld_preload

        # Runtime management
        ld_library_path = ""
        if self.runner.use_runtime():
            runtime_env = runtime.get_env()
            if 'STEAM_RUNTIME' in runtime_env and 'STEAM_RUNTIME' not in env:
                env['STEAM_RUNTIME'] = runtime_env['STEAM_RUNTIME']
            if 'LD_LIBRARY_PATH' in runtime_env:
                ld_library_path = runtime_env['LD_LIBRARY_PATH']
        game_ld_libary_path = gameplay_info.get('ld_library_path')
        if game_ld_libary_path:
            if not ld_library_path:
                ld_library_path = '$LD_LIBRARY_PATH'
            ld_library_path = ":".join([game_ld_libary_path, ld_library_path])
        env["LD_LIBRARY_PATH"] = ld_library_path

        # /Env vars

        self.game_thread = LutrisThread(launch_arguments,
                                        runner=self.runner, env=env,
                                        rootpid=gameplay_info.get('rootpid'),
                                        term=terminal)
        if hasattr(self.runner, 'stop'):
            self.game_thread.set_stop_command(self.runner.stop)
        self.game_thread.start()
        self.state = self.STATE_RUNNING
        if 'joy2key' in gameplay_info:
            self.joy2key(gameplay_info['joy2key'])
        xboxdrv_config = system_config.get('xboxdrv')
        if xboxdrv_config:
            self.xboxdrv_start(xboxdrv_config)
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
        command = [
            "pkexec", "xboxdrv", "--daemon", "--detach-kernel-driver",
            "--dbus", "session", "--silent"
        ] + config.split()
        logger.debug("[xboxdrv] %s", ' '.join(command))
        self.xboxdrv_thread = LutrisThread(command)
        self.xboxdrv_thread.set_stop_command(self.xboxdrv_stop)
        self.xboxdrv_thread.start()

    def xboxdrv_stop(self):
        os.system("pkexec xboxdrvctl --shutdown")
        if os.path.exists("/usr/share/lutris/bin/resetxpad"):
            os.system("pkexec /usr/share/lutris/bin/resetxpad")

    def beat(self):
        """Watch the game's process(es)."""
        if self.game_thread.error:
            dialogs.ErrorDialog("<b>Error lauching the game:</b>\n"
                                + self.game_thread.error)
            self.on_game_quit()
            return False
        self.game_log = self.game_thread.stdout
        killswitch_engage = self.killswitch and \
            not os.path.exists(self.killswitch)
        if not self.game_thread.is_running or killswitch_engage:
            logger.debug("Game thread stopped")
            self.on_game_quit()
            return False
        return True

    def stop(self):
        self.state = self.STATE_STOPPED
        if self.runner.system_config.get('xboxdrv'):
            self.xboxdrv_thread.stop()
        if self.game_thread:
            jobs.AsyncCall(self.game_thread.stop, None, killall=True)

    def on_game_quit(self):
        """Restore some settings and cleanup after game quit."""
        self.heartbeat = None
        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.name, quit_time)
        self.state = self.STATE_STOPPED

        os.chdir(os.path.expanduser('~'))

        if self.resolution_changed\
           or self.runner.system_config.get('reset_desktop'):
            display.change_resolution(self.original_outputs)

        if self.runner.system_config.get('use_us_layout'):
            subprocess.Popen(['setxkbmap'], env=os.environ).communicate()

        if self.runner.system_config.get('restore_gamma'):
            display.restore_gamma()

        if self.runner.system_config.get('xboxdrv') \
           and self.xboxdrv_thread.is_running:
            self.xboxdrv_thread.stop()

        if self.game_thread:
            self.game_thread.stop()
        self.process_return_codes()

        if self.exit_main_loop:
            exit()

    def process_return_codes(self):
        """Do things depending on how the game quitted."""
        if self.game_thread.return_code == 127:
            # Error missing shared lib
            error = "error while loading shared lib"
            error_line = strings.lookup_string_in_text(error,
                                                       self.game_thread.stdout)
            if error_line:
                dialogs.ErrorDialog("<b>Error: Missing shared library.</b>"
                                    "\n\n%s" % error_line)

        if self.game_thread.return_code == 1:
            # Error Wine version conflict
            error = "maybe the wrong wineserver"
            if strings.lookup_string_in_text(error, self.game_thread.stdout):
                dialogs.ErrorDialog("<b>Error: A different Wine version is "
                                    "already using the same Wine prefix.</b>")
