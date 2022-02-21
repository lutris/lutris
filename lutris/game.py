"""Module that actually runs the games."""

# pylint: disable=too-many-public-methods
import os
import shlex
import shutil
import signal
import subprocess
import time
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk

from lutris import runtime, settings
from lutris.command import MonitoredCommand
from lutris.config import LutrisConfig
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exceptions import GameConfigError, watch_lutris_errors
from lutris.gui import dialogs
from lutris.runner_interpreter import export_bash_script, get_launch_parameters
from lutris.runners import InvalidRunner, import_runner, wine
from lutris.util import audio, jobs, linux, strings, system, xdgshortcuts
from lutris.util.display import (
    DISPLAY_MANAGER, SCREEN_SAVER_INHIBITOR, disable_compositing, enable_compositing, restore_gamma
)
from lutris.util.graphics.xephyr import get_xephyr_command
from lutris.util.graphics.xrandr import turn_off_except
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import LOG_BUFFERS, logger
from lutris.util.process import Process
from lutris.util.timer import Timer

HEARTBEAT_DELAY = 2000


class Game(GObject.Object):
    """This class takes cares of loading the configuration for a game
       and running it.
    """

    now_playing_path = os.path.join(settings.CACHE_DIR, "now-playing.txt")

    STATE_STOPPED = "stopped"
    STATE_LAUNCHING = "launching"
    STATE_RUNNING = "running"

    __gsignals__ = {
        "game-error": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "game-launch": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-start": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-started": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-stop": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-stopped": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-removed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-install": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-install-update": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-install-dlc": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game_id=None):
        super().__init__()
        self.id = game_id  # pylint: disable=invalid-name
        self.runner = None
        self.config = None

        # Load attributes from database
        game_data = games_db.get_game_by_field(game_id, "id")

        self.slug = game_data.get("slug") or ""
        self.runner_name = game_data.get("runner") or ""
        self.directory = game_data.get("directory") or ""
        self.name = game_data.get("name") or ""
        self.game_config_id = game_data.get("configpath") or ""
        self.is_installed = bool(game_data.get("installed") and self.game_config_id)
        self.is_hidden = bool(game_data.get("hidden"))
        self.platform = game_data.get("platform") or ""
        self.year = game_data.get("year") or ""
        self.lastplayed = game_data.get("lastplayed") or 0
        self.has_custom_banner = bool(game_data.get("has_custom_banner"))
        self.has_custom_icon = bool(game_data.get("has_custom_icon"))
        self.service = game_data.get("service")
        self.appid = game_data.get("service_id")
        self.playtime = game_data.get("playtime") or 0.0

        if self.game_config_id:
            self.load_config()
        self.game_uuid = None
        self.game_thread = None
        self.antimicro_thread = None
        self.prelaunch_pids = []
        self.prelaunch_executor = None
        self.heartbeat = None
        self.killswitch = None
        self.state = self.STATE_STOPPED
        self.game_runtime_config = {}
        self.resolution_changed = False
        self.compositor_disabled = False
        self.original_outputs = None
        self._log_buffer = None
        self.timer = Timer()
        self.screen_saver_inhibitor_cookie = None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        value = self.name or "Game (no name)"
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    @property
    def is_updatable(self):
        """Return whether the game can be upgraded"""
        return self.service == "gog"

    @property
    def is_favorite(self):
        """Return whether the game is in the user's favorites"""
        categories = categories_db.get_categories_in_game(self.id)
        for category in categories:
            if category == "favorite":
                return True
        return False

    def add_to_favorites(self):
        """Add the game to the 'favorite' category"""
        favorite = categories_db.get_category("favorite")
        if not favorite:
            favorite = categories_db.add_category("favorite")
        categories_db.add_game_to_category(self.id, favorite["id"])
        self.emit("game-updated")

    def remove_from_favorites(self):
        """Remove game from favorites"""
        favorite = categories_db.get_category("favorite")
        categories_db.remove_category_from_game(self.id, favorite["id"])
        self.emit("game-updated")

    def set_hidden(self, is_hidden):
        """Do not show this game in the UI"""
        self.is_hidden = is_hidden
        self.save()
        self.emit("game-updated")

    @property
    def log_buffer(self):
        """Access the log buffer object, creating it if necessary"""
        _log_buffer = LOG_BUFFERS.get(str(self.id))
        if _log_buffer:
            return _log_buffer
        _log_buffer = Gtk.TextBuffer()
        _log_buffer.create_tag("warning", foreground="red")
        if self.game_thread:
            self.game_thread.set_log_buffer(self._log_buffer)
            _log_buffer.set_text(self.game_thread.stdout)
        LOG_BUFFERS[str(self.id)] = _log_buffer
        return _log_buffer

    @property
    def formatted_playtime(self):
        """Return a human readable formatted play time"""
        return strings.get_formatted_playtime(self.playtime)

    @staticmethod
    def show_error_message(message):
        """Display an error message based on the runner's output."""
        if message["error"] == "CUSTOM":
            message_text = message["text"].replace("&", "&amp;")
            dialogs.ErrorDialog(message_text)
        elif message["error"] == "RUNNER_NOT_INSTALLED":
            dialogs.ErrorDialog(_("Error the runner is not installed"))
        elif message["error"] == "NO_BIOS":
            dialogs.ErrorDialog(_("A bios file is required to run this game"))
        elif message["error"] == "FILE_NOT_FOUND":
            filename = message["file"]
            if filename:
                message_text = _("The file {} could not be found").format(filename.replace("&", "&amp;"))
            else:
                message_text = _("This game has no executable set. The install process didn't finish properly.")
            dialogs.ErrorDialog(message_text)
        elif message["error"] == "NOT_EXECUTABLE":
            message_text = message["file"].replace("&", "&amp;")
            dialogs.ErrorDialog(_("The file %s is not executable") % message_text)
        elif message["error"] == "PATH_NOT_SET":
            message_text = _("The path '%s' is not set. please set it in the options.") % message["path"]
            dialogs.ErrorDialog(message_text)
        else:
            dialogs.ErrorDialog(_("Unhandled error: %s") % message["error"])

    def get_browse_dir(self):
        """Return the path to open with the Browse Files action."""
        return self.runner.game_path

    def _get_runner(self):
        """Return the runner instance for this game's configuration"""
        try:
            runner_class = import_runner(self.runner_name)
            return runner_class(self.config)
        except InvalidRunner:
            logger.error("Unable to import runner %s for %s", self.runner_name, self.slug)

    def load_config(self):
        """Load the game's configuration."""
        if not self.is_installed:
            return
        self.config = LutrisConfig(runner_slug=self.runner_name, game_config_id=self.game_config_id)
        self.runner = self._get_runner()

    def set_desktop_compositing(self, enable):
        """Enables or disables compositing"""
        if enable:
            if self.compositor_disabled:
                enable_compositing()
                self.compositor_disabled = False
        else:
            if not self.compositor_disabled:
                disable_compositing()
                self.compositor_disabled = True

    def remove(self, delete_files=False, no_signal=False):
        """Uninstall a game

        Params:
            delete_files (bool): Delete the game files
            no_signal (bool): Don't emit game-removed signal (if running in a thread)
        """
        sql.db_update(settings.PGA_DB, "games", {"installed": 0, "runner": ""}, {"id": self.id})
        if self.config:
            self.config.remove()
        xdgshortcuts.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        if delete_files and self.runner:
            self.runner.remove_game_data(game_path=self.directory)
        self.is_installed = False
        self.runner = None
        if no_signal:
            return
        self.emit("game-removed")

    def delete(self):
        """Completely remove a game from the library"""
        if self.is_installed:
            raise RuntimeError("Uninstall the game before deleting")
        games_db.delete_game(self.id)
        self.emit("game-removed")

    def set_platform_from_runner(self):
        """Set the game's platform from the runner"""
        if not self.runner:
            logger.warning("Game has no runner, can't set platform")
            return
        self.platform = self.runner.get_platform()
        if not self.platform:
            logger.warning("The %s runner didn't provide a platform for %s", self.runner.human_name, self)

    def save(self, save_config=False):
        """
        Save the game's config and metadata, if `save_config` is set to False,
        do not save the config. This is useful when exiting the game since the
        config might have changed and we don't want to override the changes.
        """
        if self.config:
            logger.debug("Saving %s with config ID %s", self, self.config.game_config_id)
            configpath = self.config.game_config_id
            if save_config:
                self.config.save()
        else:
            logger.warning("Saving %s without a configuration", self)
            configpath = ""
        self.set_platform_from_runner()
        self.id = games_db.add_or_update(
            name=self.name,
            runner=self.runner_name,
            slug=self.slug,
            platform=self.platform,
            directory=self.directory,
            installed=self.is_installed,
            year=self.year,
            lastplayed=self.lastplayed,
            configpath=configpath,
            id=self.id,
            playtime=self.playtime,
            hidden=self.is_hidden,
            service=self.service,
            service_id=self.appid,
        )
        self.emit("game-updated")

    def is_launchable(self):
        """Verify that the current game can be launched."""
        if not self.is_installed:
            dialogs.ErrorDialog(_("Tried to launch a game that isn't installed. (Who'd you do that?)"))
            return False
        if not self.runner:
            dialogs.ErrorDialog(_("Invalid game configuration: Missing runner"))
            return False
        if not self.runner.is_installed():
            installed = self.runner.install_dialog()
            if not installed:
                dialogs.ErrorDialog(_("Runner not installed."))
                return False

        if self.runner.use_runtime():
            runtime_updater = runtime.RuntimeUpdater()
            if runtime_updater.is_updating():
                dialogs.ErrorDialog(_("Runtime currently updating"), _("Game might not work as expected"))
        if ("wine" in self.runner_name and not wine.get_wine_version() and not LINUX_SYSTEM.is_flatpak):
            dialogs.WineNotInstalledWarning(parent=None)
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
        if not system.find_executable("Xephyr"):
            raise GameConfigError("Unable to find Xephyr, install it or disable the Xephyr option")
        xephyr_command = get_xephyr_command(display, self.runner.system_config)
        xephyr_thread = MonitoredCommand(xephyr_command)
        xephyr_thread.start()
        time.sleep(3)
        return display

    def start_antimicrox(self, antimicro_config):
        """Start Antimicrox with a given config path"""
        antimicro_path = system.find_executable("antimicrox")
        if not antimicro_path:
            logger.warning("Antimicrox is not installed.")
            return
        logger.info("Starting Antic")
        antimicro_command = [antimicro_path, "--hidden", "--tray", "--profile", antimicro_config]
        self.antimicro_thread = MonitoredCommand(antimicro_command)
        self.antimicro_thread.start()

    @staticmethod
    def set_keyboard_layout(layout):
        setxkbmap_command = ["setxkbmap", "-model", "pc101", layout, "-print"]
        xkbcomp_command = ["xkbcomp", "-", os.environ.get("DISPLAY", ":0")]
        with subprocess.Popen(xkbcomp_command, stdin=subprocess.PIPE) as xkbcomp:
            with subprocess.Popen(setxkbmap_command, env=os.environ, stdout=xkbcomp.stdin) as setxkbmap:
                setxkbmap.communicate()
                xkbcomp.communicate()

    def start_prelaunch_command(self, wait_for_completion=False):
        """Start the prelaunch command specified in the system options"""
        prelaunch_command = self.runner.system_config.get("prelaunch_command")
        command_array = shlex.split(prelaunch_command)
        if not system.path_exists(command_array[0]):
            logger.warning("Command %s not found", command_array[0])
            return
        env = self.game_runtime_config["env"]
        if wait_for_completion:
            logger.info("Prelauch command: %s, waiting for completion", prelaunch_command)
            # Monitor the prelaunch command and wait until it has finished
            system.execute(command_array, env=env, cws=self.directory)
        else:
            logger.info("Prelaunch command %s launched in the background", prelaunch_command)
            self.prelaunch_executor = MonitoredCommand(
                command_array,
                include_processes=[os.path.basename(command_array[0])],
                env=env,
                cwd=self.directory,
            )
            self.prelaunch_executor.start()

    def get_terminal(self):
        """Return the terminal used to run the game into or None if the game is not run from a terminal.
        Remember that only games using text mode should use the terminal.
        """
        if self.runner.system_config.get("terminal"):
            terminal = self.runner.system_config.get("terminal_app", linux.get_default_terminal())
            if terminal and not system.find_executable(terminal):
                raise GameConfigError(_("The selected terminal application could not be launched:\n%s") % terminal)
            return terminal

    def get_killswitch(self):
        """Return the path to a file that is monitored during game execution.
        If the file stops existing, the game is stopped.
        """
        killswitch = self.runner.system_config.get("killswitch")
        # Prevent setting a killswitch to a file that doesn't exists
        if killswitch and system.path_exists(self.killswitch):
            return killswitch

    def get_gameplay_info(self):
        """Return the information provided by a runner's play method.
        Checks for possible errors.
        """
        if not self.runner:
            logger.warning("Trying to launch %s without a runner", self)
            return {}
        gameplay_info = self.runner.play()
        if self.config.game_level.get("game", {}).get("launch_configs"):
            configs = self.config.game_level["game"]["launch_configs"]
            dlg = dialogs.LaunchConfigSelectDialog(self, configs)
            if dlg.config_index:
                config = configs[dlg.config_index - 1]
                gameplay_info["command"] = [gameplay_info["command"][0], config["exe"]]
                if config.get("args"):
                    gameplay_info["command"] += strings.split_arguments(config["args"])

        if "error" in gameplay_info:
            self.show_error_message(gameplay_info)
            self.state = self.STATE_STOPPED
            self.emit("game-stop")
            return
        return gameplay_info

    @watch_lutris_errors
    def configure_game(self, prelaunched, error=None):  # noqa: C901
        """Get the game ready to start, applying all the options
        This methods sets the game_runtime_config attribute.
        """
        if error:
            logger.error(error)
            dialogs.ErrorDialog(str(error))
        if not prelaunched:
            logger.error("Game prelaunch unsuccessful")
            dialogs.ErrorDialog(_("An error prevented the game from running"))
            self.state = self.STATE_STOPPED
            self.emit("game-stop")
            return
        gameplay_info = self.get_gameplay_info()
        if not gameplay_info:
            return
        command, env = get_launch_parameters(self.runner, gameplay_info)
        env["game_name"] = self.name  # What is this used for??
        self.game_runtime_config = {
            "args": command,
            "env": env,
            "terminal": self.get_terminal(),
            "include_processes": shlex.split(self.runner.system_config.get("include_processes", "")),
            "exclude_processes": shlex.split(self.runner.system_config.get("exclude_processes", "")),
        }

        # Audio control
        if self.runner.system_config.get("reset_pulse"):
            audio.reset_pulse()

        # Input control
        if self.runner.system_config.get("use_us_layout"):
            self.set_keyboard_layout("us")

        # Display control
        self.original_outputs = DISPLAY_MANAGER.get_config()

        if self.runner.system_config.get("disable_compositor"):
            self.set_desktop_compositing(False)

        if self.runner.system_config.get("disable_screen_saver"):
            self.screen_saver_inhibitor_cookie = SCREEN_SAVER_INHIBITOR.inhibit(self.name)

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

        self.start_game()

    def launch(self):
        """Request launching a game. The game may not be installed yet."""
        if not self.is_launchable():
            logger.error("Game is not launchable")
            return

        self.load_config()  # Reload the config before launching it.

        if str(self.id) in LOG_BUFFERS:  # Reset game logs on each launch
            log_buffer = LOG_BUFFERS[str(self.id)]
            log_buffer.delete(log_buffer.get_start_iter(), log_buffer.get_end_iter())

        self.state = self.STATE_LAUNCHING
        self.prelaunch_pids = system.get_running_pid_list()
        self.emit("game-start")
        jobs.AsyncCall(self.runner.prelaunch, self.configure_game)

    def start_game(self):
        """Run a background command to lauch the game"""
        self.game_thread = MonitoredCommand(
            self.game_runtime_config["args"],
            title=self.name,
            runner=self.runner,
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
        self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.beat)
        with open(self.now_playing_path, "w", encoding="utf-8") as np_file:
            np_file.write(self.name)

    def force_stop(self):
        # If SIGTERM fails, wait a few seconds and try SIGKILL on any survivors
        if self.kill_processes(signal.SIGTERM):
            self.stop_game()
        else:
            self.force_kill_delayed()

    def force_kill_delayed(self, death_watch_seconds=5, death_watch_interval_seconds=.5):
        """Forces termination of a running game, but only after a set time has elapsed;
        Invokes stop_game() when the game is dead."""

        def death_watch():
            """Wait for the processes to die; returns True if do they all did."""
            for _n in range(int(death_watch_seconds / death_watch_interval_seconds)):
                time.sleep(death_watch_interval_seconds)
                if not self.get_stop_pids():
                    return True
            return False

        def death_watch_cb(all_died, error):
            """Called after the death watch to more firmly kill any survivors."""
            if error:
                dialogs.ErrorDialog(str(error))
            elif not all_died:
                self.kill_processes(signal.SIGKILL)
            # If we still can't kill everything, we'll still say we stopped it.
            self.stop_game()

        jobs.AsyncCall(death_watch, death_watch_cb)

    def kill_processes(self, sig):
        """Sends a signal to a process list, logging errors. Returns True if
        there were surviving processes afterwards, False if all are dead."""
        pids = self.get_stop_pids()

        if not pids:
            return False

        for pid in pids:
            try:
                os.kill(int(pid), sig)
            except ProcessLookupError as ex:
                logger.debug("Failed to kill game process: %s", ex)
        return len(self.get_stop_pids()) == 0

    def get_stop_pids(self):
        """Finds the PIDs of processes that need killin'!"""
        pids = self.get_game_pids()
        if self.game_thread and self.game_thread.game_process:
            pids.add(self.game_thread.game_process.pid)
        return pids

    def get_game_pids(self):
        """Return a list of processes belonging to the Lutris game"""
        new_pids = self.get_new_pids()
        game_pids = []
        game_folder = self.runner.game_path or ""
        for pid in new_pids:
            cmdline = Process(pid).cmdline or ""
            # pressure-vessel: This could potentially pick up PIDs not started by lutris?
            if game_folder in cmdline or "pressure-vessel" in cmdline:
                game_pids.append(pid)
        return set(game_pids + [
            pid for pid in new_pids
            if Process(pid).environ.get("LUTRIS_GAME_UUID") == self.game_uuid
        ])

    def get_new_pids(self):
        """Return list of PIDs started since the game was launched"""
        return set(system.get_running_pid_list()) - set(self.prelaunch_pids)

    def stop_game(self):
        """Cleanup after a game as stopped"""
        duration = self.timer.duration
        logger.debug("%s has run for %s seconds", self, duration)
        if duration < 5:
            logger.warning("The game has run for a very short time, did it crash?")
            # Inspect why it could have crashed

        self.state = self.STATE_STOPPED
        self.emit("game-stop")
        if os.path.exists(self.now_playing_path):
            os.unlink(self.now_playing_path)
        if not self.timer.finished:
            self.timer.end()
            self.playtime += self.timer.duration / 3600

    def prelaunch_beat(self):
        """Watch the prelaunch command"""
        if self.prelaunch_executor and self.prelaunch_executor.is_running:
            return True
        self.start_game()
        return False

    def beat(self):
        """Watch the game's process(es)."""
        if self.game_thread.error:
            dialogs.ErrorDialog(_("<b>Error lauching the game:</b>\n") + self.game_thread.error)
            self.on_game_quit()
            return False

        # The killswitch file should be set to a device (ie. /dev/input/js0)
        # When that device is unplugged, the game is forced to quit.
        killswitch_engage = self.killswitch and not system.path_exists(self.killswitch)
        if killswitch_engage:
            logger.warning("File descriptor no longer present, force quit the game")
            self.force_stop()
            return False
        game_pids = self.get_game_pids()
        if not self.game_thread.is_running and not game_pids:
            logger.debug("Game thread stopped")
            self.on_game_quit()
            return False
        return True

    def stop(self):
        """Stops the game"""
        if self.state == self.STATE_STOPPED:
            logger.debug("Game already stopped")
            return

        logger.info("Stopping %s", self)

        if self.game_thread:
            jobs.AsyncCall(self.game_thread.stop, None)
        self.stop_game()

    def on_game_quit(self):
        """Restore some settings and cleanup after game quit."""

        if self.prelaunch_executor and self.prelaunch_executor.is_running:
            logger.info("Stopping prelaunch script")
            self.prelaunch_executor.stop()

        self.heartbeat = None
        if self.state != self.STATE_STOPPED:
            logger.warning("Game still running (state: %s)", self.state)
            self.stop()

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
                    cwd=self.directory,
                )
                postexit_thread.start()

        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.name, quit_time)
        self.lastplayed = int(time.time())
        self.save(save_config=False)

        os.chdir(os.path.expanduser("~"))

        if self.antimicro_thread:
            self.antimicro_thread.stop()

        if self.resolution_changed or self.runner.system_config.get("reset_desktop"):
            DISPLAY_MANAGER.set_resolution(self.original_outputs)

        if self.compositor_disabled:
            self.set_desktop_compositing(True)

        if self.screen_saver_inhibitor_cookie is not None:
            SCREEN_SAVER_INHIBITOR.uninhibit(self.screen_saver_inhibitor_cookie)
            self.screen_saver_inhibitor_cookie = None

        if self.runner.system_config.get("use_us_layout"):
            with subprocess.Popen(["setxkbmap"], env=os.environ) as setxkbmap:
                setxkbmap.communicate()

        if self.runner.system_config.get("restore_gamma"):
            restore_gamma()

        self.process_return_codes()

    def process_return_codes(self):
        """Do things depending on how the game quitted."""
        if self.game_thread.return_code == 127:
            # Error missing shared lib
            error = "error while loading shared lib"
            error_line = strings.lookup_string_in_text(error, self.game_thread.stdout)
            if error_line:
                dialogs.ErrorDialog(_("<b>Error: Missing shared library.</b>\n\n%s") % error_line)

        if self.game_thread.return_code == 1:
            # Error Wine version conflict
            error = "maybe the wrong wineserver"
            if strings.lookup_string_in_text(error, self.game_thread.stdout):
                dialogs.ErrorDialog(_("<b>Error: A different Wine version is already using the same Wine prefix.</b>"))

    def write_script(self, script_path):
        """Output the launch argument in a bash script"""
        gameplay_info = self.get_gameplay_info()
        if not gameplay_info:
            logger.error("Unable to retrieve game information for %s. Can't write a script", self)
            return
        export_bash_script(self.runner, gameplay_info, script_path)

    def move(self, new_location):
        logger.info("Moving %s to %s", self, new_location)
        new_config = ""
        old_location = self.directory
        if os.path.exists(old_location):
            game_directory = os.path.basename(old_location)
            target_directory = os.path.join(new_location, game_directory)
        else:
            target_directory = new_location
        self.directory = target_directory
        self.save()
        if not old_location:
            logger.info("Previous location wasn't set. Cannot continue moving")
            return target_directory

        with open(self.config.game_config_path, encoding='utf-8') as config_file:
            for line in config_file.readlines():
                if target_directory in line:
                    new_config += line
                else:
                    new_config += line.replace(old_location, target_directory)
        with open(self.config.game_config_path, "w", encoding='utf-8') as config_file:
            config_file.write(new_config)

        if not system.path_exists(old_location):
            logger.warning("Location %s doesn't exist, files already moved?", old_location)
            return target_directory
        if new_location.startswith(old_location):
            logger.warning("Can't move %s to one of its children %s", old_location, new_location)
            return target_directory
        try:
            shutil.move(old_location, new_location)
        except OSError as ex:
            logger.error(
                "Failed to move %s to %s, you may have to move files manually (Exception: %s)",
                old_location, new_location, ex
            )
        return target_directory
