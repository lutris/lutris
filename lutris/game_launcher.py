from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import GLib, GObject, Gtk

from lutris import settings
from lutris.exception_backstops import watch_game_errors
from lutris.exceptions import GameConfigError, MissingExecutableError
from lutris.monitored_command import MonitoredCommand
from lutris.runner_interpreter import get_launch_parameters
from lutris.util import discord, jobs, linux, strings, system
from lutris.util.display import DISPLAY_MANAGER, SCREEN_SAVER_INHIBITOR, disable_compositing, enable_compositing
from lutris.util.graphics.xephyr import get_xephyr_command
from lutris.util.graphics.xrandr import turn_off_except
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import LOG_BUFFERS, logger
from lutris.util.process import Process
from lutris.util.timer import Timer
from lutris.util.wine import proton

if TYPE_CHECKING:
    from lutris.game import Game

HEARTBEAT_DELAY = 2000


class GameLauncher(GObject.Object):
    __gsignals__ = {
        # SIGNAL_RUN_LAST works around bug https://gitlab.gnome.org/GNOME/glib/-/issues/513
        # fix merged Dec 2020, but we support older GNOME!
        "game-error": (GObject.SIGNAL_RUN_LAST, bool, (object,)),
        "game-unhandled-error": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "game-start": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-started": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-stopped": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }
    now_playing_path = os.path.join(settings.CACHE_DIR, "now-playing.txt")

    STATE_STOPPED = "stopped"
    STATE_LAUNCHING = "launching"
    STATE_RUNNING = "running"

    def __init__(self, game: Game):
        super().__init__()
        self.game = game
        self.state: str = self.STATE_STOPPED
        self.heartbeat = None
        self.killswitch = None
        self.game_uuid: str = None
        self.game_thread: MonitoredCommand = None
        self.antimicro_thread: MonitoredCommand = None
        self.prelaunch_pids = None
        self.prelaunch_executor = None
        self.game_runtime_config = {}
        self.resolution_changed: bool = False
        self.compositor_disabled: bool = False
        self.original_outputs = None
        self._log_buffer = None
        self.timer = Timer()
        self.screen_saver_inhibitor_cookie = None

    @property
    def runner(self):
        return self.game.runner

    @property
    def log_buffer(self) -> Gtk.TextBuffer:
        """Access the log buffer object, creating it if necessary"""
        _log_buffer = LOG_BUFFERS.get(self.game.id)
        if _log_buffer:
            return _log_buffer
        _log_buffer = Gtk.TextBuffer()
        _log_buffer.create_tag("warning", foreground="red")
        if self.game_thread:
            self.game_thread.set_log_buffer(self._log_buffer)
            _log_buffer.set_text(self.game_thread.stdout)
        LOG_BUFFERS[self.game.id] = _log_buffer
        return _log_buffer

    def signal_error(self, error) -> None:
        """Reports an error by firing game-error. If handled, it returns
        True to indicate it handled it, and that's it. If not, this fires
        game-unhandled-error, which is actually handled via an emission hook
        and should not be connected otherwise.

        This allows special error handling to be set up for a particular Game, but
        there's always some handling."""
        handled = self.emit("game-error", error)
        if not handled:
            self.emit("game-unhandled-error", error)

    def check_launchable(self) -> bool:
        """Verify that the current game can be launched, and raises exceptions if not."""
        if not self.game.is_installed or not self.game.is_db_stored:
            logger.error("%s (%s) not installed", self, self.id)
            raise GameConfigError(_("Tried to launch a game that isn't installed."))
        if not self.game.has_runner:
            raise GameConfigError(_("Invalid game configuration: Missing runner"))

        return True

    def restrict_to_display(self, display):
        outputs = DISPLAY_MANAGER.get_config()
        if display == "primary":
            display = None
            for output in outputs:
                if output.primary:
                    display = output.name
                    break
            if not display:
                logger.warning("No primary display set")
        else:
            found = False
            for output in outputs:
                if output.name == display:
                    found = True
                    break
            if not found:
                logger.warning("Selected display %s not found", display)
                display = None
        if display:
            turn_off_except(display)
            time.sleep(3)
            return True
        return False

    def start_xephyr(self, display=":2"):
        """Start a monitored Xephyr instance"""
        if not system.can_find_executable("Xephyr"):
            raise GameConfigError(_("Unable to find Xephyr, install it or disable the Xephyr option"))
        xephyr_command = get_xephyr_command(display, self.game.runner.system_config)
        xephyr_thread = MonitoredCommand(xephyr_command)
        xephyr_thread.start()
        time.sleep(3)
        return display

    def start_antimicrox(self, antimicro_config):
        """Start Antimicrox with a given config path"""
        if LINUX_SYSTEM.is_flatpak():
            antimicro_command = ["flatpak-spawn", "--host", "antimicrox"]
        else:
            try:
                antimicro_command = [system.find_required_executable("antimicrox")]
            except MissingExecutableError as ex:
                raise GameConfigError(
                    _("Unable to find Antimicrox, install it or disable the Antimicrox option")
                ) from ex

        logger.info("Starting Antimicro")
        antimicro_command += ["--hidden", "--tray", "--profile", antimicro_config]
        self.antimicro_thread = MonitoredCommand(antimicro_command)
        self.antimicro_thread.start()

    def start_prelaunch_command(self, wait_for_completion=False):
        """Start the prelaunch command specified in the system options"""
        prelaunch_command = self.game.runner.system_config.get("prelaunch_command")
        command_array = shlex.split(prelaunch_command)
        if not system.path_exists(command_array[0]):
            logger.warning("Command %s not found", command_array[0])
            return
        env = self.game_runtime_config["env"]
        if wait_for_completion:
            logger.info("Prelauch command: %s, waiting for completion", prelaunch_command)
            # Monitor the prelaunch command and wait until it has finished
            system.execute(command_array, env=env, cwd=self.game.resolve_game_path())
        else:
            logger.info("Prelaunch command %s launched in the background", prelaunch_command)
            self.prelaunch_executor = MonitoredCommand(
                command_array,
                include_processes=[os.path.basename(command_array[0])],
                env=env,
                cwd=self.game.resolve_game_path(),
            )
            self.prelaunch_executor.start()

    def get_terminal(self):
        """Return the terminal used to run the game into or None if the game is not run from a terminal.
        Remember that only games using text mode should use the terminal.
        """
        if self.game.runner.system_config.get("terminal"):
            terminal = self.game.runner.system_config.get("terminal_app", linux.get_default_terminal())
            if terminal and not system.can_find_executable(terminal):
                raise GameConfigError(_("The selected terminal application could not be launched:\n%s") % terminal)
            return terminal

    def get_killswitch(self):
        """Return the path to a file that is monitored during game execution.
        If the file stops existing, the game is stopped.
        """
        killswitch = self.game.runner.system_config.get("killswitch")
        # Prevent setting a killswitch to a file that doesn't exists
        if killswitch and system.path_exists(self.killswitch):
            return killswitch

    def get_gameplay_info(self, launch_ui_delegate) -> dict:
        """Return the information provided by a runner's play method.
        It checks for possible errors and raises exceptions if they occur.

        This may invoke methods on the delegates to make decisions,
        and this may show UI.

        This returns an empty dictionary if the user cancels this UI,
        in which case the game should not be run.
        """

        gameplay_info = self.runner.play()

        if "working_dir" not in gameplay_info:
            gameplay_info["working_dir"] = self.runner.working_dir

        config = launch_ui_delegate.select_game_launch_config(self)

        if config is None:
            return {}  # no error here- the user cancelled out

        if config:  # empty dict for primary configuration
            self.runner.apply_launch_config(gameplay_info, config)

        return gameplay_info

    @watch_game_errors(game_stop_result=False)
    def configure_game(self, launch_ui_delegate) -> bool:
        """Get the game ready to start, applying all the options.
        This method sets the game_runtime_config attribute.
        """
        gameplay_info = self.get_gameplay_info(launch_ui_delegate)
        if not gameplay_info:  # if user cancelled - not an error
            return False
        command, env = get_launch_parameters(self.runner, gameplay_info)

        if env.get("WINEARCH") == "win32" and "umu" in " ".join(command):
            raise RuntimeError("Proton is not compatible with 32bit prefixes")

        # Allow user to override default umu environment variables to apply fixes
        env["GAMEID"] = proton.get_game_id(self.game)
        env["STORE"] = env.get("STORE") or self.game.get_store_name()

        # Some environment variables for the use of custom pre-launch and post-exit scripts.
        env["GAME_NAME"] = self.game.name
        if self.game.directory:
            env["GAME_DIRECTORY"] = self.game.directory

        self.game_runtime_config = {
            "args": command,
            "env": env,
            "terminal": self.get_terminal(),
            "include_processes": shlex.split(self.runner.system_config.get("include_processes", "")),
            "exclude_processes": shlex.split(self.runner.system_config.get("exclude_processes", "")),
        }

        if "working_dir" in gameplay_info:
            self.game_runtime_config["working_dir"] = gameplay_info["working_dir"]

        # Input control
        if self.runner.system_config.get("use_us_layout"):
            system.set_keyboard_layout("us")

        # Display control
        self.original_outputs = DISPLAY_MANAGER.get_config()

        if self.runner.system_config.get("disable_compositor"):
            self._set_desktop_compositing(False)

        if self.runner.system_config.get("disable_screen_saver"):
            self.screen_saver_inhibitor_cookie = SCREEN_SAVER_INHIBITOR.inhibit(self.game.name)

        if self.runner.system_config.get("display") != "off":
            self.resolution_changed = self.restrict_to_display(self.runner.system_config.get("display"))

        resolution = self.runner.system_config.get("resolution")
        if resolution != "off":
            DISPLAY_MANAGER.set_resolution(resolution)
            time.sleep(3)
            self.resolution_changed = True

        xephyr = self.runner.system_config.get("xephyr") or "off"
        if xephyr != "off":
            env["DISPLAY"] = self.start_xephyr()

        antimicro_config = self.runner.system_config.get("antimicro_config")
        if system.path_exists(antimicro_config):
            self.start_antimicrox(antimicro_config)

        # Execution control
        self.killswitch = self.get_killswitch()

        if self.runner.system_config.get("prelaunch_command"):
            self.start_prelaunch_command(self.runner.system_config.get("prelaunch_wait"))

        self._start_game()
        return True

    def _set_desktop_compositing(self, enable) -> None:
        """Enables or disables compositing"""
        if enable:
            if self.compositor_disabled:
                enable_compositing()
                self.compositor_disabled = False
        else:
            if not self.compositor_disabled:
                disable_compositing()
                self.compositor_disabled = True

    @watch_game_errors(game_stop_result=False)
    def launch(self, launch_ui_delegate) -> bool:
        """Request launching a game. The game may not be installed yet."""
        if not self.check_launchable():
            logger.error("Game is not launchable")
            return False

        if not launch_ui_delegate.check_game_launchable(self):
            return False

        self.game.reload_config()  # Reload the config before launching it.

        if self.game.id in LOG_BUFFERS:  # Reset game logs on each launch
            log_buffer = LOG_BUFFERS[self.game.id]
            log_buffer.delete(log_buffer.get_start_iter(), log_buffer.get_end_iter())

        self.state = self.STATE_LAUNCHING
        self.prelaunch_pids = system.get_running_pid_list()

        if not self.prelaunch_pids:
            logger.error("No prelaunch PIDs could be obtained. Game stop may be ineffective.")
            self.prelaunch_pids = None

        self.emit("game-start")

        @watch_game_errors(game_stop_result=False, game_launcher=self)
        def configure_game(_ignored, error):
            if error:
                raise error
            self.configure_game(launch_ui_delegate)

        jobs.AsyncCall(self.runner.prelaunch, configure_game)
        return True

    def _start_game(self) -> None:
        """Run a background command to launch the game"""
        self.game_thread = MonitoredCommand(
            self.game_runtime_config["args"],
            title=self.game.name,
            runner=self.runner,
            cwd=self.game_runtime_config.get("working_dir"),
            env=self.game_runtime_config["env"],
            term=self.game_runtime_config["terminal"],
            log_buffer=self.log_buffer,
            include_processes=self.game_runtime_config["include_processes"],
            exclude_processes=self.game_runtime_config["exclude_processes"],
        )
        if hasattr(self.runner, "stop"):
            self.game_thread.stop_func = self.runner.stop
        self.game_uuid = self.game_thread.env["LUTRIS_GAME_UUID"]
        self.game_thread.start()
        self.timer.start()
        self.state = self.STATE_RUNNING
        self.emit("game-started")

        # Game is running, let's update discord status
        if settings.read_setting("discord_rpc") == "True" and self.game.discord_id:
            try:
                discord.client.update(self.game.discord_id)
            except AssertionError:
                pass

        self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self._beat)
        with open(self.now_playing_path, "w", encoding="utf-8") as np_file:
            np_file.write(self.game.name)

    def force_stop(self) -> None:
        # If force_stop_game fails, wait a few seconds and try SIGKILL on any survivors

        def force_stop_game() -> bool:
            self.runner.force_stop_game(self)
            return not self._get_stop_pids()

        def force_stop_game_cb(all_dead, error):
            if error:
                self.signal_error(error)
            elif all_dead:
                self.stop_game()
            else:
                self._force_kill_delayed()

        jobs.AsyncCall(force_stop_game, force_stop_game_cb)

    def _force_kill_delayed(self, death_watch_seconds=5, death_watch_interval_seconds=0.5) -> None:
        """Forces termination of a running game, but only after a set time has elapsed;
        Invokes stop_game() when the game is dead."""

        def death_watch() -> None:
            """Wait for the processes to die; kill them if they do not."""
            for _n in range(int(death_watch_seconds / death_watch_interval_seconds)):
                time.sleep(death_watch_interval_seconds)
                if not self._get_stop_pids():
                    return

            # Once we get past the time limit, starting killing!
            self.kill_processes(signal.SIGKILL)

        def _death_watch_cb(_result, error):
            """Called after the death watch to more firmly kill any survivors."""
            if error:
                self.signal_error(error)

            # If we still can't kill everything, we'll still say we stopped it.
            self.stop_game()

        jobs.AsyncCall(death_watch, _death_watch_cb)

    def kill_processes(self, sig) -> None:
        """Sends a signal to a process list, logging errors."""
        pids = self._get_stop_pids()

        for pid in pids:
            try:
                os.kill(int(pid), sig)
            except ProcessLookupError as ex:
                logger.debug("Failed to kill game process: %s", ex)
            except PermissionError:
                logger.debug("Permission to kill process %s denied", pid)

    def _get_stop_pids(self) -> set:
        """Finds the PIDs of processes that need killin'!"""
        pids = self._get_game_pids()
        if self.game_thread and self.game_thread.game_process:
            if self.game_thread.game_process.poll() is None:
                pids.add(self.game_thread.game_process.pid)
        return pids

    def _get_game_pids(self) -> set:
        """Return a list of processes belonging to the Lutris game"""
        if not self.game_uuid:
            logger.error("No LUTRIS_GAME_UUID recorded. The game's PIDs cannot be computed.")
            return set()

        new_pids = self._get_new_pids()

        game_folder = self.game.resolve_game_path()
        folder_pids = set()
        for pid in new_pids:
            cmdline = Process(pid).cmdline or ""
            # pressure-vessel: This could potentially pick up PIDs not started by lutris?
            if game_folder in cmdline or "pressure-vessel" in cmdline:
                folder_pids.add(pid)

        uuid_pids = set(pid for pid in new_pids if Process(pid).environ.get("LUTRIS_GAME_UUID") == self.game_uuid)

        return folder_pids & uuid_pids

    def _get_new_pids(self) -> set:
        """Return list of PIDs started since the game was launched"""
        if self.prelaunch_pids:
            return set(system.get_running_pid_list()) - set(self.prelaunch_pids)

        logger.error("No prelaunch PIDs recorded. The game's PIDs cannot be computed.")
        return set()

    def stop_game(self) -> None:
        """Cleanup after a game as stopped"""
        duration = self.timer.duration
        logger.debug("%s has run for %d seconds", self, duration)
        if duration < 5:
            logger.warning("The game has run for a very short time, did it crash?")
            # Inspect why it could have crashed

        self.state = self.STATE_STOPPED
        self.emit("game-stopped")
        if os.path.exists(self.now_playing_path):
            os.unlink(self.now_playing_path)
        if not self.timer.finished:
            self.timer.end()
            self.game.playtime += self.timer.duration / 3600

    @watch_game_errors(game_stop_result=False)
    def _beat(self) -> bool:
        """Watch the game's process(es)."""
        if self.game_thread.error:
            self._on_game_quit()
            raise RuntimeError(_("<b>Error lauching the game:</b>\n") + self.game_thread.error)

        # The killswitch file should be set to a device (ie. /dev/input/js0)
        # When that device is unplugged, the game is forced to quit.
        killswitch_engage = self.killswitch and not system.path_exists(self.killswitch)
        if killswitch_engage:
            logger.warning("File descriptor no longer present, force quit the game")
            self.force_stop()
            return False
        game_pids = self._get_game_pids()
        runs_only_prelaunch = False
        if self.prelaunch_executor and self.prelaunch_executor.is_running:
            runs_only_prelaunch = game_pids == {self.prelaunch_executor.game_process.pid}
        if runs_only_prelaunch or (not self.game_thread.is_running and not game_pids):
            logger.debug("Game thread stopped.")
            logger.debug("Game PIDs: %s", game_pids)
            self._on_game_quit()
            return False
        return True

    def _stop(self) -> None:
        """Stops the game"""
        if self.state == self.STATE_STOPPED:
            logger.debug("Game already stopped")
            return

        logger.info("Stopping %s", self)

        if self.game_thread:

            def stop_cb(_result, error):
                if error:
                    self.signal_error(error)

            jobs.AsyncCall(self.game_thread.stop, stop_cb)
        self.stop_game()

    def _on_game_quit(self) -> None:
        """Restore some settings and cleanup after game quit."""

        if self.prelaunch_executor and self.prelaunch_executor.is_running:
            logger.info("Stopping prelaunch script")
            self.prelaunch_executor.stop()

        # We need to do some cleanup before we emit game-stop as this can
        # trigger Lutris shutdown

        if self.screen_saver_inhibitor_cookie is not None:
            SCREEN_SAVER_INHIBITOR.uninhibit(self.screen_saver_inhibitor_cookie)
            self.screen_saver_inhibitor_cookie = None

        self.heartbeat = None
        if self.state != self.STATE_STOPPED:
            logger.warning("Game still running (state: %s)", self.state)
            self._stop()

        # Check for post game script
        postexit_command = self.runner.system_config.get("postexit_command")
        if postexit_command:
            command_array = shlex.split(postexit_command)
            if system.path_exists(command_array[0]):
                logger.info("Running post-exit command: %s", postexit_command)
                postexit_thread = MonitoredCommand(
                    command_array,
                    include_processes=[os.path.basename(postexit_command)],
                    env=self.game_runtime_config["env"],
                    cwd=self.resolve_game_path(),
                )
                postexit_thread.start()

        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.game.name, quit_time)
        self.lastplayed = int(time.time())
        self.game.save_lastplayed()

        os.chdir(os.path.expanduser("~"))

        if self.antimicro_thread:
            self.antimicro_thread.stop()

        if self.resolution_changed or self.runner.system_config.get("reset_desktop"):
            DISPLAY_MANAGER.set_resolution(self.original_outputs)

        if self.compositor_disabled:
            self._set_desktop_compositing(True)

        if self.runner.system_config.get("use_us_layout"):
            with subprocess.Popen(["setxkbmap"], env=os.environ) as setxkbmap:
                setxkbmap.communicate()

        # Clear Discord Client Status
        if settings.read_setting("discord_rpc") == "True" and self.game.discord_id:
            discord.client.clear()

        self._process_return_codes()

    def _process_return_codes(self):
        """Do things depending on how the game quitted."""
        if self.game_thread.return_code == 127:
            # Error missing shared lib
            error = "error while loading shared lib"
            error_lines = strings.lookup_strings_in_text(error, self.game_thread.stdout)
            if error_lines:
                raise RuntimeError(_("<b>Error: Missing shared library.</b>\n\n%s") % error_lines[0])

        if self.game_thread.return_code == 1:
            # Error Wine version conflict
            error = "maybe the wrong wineserver"
            if strings.lookup_strings_in_text(error, self.game_thread.stdout):
                raise RuntimeError(_("<b>Error: A different Wine version is already using the same Wine prefix.</b>"))
