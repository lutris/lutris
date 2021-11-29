"""Collection of installer files"""
import os
import time

from gi.repository import GLib, GObject

from lutris.config import LutrisConfig
from lutris.installer.errors import ScriptingError
from lutris.runners import steam
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.steam.log import get_app_state_log


class SteamInstaller(GObject.Object):
    """Handles installation of Steam games"""

    __gsignals__ = {
        "steam-game-installed": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        "steam-state-changed": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, steam_uri, file_id):
        """
        Params:
            steam_uri: Colon separated game info containing:
                    - $STEAM
                    - The Steam appid
                    - The relative path of files to retrieve
            file_id: The lutris installer internal id for the game files
        """
        super().__init__()
        self.steam_poll = None
        self.prev_states = []  # Previous states for the Steam installer
        self.state = ""
        self.install_start_time = None
        self.steam_uri = steam_uri
        self.stop_func = None
        self.cancelled = False
        self._runner = None

        self.file_id = file_id
        try:
            _steam, appid, path = self.steam_uri.split(":", 2)
        except ValueError as err:
            raise ScriptingError("Malformed steam path: %s" % self.steam_uri) from err

        self.appid = appid
        self.path = path
        self.platform = "linux"
        self.runner = steam.steam()

    @property
    def steam_rel_path(self):
        """Return the relative path for data files"""
        _steam_rel_path = self.path.strip()
        if _steam_rel_path == "/":
            _steam_rel_path = "."
        return _steam_rel_path

    @staticmethod
    def on_steam_game_installed(_data, error):
        """Callback for Steam game installer, mostly for error handling
        since install progress is handled by _monitor_steam_game_install
        """
        if error:
            raise ScriptingError(str(error))

    def install_steam_game(self):
        """Launch installation of a steam game"""
        if self.runner.get_game_path_from_appid(appid=self.appid):
            logger.info("Steam game %s is already installed", self.appid)
            self.emit("steam-game-installed", self.appid)
        else:
            logger.debug("Installing steam game %s", self.appid)
            self.runner.config = LutrisConfig(runner_slug=self.runner.name)
            AsyncCall(self.runner.install_game, self.on_steam_game_installed, self.appid)
            self.install_start_time = time.localtime()
            self.steam_poll = GLib.timeout_add(2000, self._monitor_steam_game_install)
            self.stop_func = lambda: self.runner.remove_game_data(appid=self.appid)

    def get_steam_data_path(self):
        """Return path of Steam files"""
        data_path = self.runner.get_game_path_from_appid(appid=self.appid)
        if not data_path or not os.path.exists(data_path):
            logger.info("No path found for Steam game %s", self.appid)
            return ""
        return os.path.abspath(
            os.path.join(data_path, self.steam_rel_path)
        )

    def _monitor_steam_game_install(self):
        if self.cancelled:
            return False
        states = get_app_state_log(
            self.runner.steam_data_dir, self.appid, self.install_start_time
        )
        if states and states != self.prev_states:
            self.state = states[-1].split(",")[-1]
            logger.debug("Steam installation status: %s", states)
            self.emit("steam-state-changed", self.state)  # Broadcast new state to listeners

        self.prev_states = states
        logger.debug(self.state)
        logger.debug(states)
        if self.state == "Fully Installed":
            logger.info("Steam game %s has been installed successfully", self.appid)
            self.emit("steam-game-installed", self.appid)
            return False
        return True
