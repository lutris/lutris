"""Module that actually runs the games."""

# pylint: disable=too-many-public-methods
import os
import shlex
import subprocess
import time
from gettext import gettext as _

from gi.repository import GLib, GObject, Gtk

from lutris import pga, runtime
from lutris.command import MonitoredCommand
from lutris.config import LutrisConfig
from lutris.discord import DiscordPresence
from lutris.exceptions import GameConfigError, watch_lutris_errors
from lutris.gui import dialogs
from lutris.runners import InvalidRunner, import_runner, wine
from lutris.settings import DEFAULT_DISCORD_CLIENT_ID
from lutris.util import audio, jobs, strings, system, xdgshortcuts
from lutris.util.display import DISPLAY_MANAGER, disable_compositing, enable_compositing, restore_gamma
from lutris.util.graphics.xrandr import turn_off_except
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.timer import Timer

HEARTBEAT_DELAY = 2000


class Game(GObject.Object):

    """This class takes cares of loading the configuration for a game
       and running it.
    """

    STATE_IDLE = "idle"
    STATE_STOPPED = "stopped"
    STATE_RUNNING = "running"

    __gsignals__ = {
        "game-error": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "game-start": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-started": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-stop": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-stopped": (GObject.SIGNAL_RUN_FIRST, None, (int, )),
        "game-removed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-updated": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, game_id=None):
        super().__init__()
        self.id = game_id  # pylint: disable=invalid-name
        self.runner = None
        self.config = None

        # Load attributes from database
        game_data = pga.get_game_by_field(game_id, "id")
        self.slug = game_data.get("slug") or ""
        self.runner_name = game_data.get("runner") or ""
        self.directory = game_data.get("directory") or ""
        self.name = game_data.get("name") or ""

        self.game_config_id = game_data.get("configpath") or ""
        self.is_installed = bool(game_data.get("installed") and self.game_config_id)
        self.platform = game_data.get("platform") or ""
        self.year = game_data.get("year") or ""
        self.lastplayed = game_data.get("lastplayed") or 0
        self.steamid = game_data.get("steamid") or ""
        self.has_custom_banner = bool(game_data.get("has_custom_banner"))
        self.has_custom_icon = bool(game_data.get("has_custom_icon"))
        self.discord_presence = DiscordPresence()
        try:
            self.playtime = float(game_data.get("playtime") or 0.0)
        except ValueError:
            logger.error("Invalid playtime value %s", game_data.get("playtime"))
            self.playtime = 0.0

        if self.game_config_id:
            self.load_config()
        self.game_thread = None
        self.prelaunch_executor = None
        self.heartbeat = None
        self.killswitch = None
        self.state = self.STATE_IDLE
        self.game_runtime_config = {}
        self.resolution_changed = False
        self.compositor_disabled = False
        self.original_outputs = None
        self._log_buffer = None
        self.timer = Timer()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        value = self.name
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    @property
    def log_buffer(self):
        """Access the log buffer object, creating it if necessary"""
        if self._log_buffer is None:
            self._log_buffer = Gtk.TextBuffer()
            self._log_buffer.create_tag("warning", foreground="red")
            if self.game_thread:
                self.game_thread.set_log_buffer(self._log_buffer)
                self._log_buffer.set_text(self.game_thread.stdout)
        return self._log_buffer

    @property
    def formatted_playtime(self):
        """Return a human readable formatted play time"""
        return strings.get_formatted_playtime(self.playtime)

    @property
    def is_search_result(self):
        """Return whether or not the game is a remote game from search results.
        This is bad, find another way to do this.
        """
        return self.id < 0

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
                message_text = _("No file provided")
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
        if self.discord_presence.available:
            self.discord_presence.client_id = (
                self.config.system_config.get("discord_client_id") or DEFAULT_DISCORD_CLIENT_ID
            )
            self.discord_presence.game_name = (self.config.system_config.get("discord_custom_game_name") or self.name)
            self.discord_presence.show_runner = self.config.system_config.get("discord_show_runner", True)
            self.discord_presence.runner_name = (
                self.config.system_config.get("discord_custom_runner_name") or self.runner_name
            )
            self.discord_presence.rpc_enabled = self.config.system_config.get("discord_rpc_enabled", True)

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

    def remove(self, from_library=False, from_disk=False):
        """Uninstall a game

        Params:
            from_library (bool): Completely remove the game from library, do
                                 not set it as uninstalled
            from_disk (bool): Delete the game files

        Return:
            bool: Updated value for from_library
        """
        if from_disk and self.runner:
            logger.debug("Removing game %s from disk", self.id)
            self.runner.remove_game_data(game_path=self.directory)

        # Do not keep multiple copies of the same game
        existing_games = pga.get_games_where(slug=self.slug)
        if len(existing_games) > 1:
            from_library = True

        if from_library:
            logger.debug("Removing game %s from library", self.id)
            pga.delete_game(self.id)
        else:
            pga.set_uninstalled(self.id)
        if self.config:
            self.config.remove()
        xdgshortcuts.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        self.is_installed = False
        self.emit("game-removed")
        return from_library

    def set_platform_from_runner(self):
        """Set the game's platform from the runner"""
        if not self.runner:
            logger.warning("Game has no runner, can't set platform")
            return
        self.platform = self.runner.get_platform()
        if not self.platform:
            logger.warning("Can't get platform for runner %s", self.runner.human_name)

    def save(self, metadata_only=False):
        """
        Save the game's config and metadata, if `metadata_only` is set to True,
        do not save the config. This is useful when exiting the game since the
        config might have changed and we don't want to override the changes.
        """
        logger.debug("Saving %s", self)
        if not metadata_only:
            self.config.save()
        self.set_platform_from_runner()
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
            id=self.id,
            playtime=self.playtime,
        )
        self.emit("game-updated")

    def is_launchable(self):
        """Verify that the current game can be launched."""
        if not self.runner.is_installed():
            installed = self.runner.install_dialog()
            if not installed:
                return False

        if self.runner.use_runtime():
            runtime_updater = runtime.RuntimeUpdater()
            if runtime_updater.is_updating():
                logger.warning("Runtime updates: %s", runtime_updater.current_updates)
                dialogs.ErrorDialog(_("Runtime currently updating"), _("Game might not work as expected"))
        if ("wine" in self.runner_name and not wine.get_system_wine_version() and not LINUX_SYSTEM.is_flatpak):
            # TODO find a reference to the root window or better yet a way not
            # to have Gtk dependent code in this class.
            root_window = None
            dialogs.WineNotInstalledWarning(parent=root_window)
        return True

    def play(self):
        """Launch the game."""
        if not self.runner:
            dialogs.ErrorDialog(_("Invalid game configuration: Missing runner"))
            self.state = self.STATE_STOPPED
            self.emit("game-stop")
            return

        if not self.is_launchable():
            self.state = self.STATE_STOPPED
            self.emit("game-stop")
            return

        self.emit("game-start")
        jobs.AsyncCall(self.runner.prelaunch, self.configure_game)

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

    def get_launch_parameters(self, gameplay_info):
        system_config = self.runner.system_config
        launch_arguments = gameplay_info["command"]

        optimus = system_config.get("optimus")
        if optimus == "primusrun" and system.find_executable("primusrun"):
            launch_arguments.insert(0, "primusrun")
        elif optimus == "optirun" and system.find_executable("optirun"):
            launch_arguments.insert(0, "virtualgl")
            launch_arguments.insert(0, "-b")
            launch_arguments.insert(0, "optirun")
        elif optimus == "pvkrun" and system.find_executable("pvkrun"):
            launch_arguments.insert(0, "pvkrun")

        # Mangohud activation
        mangohud = system_config.get("mangohud") or ""
        if mangohud and system.find_executable("mangohud"):
            # This is probably not the way to go. This only work with a few
            # Wine games. It will probably crash it, or do nothing at all.
            # I have never got mangohud to work on anything other than a Wine
            # game.
            dialogs.NoticeDialog("MangoHud support is experimental. Expect the "
                                 "game to crash or the framerate counter not to "
                                 "appear at all.")
            launch_arguments = ["mangohud"] + launch_arguments

        fps_limit = system_config.get("fps_limit") or ""
        if fps_limit:
            strangle_cmd = system.find_executable("strangle")
            if strangle_cmd:
                launch_arguments = [strangle_cmd, fps_limit] + launch_arguments
            else:
                logger.warning("libstrangle is not available on this system, FPS limiter disabled")

        prefix_command = system_config.get("prefix_command") or ""
        if prefix_command:
            launch_arguments = (shlex.split(os.path.expandvars(prefix_command)) + launch_arguments)

        single_cpu = system_config.get("single_cpu") or False
        if single_cpu:
            logger.info("The game will run on a single CPU core")
            launch_arguments.insert(0, "0")
            launch_arguments.insert(0, "-c")
            launch_arguments.insert(0, "taskset")


        env = {}
        env.update(self.runner.get_env())
        env.update(gameplay_info.get("env") or {})
        env["game_name"] = self.name

        # Set environment variables dependent on gameplay info

        # LD_PRELOAD
        ld_preload = gameplay_info.get("ld_preload")
        if ld_preload:
            env["LD_PRELOAD"] = ld_preload

        # LD_LIBRARY_PATH
        game_ld_libary_path = gameplay_info.get("ld_library_path")
        if game_ld_libary_path:
            ld_library_path = env.get("LD_LIBRARY_PATH")
            if not ld_library_path:
                ld_library_path = "$LD_LIBRARY_PATH"
            env["LD_LIBRARY_PATH"] = ":".join([game_ld_libary_path, ld_library_path])

        # Feral gamemode
        gamemode = system_config.get("gamemode") and LINUX_SYSTEM.gamemode_available()
        if gamemode:
            if system.find_executable("gamemoderun"):
                launch_arguments.insert(0, "gamemoderun")
            else:
                env["LD_PRELOAD"] = ":".join([path for path in [
                    env.get("LD_PRELOAD"),
                    "libgamemodeauto.so",
                ] if path])
        return launch_arguments, env

    def start_xephyr(self, display=":2"):
        """Start a monitored Xephyr instance"""
        if not system.find_executable("Xephyr"):
            raise GameConfigError("Unable to find Xephyr, install it or disable the Xephyr option")

        xephyr_depth = "8" if self.runner.system_config.get("xephyr") == "8bpp" else "16"
        xephyr_resolution = self.runner.system_config.get("xephyr_resolution") or "640x480"
        xephyr_command = [
            "Xephyr",
            display,
            "-ac",
            "-screen",
            xephyr_resolution + "x" + xephyr_depth,
            "-glamor",
            "-reset",
            "-terminate",
        ]
        if self.runner.system_config.get("xephyr_fullscreen"):
            xephyr_command.append("-fullscreen")

        xephyr_thread = MonitoredCommand(xephyr_command)
        xephyr_thread.start()
        time.sleep(3)
        return display

    @staticmethod
    def set_keyboard_layout(layout):
        setxkbmap_command = ["setxkbmap", "-model", "pc101", layout, "-print"]
        xkbcomp_command = ["xkbcomp", "-", os.environ.get("DISPLAY", ":0")]
        xkbcomp = subprocess.Popen(xkbcomp_command, stdin=subprocess.PIPE)
        subprocess.Popen(setxkbmap_command, env=os.environ, stdout=xkbcomp.stdin).communicate()
        xkbcomp.communicate()

    def start_prelaunch_command(self):
        """Start the prelaunch command specified in the system options"""
        prelaunch_command = self.runner.system_config.get("prelaunch_command")
        command_array = shlex.split(prelaunch_command)
        if not system.path_exists(command_array[0]):
            logger.warning("Command %s not found", command_array[0])
            return
        self.prelaunch_executor = MonitoredCommand(
            command_array,
            include_processes=[os.path.basename(command_array[0])],
            env=self.game_runtime_config["env"],
            cwd=self.directory,
        )
        self.prelaunch_executor.start()
        logger.info("Running %s in the background", prelaunch_command)

    def get_terminal(self):
        """Return the terminal used to run the game into or None if the game is not run from a terminal.
        Remember that only games using text mode should use the terminal.
        """
        if self.system_config.get("terminal"):
            terminal = self.system_config.get("terminal_app", system.get_default_terminal())
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
        gameplay_info = self.runner.play()
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
        command, env = self.get_launch_parameters(gameplay_info)
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

        if self.system_config.get("use_us_layout"):
            self.set_keyboard_layout("us")

        # Display control

        self.original_outputs = DISPLAY_MANAGER.get_config()

        if self.runner.system_config.get("disable_compositor"):
            self.set_desktop_compositing(False)

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

        # Execution control

        self.killswitch = self.get_killswitch()

        if self.runner.system_config.get("prelaunch_command"):
            self.start_prelaunch_command()

        if self.runner.system_config.get("prelaunch_wait"):
            # Monitor the prelaunch command and wait until it has finished
            self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.prelaunch_beat)
        else:
            self.start_game()

    def start_game(self):
        """Run a background command to lauch the game"""
        self.game_thread = MonitoredCommand(
            self.game_runtime_config["args"],
            title=self.name,
            runner=self.runner,
            env=self.game_runtime_config["env"],
            term=self.game_runtime_config["terminal"],
            log_buffer=self._log_buffer,
            include_processes=self.game_runtime_config["include_processes"],
            exclude_processes=self.game_runtime_config["exclude_processes"],
        )
        if hasattr(self.runner, "stop"):
            self.game_thread.stop_func = self.runner.stop
        self.game_thread.start()
        self.timer.start()
        self.emit("game-started")
        self.state = self.STATE_RUNNING
        self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.beat)

    def stop_game(self):
        """Cleanup after a game as stopped"""
        self.state = self.STATE_STOPPED
        self.emit("game-stop")
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
        if not self.game_thread.is_running or killswitch_engage:
            logger.debug("Game thread stopped")
            self.on_game_quit()
            return False

        if self.discord_presence.available:
            self.discord_presence.update_discord_rich_presence()

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

        if self.discord_presence.available:
            self.discord_presence.clear_discord_rich_presence()

        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.name, quit_time)
        self.lastplayed = int(time.time())
        self.save(metadata_only=True)

        os.chdir(os.path.expanduser("~"))

        if self.resolution_changed or self.runner.system_config.get("reset_desktop"):
            DISPLAY_MANAGER.set_resolution(self.original_outputs)

        if self.compositor_disabled:
            self.set_desktop_compositing(True)

        if self.runner.system_config.get("use_us_layout"):
            subprocess.Popen(["setxkbmap"], env=os.environ).communicate()

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

    def notify_steam_game_changed(self, appmanifest):
        """Receive updates from Steam games and set the thread's ready state accordingly"""
        if not self.game_thread:
            return
        if "Fully Installed" in appmanifest.states and not self.game_thread.ready_state:
            logger.info("Steam game %s is fully installed", appmanifest.steamid)
            self.game_thread.ready_state = True
        elif "Update Required" in appmanifest.states and self.game_thread.ready_state:
            logger.info(
                "Steam game %s updating, setting game thread as not ready",
                appmanifest.steamid,
            )
            self.game_thread.ready_state = False
