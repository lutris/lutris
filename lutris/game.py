"""Module that actually runs the games."""

# pylint: disable=too-many-public-methods disable=too-many-lines
import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from gettext import gettext as _
from typing import cast

from gi.repository import Gio, GLib, Gtk

from lutris import settings
from lutris.config import LutrisConfig
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exception_backstops import watch_game_errors
from lutris.exceptions import GameConfigError, InvalidGameMoveError, MissingExecutableError
from lutris.gui.widgets import NotificationSource
from lutris.installer import InstallationKind
from lutris.monitored_command import MonitoredCommand
from lutris.runner_interpreter import export_bash_script, get_launch_parameters
from lutris.runners import import_runner, is_valid_runner_name
from lutris.runners.runner import Runner
from lutris.util import discord, extract, jobs, linux, strings, system, xdgshortcuts
from lutris.util.display import DISPLAY_MANAGER, SCREEN_SAVER_INHIBITOR, disable_compositing, enable_compositing
from lutris.util.graphics.xephyr import get_xephyr_command
from lutris.util.graphics.xrandr import turn_off_except
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import LOG_BUFFERS, logger
from lutris.util.process import Process
from lutris.util.steam.shortcut import remove_shortcut as remove_steam_shortcut
from lutris.util.system import fix_path_case
from lutris.util.timer import Timer
from lutris.util.wine import proton
from lutris.util.yaml import write_yaml_to_file

HEARTBEAT_DELAY = 2000

GAME_START = NotificationSource()
GAME_STARTED = NotificationSource()
GAME_STOPPED = NotificationSource()
GAME_UPDATED = NotificationSource()
GAME_INSTALLED = NotificationSource()
GAME_UNHANDLED_ERROR = NotificationSource()


class Game:
    """This class takes cares of loading the configuration for a game
    and running it.
    """

    now_playing_path = os.path.join(settings.CACHE_DIR, "now-playing.txt")

    STATE_STOPPED = "stopped"
    STATE_LAUNCHING = "launching"
    STATE_RUNNING = "running"

    PRIMARY_LAUNCH_CONFIG_NAME = "(primary)"

    def __init__(self, game_id: str = None):
        super().__init__()

        self.game_error = NotificationSource()

        self._id = str(game_id) if game_id else None  # pylint: disable=invalid-name

        # Load attributes from database
        game_data = games_db.get_game_by_field(game_id, "id")

        self.slug = game_data.get("slug") or ""
        self._runner_name = game_data.get("runner") or ""
        self.directory = game_data.get("directory") or ""
        self.name = game_data.get("name") or ""
        self.sortname = game_data.get("sortname") or ""
        self.game_config_id = game_data.get("configpath") or ""
        self.is_installed = bool(game_data.get("installed") and self.game_config_id)
        self.platform = game_data.get("platform") or ""
        self.year = game_data.get("year") or ""
        self.lastplayed = game_data.get("lastplayed") or 0
        self.custom_images = set()
        if game_data.get("has_custom_banner"):
            self.custom_images.add("banner")
        if game_data.get("has_custom_icon"):
            self.custom_images.add("icon")
        if game_data.get("has_custom_coverart_big"):
            self.custom_images.add("coverart_big")
        self.service = game_data.get("service")
        self.appid = game_data.get("service_id")
        try:
            self.playtime = float(game_data.get("playtime") or 0.0)
        except ValueError as ex:
            logger.exception("Unable to parse playtime '%s' for game %s: %s", game_data.get("playtime"), self.slug, ex)
            self.playtime = 0.0

        self.discord_id = game_data.get("discord_id")  # Discord App ID for RPC

        self._config = None
        self._runner = None

        self.game_uuid = None
        self.game_thread = None
        self.antimicro_thread = None
        self.prelaunch_pids = None
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

    @staticmethod
    def create_empty_service_game(db_game, service):
        """Creates a Game from the database data from ServiceGameCollection, which is
        not a real game, but which can be used to install. Such a game has no ID, but
        has an 'appid' and slug."""
        game = Game()
        game.name = db_game["name"]
        game.slug = service.get_installed_slug(db_game)
        game.runner_name = service.get_installed_runner_name(db_game)

        if "service_id" in db_game:
            game.appid = db_game["service_id"]
        elif service:
            game.appid = db_game["appid"]

        game.service = service.id if service else None
        return game

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        value = self.name or "Game (no name)"
        if self.runner_name:
            value += " (%s)" % self.runner_name
        return value

    @property
    def id(self) -> str:
        if not self._id:
            logger.error("The game '%s' has no ID, it is not stored in the database.", self.name)
        return cast(str, self._id)

    @property
    def is_db_stored(self) -> bool:
        """True if this Game has an ID, which means it is saved in the database."""
        return bool(self._id)

    @property
    def is_updatable(self):
        """Return whether the game can be upgraded"""
        return self.is_installed and self.service in ["gog", "itchio"]

    def get_categories(self):
        """Return the categories the game is in."""
        return categories_db.get_categories_in_game(self.id) if self.is_db_stored else []

    def update_game_categories(self, added_category_names, removed_category_names):
        """add to / remove from categories"""
        for added_category_name in added_category_names:
            self.add_category(added_category_name, no_signal=True)

        for removed_category_name in removed_category_names:
            self.remove_category(removed_category_name, no_signal=True)

        GAME_UPDATED.fire(self)

    def add_category(self, category_name, no_signal=False):
        """add game to category"""
        if not self.is_db_stored:
            raise RuntimeError("Games that do not have IDs cannot belong to categories.")

        category = categories_db.get_category(category_name)
        if category is None:
            category_id = categories_db.add_category(category_name)
        else:
            category_id = category["id"]
        categories_db.add_game_to_category(self.id, category_id)

        if not no_signal:
            GAME_UPDATED.fire(self)

    def remove_category(self, category_name, no_signal=False):
        """remove game from category"""
        if not self.is_db_stored:
            return

        category = categories_db.get_category(category_name)
        if category is None:
            return
        category_id = category["id"]
        categories_db.remove_category_from_game(self.id, category_id)

        if not no_signal:
            GAME_UPDATED.fire(self)

    @property
    def is_favorite(self) -> bool:
        """Return whether the game is in the user's favorites"""
        return "favorite" in self.get_categories()

    def mark_as_favorite(self, is_favorite: bool) -> None:
        """Place the game in the favorite's category, or remove it.
        This change is applied at once, and does not need to be saved."""
        if self.is_favorite != bool(is_favorite):
            if is_favorite:
                self.add_category("favorite")
            else:
                self.remove_category("favorite")

    @property
    def is_hidden(self) -> bool:
        """Return whether the game is in the user's favorites"""
        return ".hidden" in self.get_categories()

    def mark_as_hidden(self, is_hidden: bool) -> None:
        """Place the game in the hidden category, or remove it.
        This change is applied at once, and does not need to be saved."""
        if self.is_hidden != bool(is_hidden):
            if is_hidden:
                self.add_category(".hidden")
            else:
                self.remove_category(".hidden")

    @property
    def log_buffer(self):
        """Access the log buffer object, creating it if necessary"""
        _log_buffer = LOG_BUFFERS.get(self.id)
        if _log_buffer:
            return _log_buffer
        _log_buffer = Gtk.TextBuffer()
        _log_buffer.create_tag("warning", foreground="red")
        if self.game_thread:
            self.game_thread.set_log_buffer(self._log_buffer)
            _log_buffer.set_text(self.game_thread.stdout)
        LOG_BUFFERS[self.id] = _log_buffer
        return _log_buffer

    @property
    def formatted_playtime(self):
        """Return a human-readable formatted play time"""
        return strings.get_formatted_playtime(self.playtime)

    def signal_error(self, error):
        """Reports an error by firing game_error. If there is no handler for this,
        we fall back to the global GAME_UNHANDLED_ERROR.

        This allows special error handling to be set up for a particular Game, but
        there's always some global handling."""

        if self.game_error.has_handlers:
            self.game_error.fire(error)
        else:
            GAME_UNHANDLED_ERROR.fire(self, error)

    def get_browse_dir(self):
        """Return the path to open with the Browse Files action."""
        return self.resolve_game_path()

    def resolve_game_path(self):
        """Return the game's directory; if it is not known this will try to find
        it. This can still return an empty string if it can't do that."""
        if self.directory:
            return os.path.expanduser(self.directory)  # expanduser just in case!
        if self.has_runner:
            return self.runner.resolve_game_path()
        return ""

    @property
    def config(self):
        if not self.is_installed or not self.game_config_id:
            return None
        if not self._config:
            self._config = LutrisConfig(runner_slug=self.runner_name, game_config_id=self.game_config_id)
        return self._config

    @config.setter
    def config(self, value):
        self._config = value
        self._runner = None
        if value:
            self.game_config_id = value.game_config_id

    def reload_config(self):
        """Triggers the config to reload when next used; this also reloads the runner,
        so that it will pick up the new configuration."""
        self._config = None
        self._runner = None

    @property
    def runner_name(self) -> str:
        return self._runner_name

    @runner_name.setter
    def runner_name(self, value: str) -> None:
        self._runner_name = value or ""
        if self._runner and self._runner.name != value:
            self._runner = None

    @property
    def has_runner(self) -> bool:
        return bool(self._runner_name and is_valid_runner_name(self._runner_name))

    @property
    def runner(self) -> Runner:
        if not self.has_runner:
            raise GameConfigError(_("Invalid game configuration: Missing runner"))

        if not self._runner:
            runner_class = import_runner(self.runner_name)
            self._runner = runner_class(self.config)
        return cast(Runner, self._runner)

    @runner.setter
    def runner(self, value: Runner) -> None:
        self._runner = value
        if value:
            self._runner_name = value.name

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

    def install(self, launch_ui_delegate):
        """Request installation of a game"""
        if not self.slug:
            raise ValueError("Invalid game passed: %s" % self)

        if not self.service or self.service == "lutris":
            application = Gio.Application.get_default()
            application.show_lutris_installer_window(game_slug=self.slug)
            return

        service = launch_ui_delegate.get_service(self.service)
        db_game = service.get_service_db_game(self)
        if not db_game:
            logger.error("Can't find %s for %s, trying to fall back to Lutris installers", self.name, service.name)
            application = Gio.Application.get_default()
            application.show_lutris_installer_window(game_slug=self.slug)
            return

        try:
            game_id = service.install(db_game)
        except ValueError as e:
            logger.debug(e)
            game_id = None

        if game_id:

            def on_error(error: BaseException) -> None:
                logger.exception("Unable to install game: %s", error)

            game = Game(game_id)
            game.game_error.register(on_error)
            game.launch(launch_ui_delegate)

    def install_updates(self, install_ui_delegate):
        service = install_ui_delegate.get_service(self.service)
        db_game = games_db.get_game_by_field(self.id, "id")

        def on_installers_ready(installers, error):
            if error:
                raise error  # bounce errors off the backstop

            if not installers:
                raise RuntimeError(_("No updates found"))

            application = Gio.Application.get_default()
            application.show_installer_window(
                installers, service, self.appid, installation_kind=InstallationKind.UPDATE
            )

        jobs.AsyncCall(service.get_update_installers, on_installers_ready, db_game)
        return True

    def install_dlc(self, install_ui_delegate):
        service = install_ui_delegate.get_service(self.service)
        db_game = games_db.get_game_by_field(self.id, "id")

        def on_installers_ready(installers, error):
            if error:
                raise error  # bounce errors off the backstop

            if not installers:
                raise RuntimeError(_("No DLC found"))

            application = Gio.Application.get_default()
            application.show_installer_window(installers, service, self.appid, installation_kind=InstallationKind.DLC)

        jobs.AsyncCall(service.get_dlc_installers_runner, on_installers_ready, db_game, db_game["runner"])
        return True

    def uninstall(self, delete_files: bool = False) -> None:
        """Uninstall a game, but do not remove it from the library.

        Params:
            delete_files (bool): Delete the game files
        """
        sql.db_update(settings.DB_PATH, "games", {"installed": 0, "runner": ""}, {"id": self.id})
        if self.config:
            self.config.remove()
        xdgshortcuts.remove_launcher(self.slug, self.id, desktop=True, menu=True)
        remove_steam_shortcut(self)
        if delete_files and self.has_runner:
            # self.directory here, not self.resolve_game_path; no guessing at
            # directories when we delete them
            self.runner.remove_game_data(app_id=self.appid, game_path=self.directory)
        self.is_installed = False
        self._config = None
        self._runner = None

        if self.id in LOG_BUFFERS:  # Reset game logs on removal
            log_buffer = LOG_BUFFERS[self.id]
            log_buffer.delete(log_buffer.get_start_iter(), log_buffer.get_end_iter())

    def delete(self) -> None:
        """Delete a game from the library; must be uninstalled first."""
        if self.is_installed:
            raise RuntimeError(_("Uninstall the game before deleting"))
        games_db.delete_game(self.id)
        self._id = None

    def set_platform_from_runner(self):
        """Set the game's platform from the runner"""
        if not self.has_runner:
            logger.warning("Game has no runner, can't set platform")
            return
        self.platform = self.runner.get_platform()
        if not self.platform:
            logger.warning("The %s runner didn't provide a platform for %s", self.runner.human_name, self)

    def save(self, no_signal=False):
        """
        Save the game's config and metadata.
        """
        if self.config:
            configpath = self.config.game_config_id
            logger.debug("Saving %s with config ID %s", self, self.config.game_config_id)
            self.config.save()
        else:
            logger.warning("Saving %s with the configuration missing", self)
            configpath = ""
        self.set_platform_from_runner()

        game_data = {
            "name": self.name,
            "sortname": self.sortname,
            "runner": self.runner_name,
            "slug": self.slug,
            "platform": self.platform,
            "directory": self.directory,
            "installed": self.is_installed,
            "year": self.year,
            "lastplayed": self.lastplayed,
            "configpath": configpath,
            "id": self.id,
            "playtime": self.playtime,
            "service": self.service,
            "service_id": self.appid,
            "discord_id": self.discord_id,
            "has_custom_banner": "banner" in self.custom_images,
            "has_custom_icon": "icon" in self.custom_images,
            "has_custom_coverart_big": "coverart_big" in self.custom_images,
        }
        self._id = str(games_db.add_or_update(**game_data))
        if not no_signal:
            GAME_UPDATED.fire(self)

    def save_platform(self):
        """Save only the platform field- do not restore any other values the user may have changed
        in another window."""
        games_db.update_existing(id=self.id, slug=self.slug, platform=self.platform)
        GAME_UPDATED.fire(self)

    def save_lastplayed(self):
        """Save only the lastplayed field- do not restore any other values the user may have changed
        in another window."""
        games_db.update_existing(id=self.id, slug=self.slug, lastplayed=self.lastplayed, playtime=self.playtime)
        GAME_UPDATED.fire(self)

    def check_launchable(self):
        """Verify that the current game can be launched, and raises exceptions if not."""
        if not self.is_installed or not self.is_db_stored:
            logger.error("%s (%s) not installed", self, self.id)
            raise GameConfigError(_("Tried to launch a game that isn't installed."))
        if not self.has_runner:
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
        xephyr_command = get_xephyr_command(display, self.runner.system_config)
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
        prelaunch_command = self.runner.system_config.get("prelaunch_command")
        command_array = shlex.split(prelaunch_command)
        if not system.path_exists(command_array[0]):
            logger.warning("Command %s not found", command_array[0])
            return
        env = self.game_runtime_config["env"]
        if wait_for_completion:
            logger.info("Prelauch command: %s, waiting for completion", prelaunch_command)
            # Monitor the prelaunch command and wait until it has finished
            system.execute(command_array, env=env, cwd=self.resolve_game_path())
        else:
            logger.info("Prelaunch command %s launched in the background", prelaunch_command)
            self.prelaunch_executor = MonitoredCommand(
                command_array,
                include_processes=[os.path.basename(command_array[0])],
                env=env,
                cwd=self.resolve_game_path(),
            )
            self.prelaunch_executor.start()

    def get_terminal(self):
        """Return the terminal used to run the game into or None if the game is not run from a terminal.
        Remember that only games using text mode should use the terminal.
        """
        if self.runner.system_config.get("terminal"):
            terminal = self.runner.system_config.get("terminal_app", linux.get_default_terminal())
            if terminal and not system.can_find_executable(terminal):
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

    def get_gameplay_info(self, launch_ui_delegate):
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

    def get_path_from_config(self):
        """Return the path of the main entry point for a game"""
        if not self.config:
            logger.warning("%s has no configuration", self)
            return ""
        game_config = self.config.game_config

        # Skip MAME roms referenced by their ID
        if self.runner_name == "mame":
            if "main_file" in game_config and "." not in game_config["main_file"]:
                return ""

        for key in ["exe", "main_file", "iso", "rom", "disk-a", "path", "files"]:
            if key in game_config:
                path = game_config[key]
                if key == "files":
                    path = path[0]

                if path:
                    path = os.path.expanduser(path)
                    if not path.startswith("/"):
                        path = os.path.join(self.directory, path)

                    # The Wine runner fixes case mismatches automatically,
                    # sort of like Windows, so we need to do the same.
                    if self.runner_name == "wine":
                        path = fix_path_case(path)

                    return path

        logger.warning("No path found in %s", self.config)
        return ""

    def get_store_name(self) -> str:
        store = self.service
        if not store:
            return "none"
        if self.service == "humblebundle":
            return "humble"
        return store

    @watch_game_errors(game_stop_result=False)
    def configure_game(self, launch_ui_delegate):
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
        env["GAMEID"] = proton.get_game_id(self)
        env["STORE"] = env.get("STORE") or self.get_store_name()

        if env.get("WINE") == proton.GE_PROTON_LATEST:
            env["PROTONPATH"] = "GE-Proton"

        # Some environment variables for the use of custom pre-launch and post-exit scripts.
        env["GAME_NAME"] = self.name
        if self.directory:
            env["GAME_DIRECTORY"] = self.directory

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
        return True

    @watch_game_errors(game_stop_result=False)
    def launch(self, launch_ui_delegate):
        """Request launching a game. The game may not be installed yet."""
        if not self.check_launchable():
            logger.error("Game is not launchable")
            return False

        if not launch_ui_delegate.check_game_launchable(self):
            return False

        self.reload_config()  # Reload the config before launching it.

        if self.id in LOG_BUFFERS:  # Reset game logs on each launch
            log_buffer = LOG_BUFFERS[self.id]
            log_buffer.delete(log_buffer.get_start_iter(), log_buffer.get_end_iter())

        self.state = self.STATE_LAUNCHING
        self.prelaunch_pids = system.get_running_pid_list()

        if not self.prelaunch_pids:
            logger.error("No prelaunch PIDs could be obtained. Game stop may be ineffective.")
            self.prelaunch_pids = None

        GAME_START.fire(self)

        @watch_game_errors(game_stop_result=False, game=self)
        def configure_game(_ignored, error):
            if error:
                raise error
            self.configure_game(launch_ui_delegate)

        jobs.AsyncCall(self.runner.prelaunch, configure_game)
        return True

    def start_game(self):
        """Run a background command to launch the game"""
        self.game_thread = MonitoredCommand(
            self.game_runtime_config["args"],
            title=self.name,
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
        GAME_STARTED.fire(self)

        # Game is running, let's update discord status
        if settings.read_setting("discord_rpc") == "True" and self.discord_id:
            try:
                discord.client.update(self.discord_id)
            except AssertionError:
                pass

        self.heartbeat = GLib.timeout_add(HEARTBEAT_DELAY, self.beat)
        with open(self.now_playing_path, "w", encoding="utf-8") as np_file:
            np_file.write(self.name)

    def force_stop(self):
        # If force_stop_game fails, wait a few seconds and try SIGKILL on any survivors

        def force_stop_game():
            self.runner.force_stop_game(self)
            return not self.get_stop_pids()

        def force_stop_game_cb(all_dead, error):
            if error:
                self.signal_error(error)
            elif all_dead:
                self.stop_game()
            else:
                self.force_kill_delayed()

        jobs.AsyncCall(force_stop_game, force_stop_game_cb)

    def force_kill_delayed(self, death_watch_seconds=5, death_watch_interval_seconds=0.5):
        """Forces termination of a running game, but only after a set time has elapsed;
        Invokes stop_game() when the game is dead."""

        def death_watch():
            """Wait for the processes to die; kill them if they do not."""
            for _n in range(int(death_watch_seconds / death_watch_interval_seconds)):
                time.sleep(death_watch_interval_seconds)
                if not self.get_stop_pids():
                    return

            # Once we get past the time limit, starting killing!
            self.kill_processes(signal.SIGKILL)

        def death_watch_cb(_result, error):
            """Called after the death watch to more firmly kill any survivors."""
            if error:
                self.signal_error(error)

            # If we still can't kill everything, we'll still say we stopped it.
            self.stop_game()

        jobs.AsyncCall(death_watch, death_watch_cb)

    def kill_processes(self, sig):
        """Sends a signal to a process list, logging errors."""
        pids = self.get_stop_pids()

        for pid in pids:
            try:
                os.kill(int(pid), sig)
            except ProcessLookupError as ex:
                logger.debug("Failed to kill game process: %s", ex)
            except PermissionError:
                logger.debug("Permission to kill process %s denied", pid)

    def get_stop_pids(self):
        """Finds the PIDs of processes that need killin'!"""
        pids = self.get_game_pids()
        if self.game_thread and self.game_thread.game_process:
            if self.game_thread.game_process.poll() is None:
                pids.add(self.game_thread.game_process.pid)
        return pids

    def get_game_pids(self):
        """Return a list of processes belonging to the Lutris game"""
        if not self.game_uuid:
            logger.error("No LUTRIS_GAME_UUID recorded. The game's PIDs cannot be computed.")
            return set()

        new_pids = self.get_new_pids()

        game_folder = self.resolve_game_path()
        folder_pids = set()
        for pid in new_pids:
            cmdline = Process(pid).cmdline or ""
            # pressure-vessel: This could potentially pick up PIDs not started by lutris?
            if game_folder in cmdline or "pressure-vessel" in cmdline:
                folder_pids.add(pid)

        uuid_pids = set(pid for pid in new_pids if Process(pid).environ.get("LUTRIS_GAME_UUID") == self.game_uuid)

        return folder_pids & uuid_pids

    def get_new_pids(self):
        """Return list of PIDs started since the game was launched"""
        if self.prelaunch_pids:
            return set(system.get_running_pid_list()) - set(self.prelaunch_pids)

        logger.error("No prelaunch PIDs recorded. The game's PIDs cannot be computed.")
        return set()

    def stop_game(self):
        """Cleanup after a game as stopped"""
        duration = self.timer.duration
        logger.debug("%s has run for %d seconds", self, duration)
        if duration < 5:
            logger.warning("The game has run for a very short time, did it crash?")
            # Inspect why it could have crashed

        self.state = self.STATE_STOPPED
        GAME_STOPPED.fire(self)
        if os.path.exists(self.now_playing_path):
            os.unlink(self.now_playing_path)
        if not self.timer.finished:
            self.timer.end()
            self.playtime += self.timer.duration / 3600
            logger.debug("Playtime: %s", self.formatted_playtime)

    @watch_game_errors(game_stop_result=False)
    def beat(self):
        """Watch the game's process(es)."""
        if self.game_thread.error:
            self.on_game_quit()
            raise RuntimeError(_("<b>Error lauching the game:</b>\n") + self.game_thread.error)

        # The killswitch file should be set to a device (ie. /dev/input/js0)
        # When that device is unplugged, the game is forced to quit.
        killswitch_engage = self.killswitch and not system.path_exists(self.killswitch)
        if killswitch_engage:
            logger.warning("File descriptor no longer present, force quit the game")
            self.force_stop()
            return False
        game_pids = self.get_game_pids()
        runs_only_prelaunch = False
        if self.prelaunch_executor and self.prelaunch_executor.is_running:
            runs_only_prelaunch = game_pids == {self.prelaunch_executor.game_process.pid}
        if runs_only_prelaunch or (not self.game_thread.is_running and not game_pids):
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

            def stop_cb(_result, error):
                if error:
                    self.signal_error(error)

            jobs.AsyncCall(self.game_thread.stop, stop_cb)
        self.stop_game()

    def on_game_quit(self):
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
                    cwd=self.resolve_game_path(),
                )
                postexit_thread.start()

        quit_time = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        logger.debug("%s stopped at %s", self.name, quit_time)
        self.lastplayed = int(time.time())
        self.save_lastplayed()

        os.chdir(os.path.expanduser("~"))

        if self.antimicro_thread:
            self.antimicro_thread.stop()

        if self.resolution_changed or self.runner.system_config.get("reset_desktop"):
            DISPLAY_MANAGER.set_resolution(self.original_outputs)

        if self.compositor_disabled:
            self.set_desktop_compositing(True)

        if self.runner.system_config.get("use_us_layout"):
            with subprocess.Popen(["setxkbmap"], env=os.environ) as setxkbmap:
                setxkbmap.communicate()

        # Clear Discord Client Status
        if settings.read_setting("discord_rpc") == "True" and self.discord_id:
            discord.client.clear()

        self.process_return_codes()

    def process_return_codes(self):
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

    def write_script(self, script_path, launch_ui_delegate):
        """Output the launch argument in a bash script"""
        gameplay_info = self.get_gameplay_info(launch_ui_delegate)
        if not gameplay_info:
            # User cancelled; errors are raised as exceptions instead of this
            return
        export_bash_script(self.runner, gameplay_info, script_path)

    def move(self, new_location, no_signal=False):
        logger.info("Moving %s to %s", self, new_location)
        new_config = ""
        old_location = self.directory
        target_directory = self._get_move_target_directory(new_location)

        if system.path_contains(old_location, new_location):
            raise InvalidGameMoveError(
                _("Lutris can't move '%s' to a location inside of itself, '%s'.") % (old_location, new_location)
            )

        self.directory = target_directory
        self.save(no_signal=no_signal)

        with open(self.config.game_config_path, encoding="utf-8") as config_file:
            for line in config_file.readlines():
                if target_directory in line:
                    new_config += line
                else:
                    new_config += line.replace(old_location, target_directory)
        with open(self.config.game_config_path, "w", encoding="utf-8") as config_file:
            config_file.write(new_config)

        if not system.path_exists(old_location):
            logger.warning("Initial location %s does not exist, files may have already been moved.")
            return target_directory

        try:
            shutil.move(old_location, new_location)
        except OSError as ex:
            logger.error(
                "Failed to move %s to %s, you may have to move files manually (Exception: %s)",
                old_location,
                new_location,
                ex,
            )
        return target_directory

    def set_location(self, new_location):
        target_directory = self._get_move_target_directory(new_location)
        self.directory = target_directory
        self.save()
        return target_directory

    def _get_move_target_directory(self, new_location):
        old_location = self.directory
        if old_location and os.path.exists(old_location):
            game_directory = os.path.basename(old_location)
            return os.path.join(new_location, game_directory)

        return new_location


def export_game(slug, dest_dir):
    """Export a full game folder along with some lutris metadata"""
    # List of runner where we know for sure that 1 folder = 1 game.
    # For runners that handle ROMs, we have to handle this more finely.
    # There is likely more than one game in a ROM folder but a ROM
    # might have several files (like a bin/cue, or a multi-disk game)
    exportable_runners = [
        "linux",
        "wine",
        "dosbox",
        "scummvm",
    ]
    db_game = games_db.get_game_by_field(slug, "slug")
    if not db_game:
        logger.error("Game %s not found", slug)
        return
    if db_game["runner"] not in exportable_runners:
        raise RuntimeError("Game %s can't be exported." % db_game["name"])
    if not db_game["directory"]:
        raise RuntimeError("No game directory set. Could we guess it?")

    game = Game(db_game["id"])
    db_game["config"] = game.config.game_level
    game_path = db_game["directory"]
    config_path = os.path.join(db_game["directory"], "%s.lutris" % slug)
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(db_game, config_file, indent=2)
    archive_path = os.path.join(dest_dir, "%s.tar.xz" % slug)
    command = ["tar", "cJf", archive_path, os.path.basename(game_path)]
    system.execute(command, cwd=os.path.dirname(game_path))
    logger.info("%s exported to %s", slug, archive_path)


def import_game(file_path, dest_dir):
    """Import a game in Lutris"""
    if not os.path.exists(file_path):
        raise RuntimeError("No file %s" % file_path)
    logger.info("Importing %s to %s", file_path, dest_dir)
    if not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    original_file_list = set(os.listdir(dest_dir))
    extract.extract_archive(file_path, dest_dir, merge_single=False)
    new_file_list = set(os.listdir(dest_dir))
    new_dir = list(new_file_list - original_file_list)[0]
    game_dir = os.path.join(dest_dir, new_dir)
    try:
        game_config = [f for f in os.listdir(game_dir) if f.endswith(".lutris")][0]
    except IndexError:
        logger.error("No Lutris configuration file found in archive")
        return

    with open(os.path.join(game_dir, game_config), encoding="utf-8") as config_file:
        lutris_config = json.load(config_file)
    old_dir = lutris_config["directory"]
    with open(os.path.join(game_dir, game_config), "r", encoding="utf-8") as config_file:
        config_data = config_file.read()
    config_data = config_data.replace(old_dir, game_dir)
    with open(os.path.join(game_dir, game_config), "w", encoding="utf-8") as config_file:
        config_file.write(config_data)
    with open(os.path.join(game_dir, game_config), encoding="utf-8") as config_file:
        lutris_config = json.load(config_file)
    config_filename = os.path.join(settings.CONFIG_DIR, "games/%s.yml" % lutris_config["configpath"])
    write_yaml_to_file(lutris_config["config"], config_filename)
    game_id = games_db.add_game(
        name=lutris_config["name"],
        runner=lutris_config["runner"],
        slug=lutris_config["slug"],
        platform=lutris_config["platform"],
        directory=game_dir,
        installed=lutris_config["installed"],
        year=lutris_config["year"],
        lastplayed=lutris_config["lastplayed"],
        configpath=lutris_config["configpath"],
        playtime=lutris_config["playtime"],
        service=lutris_config["service"],
        service_id=lutris_config["service_id"],
    )
    print("Added game with ID %s" % game_id)
