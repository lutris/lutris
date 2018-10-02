# -*- coding: utf-8 -*-
"""Module that actually runs the games."""
import os
import time
import shlex
import subprocess

from gi.repository import GLib, Gtk

from lutris import pga
from lutris import runtime
from lutris.services import xdg
from lutris.runners import import_runner, InvalidRunner
from lutris.util import audio, display, jobs, system, strings
from lutris.util.log import logger
from lutris.config import LutrisConfig
from lutris.thread import LutrisThread, HEARTBEAT_DELAY
from lutris.gui import dialogs


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
        self.exit_main_loop = False

        game_data = pga.get_game_by_field(id, 'id')
        self.slug = game_data.get('slug') or ''
        self.runner_name = game_data.get('runner') or ''
        self.directory = game_data.get('directory') or ''
        self.name = game_data.get('name') or ''

        self.is_installed = bool(game_data.get('installed')) or False
        self.platform = game_data.get('platform') or ''
        self.year = game_data.get('year') or ''
        self.lastplayed = game_data.get('lastplayed') or 0
        self.game_config_id = game_data.get('configpath') or ''
        self.steamid = game_data.get('steamid') or ''
        self.has_custom_banner = bool(game_data.get('has_custom_banner')) or False
        self.has_custom_icon = bool(game_data.get('has_custom_icon')) or False

        self.load_config()
        self.resolution_changed = False
        self.compositor_disabled = False
        self.stop_compositor = self.start_compositor = ""
        self.original_outputs = None
        self.log_buffer = Gtk.TextBuffer()
        self.log_buffer.create_tag("warning", foreground="red")

    def __repr__(self):
        return self.__unicode__()

    def __unicode__(self):
        value = self.name
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    def show_error_message(self, message):
        """Display an error message based on the runner's output."""
        if "CUSTOM" == message['error']:
            message_text = message['text'].replace('&', '&amp;')
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

    def desktop_effects(self, enable):
        if enable:
            system.execute(self.start_compositor, shell=True)
        else:
            if os.environ.get('DESKTOP_SESSION') == "plasma":
                self.stop_compositor = "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.suspend"
                self.start_compositor = "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.resume"
            elif os.environ.get('DESKTOP_SESSION') == "mate" and system.execute("gsettings get org.mate.Marco.general compositing-manager", shell=True) == 'true':
                self.stop_compositor = "gsettings set org.mate.Marco.general compositing-manager false"
                self.start_compositor = "gsettings set org.mate.Marco.general compositing-manager true"
            elif os.environ.get('DESKTOP_SESSION') == "xfce" and system.execute("xfconf-query --channel=xfwm4 --property=/general/use_compositing", shell=True) == 'true':
                self.stop_compositor = "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=false"
                self.start_compositor = "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=true"

            if not (self.compositor_disabled or self.stop_compositor == ""):
                system.execute(self.stop_compositor, shell=True)
                self.compositor_disabled = True;

    def remove(self, from_library=False, from_disk=False):
        if from_disk and self.runner:
            logger.debug("Removing game %s from disk" % self.id)
            self.runner.remove_game_data(game_path=self.directory)

        # Do not keep multiple copies of the same game
        existing_games = pga.get_games_where(slug=self.slug)
        if len(existing_games) > 1:
            from_library = True

        if from_library:
            logger.debug("Removing game %s from library" % self.id)
            pga.delete_game(self.id)
        else:
            pga.set_uninstalled(self.id)
        self.config.remove()
        xdg.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        return from_library

    def set_platform_from_runner(self):
        if not self.runner:
            return
        self.platform = self.runner.get_platform()

    def save(self, metadata_only=False):
        """
        Save the game's config and metadata, if `metadata_only` is set to True,
        do not save the config. This is useful when exiting the game since the
        config might have changed and we don't want to override the changes.
        """
        if not metadata_only:
            self.config.save()
        self.id = pga.add_or_update(
            name=self.name,
            runner=self.runner_name,
            slug=self.slug,
            platform=self.platform,
            year=self.year,
            lastplayed=self.lastplayed,
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
        self.original_outputs = sorted(
            display.get_outputs(),
            key=lambda e: e[0] == system_config.get('display')
        )

        gameplay_info = self.runner.play()
        logger.debug("Launching %s: %s" % (self.name, gameplay_info))
        if 'error' in gameplay_info:
            self.show_error_message(gameplay_info)
            self.state = self.STATE_STOPPED
            return

        env = {}
        sdl_gamecontrollerconfig = system_config.get('sdl_gamecontrollerconfig')
        if sdl_gamecontrollerconfig:
            path = os.path.expanduser(sdl_gamecontrollerconfig)
            if os.path.exists(path):
                with open(path, "r") as f:
                    sdl_gamecontrollerconfig = f.read()
            env['SDL_GAMECONTROLLERCONFIG'] = sdl_gamecontrollerconfig

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

        optimus = system_config.get('optimus')
        if optimus == 'primusrun' and system.find_executable('primusrun'):
            launch_arguments.insert(0, 'primusrun')
        elif optimus == 'optirun' and system.find_executable('optirun'):
            launch_arguments.insert(0, 'virtualgl')
            launch_arguments.insert(0, '-b')
            launch_arguments.insert(0, 'optirun')

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
        if prefix_command:
            launch_arguments = shlex.split(os.path.expandvars(prefix_command)) + launch_arguments

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
        game_env = gameplay_info.get('env') or self.runner.get_env()
        env.update(game_env)

        ld_preload = gameplay_info.get('ld_preload')
        if ld_preload:
            env["LD_PRELOAD"] = ld_preload

        game_ld_libary_path = gameplay_info.get('ld_library_path')
        if game_ld_libary_path:
            ld_library_path = env.get("LD_LIBRARY_PATH")
            if not ld_library_path:
                ld_library_path = '$LD_LIBRARY_PATH'
            ld_library_path = ":".join([game_ld_libary_path, ld_library_path])
            env["LD_LIBRARY_PATH"] = ld_library_path
        # /Env vars

        include_processes = shlex.split(system_config.get('include_processes', ''))
        exclude_processes = shlex.split(system_config.get('exclude_processes', ''))

        monitoring_disabled = system_config.get('disable_monitoring')
        if monitoring_disabled:
            dialogs.ErrorDialog("<b>The process monitor is disabled, Lutris "
                                "won't be able to keep track of the game status. "
                                "If this game require the process monitor to be "
                                "disabled in order to run, please submit an "
                                "issue.</b>")
        process_watch = not monitoring_disabled

        if self.runner.system_config.get('disable_compositor'):
            self.desktop_effects(False)

        self.game_thread = LutrisThread(launch_arguments,
                                        runner=self.runner,
                                        env=env,
                                        rootpid=gameplay_info.get('rootpid'),
                                        watch=process_watch,
                                        term=terminal,
                                        log_buffer=self.log_buffer,
                                        include_processes=include_processes,
                                        exclude_processes=exclude_processes)
        if hasattr(self.runner, 'stop'):
            self.game_thread.set_stop_command(self.runner.stop)
        self.game_thread.start()
        self.state = self.STATE_RUNNING

        # xboxdrv setup
        xboxdrv_config = system_config.get('xboxdrv')
        if xboxdrv_config:
            self.xboxdrv_start(xboxdrv_config)

        if monitoring_disabled:
            logger.info("Process monitoring disabled")
        else:
            self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.beat)

    def xboxdrv_start(self, config):
        command = [
            "pkexec", "xboxdrv", "--daemon", "--detach-kernel-driver",
            "--dbus", "session", "--silent"
        ] + config.split()
        logger.debug("[xboxdrv] %s", ' '.join(command))
        self.xboxdrv_thread = LutrisThread(command, include_processes=['xboxdrv'])
        self.xboxdrv_thread.set_stop_command(self.xboxdrv_stop)
        self.xboxdrv_thread.start()

    def xboxdrv_stop(self):
        os.system("pkexec xboxdrvctl --shutdown")
        if os.path.exists("/usr/share/lutris/bin/resetxpad"):
            os.system("pkexec /usr/share/lutris/bin/resetxpad")

    def beat(self):
        """Watch the game's process(es)."""
        if self.game_thread.error:
            dialogs.ErrorDialog("<b>Error lauching the game:</b>\n" +
                                self.game_thread.error)
            self.on_game_quit()
            return False

        # The killswitch file should be set to a device (ie. /dev/input/js0)
        # When that device is unplugged, the game is forced to quit.
        killswitch_engage = (
            self.killswitch and not os.path.exists(self.killswitch)
        )
        if not self.game_thread.is_running or killswitch_engage:
            logger.debug("Game thread stopped")
            self.on_game_quit()
            return False
        return True

    def stop(self):
        if self.runner.system_config.get('xboxdrv'):
            logger.debug("Stopping xboxdrv")
            self.xboxdrv_thread.stop()
        if self.game_thread:
            jobs.AsyncCall(self.game_thread.stop, None, killall=self.runner.killall_on_exit())
        self.state = self.STATE_STOPPED

    def on_game_quit(self):
        """Restore some settings and cleanup after game quit."""
        self.heartbeat = None
        if self.state != self.STATE_STOPPED:
            logger.debug("Game thread still running, stopping it (state: %s)", self.state)
            self.stop()
        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.name, quit_time)
        self.lastplayed = int(time.time())
        self.save(metadata_only=True)

        os.chdir(os.path.expanduser('~'))

        if self.resolution_changed\
           or self.runner.system_config.get('reset_desktop'):
            display.change_resolution(self.original_outputs)

        if self.compositor_disabled:
            self.desktop_effects(True)

        if self.runner.system_config.get('use_us_layout'):
            subprocess.Popen(['setxkbmap'], env=os.environ).communicate()

        if self.runner.system_config.get('restore_gamma'):
            display.restore_gamma()

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

    def notify_steam_game_changed(self, appmanifest):
        """Receive updates from Steam games and set the thread's ready state accordingly"""
        if not self.game_thread:
            return
        if 'Fully Installed' in appmanifest.states and not self.game_thread.ready_state:
            logger.info("Steam game %s is fully installed", appmanifest.steamid)
            self.game_thread.ready_state = True
        elif 'Update Required' in appmanifest.states and self.game_thread.ready_state:
            logger.info("Steam game %s updating, setting game thread as not ready",
                        appmanifest.steamid)
            self.game_thread.ready_state = False
