"""Collection of installer files"""
import os
import time

from gi.repository import GLib, GObject

from lutris.installer.errors import ScriptingError
from lutris.util.steam.log import get_app_state_log
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.config import LutrisConfig
from lutris.runners import (
    winesteam,
    steam
)


class SteamInstaller(GObject.Object):
    """Handles installation of Steam games"""

    __gsignals__ = {
        "game-installed": (GObject.SIGNAL_RUN_FIRST, None, (str, )),
    }

    def __init__(self, steam_uri, file_id):
        """
        Params:
            steam_uri: Colon separated game info containing:
                    - $STEAM or $WINESTEAM depending on the version of Steam
                        Since Steam for Linux can download games for any
                        platform, using $WINESTEAM has little value except in
                        some cases where the game needs to be started by Steam
                        in order to get a CD key (ie. Doom 3 or UT2004)
                    - The Steam appid
                    - The relative path of files to retrieve
            file_id: The lutris installer internal id for the game files
        """
        super().__init__()
        self.steam_poll = None
        self.prev_states = []  # Previous states for the Steam installer
        self.install_start_time = None
        self.steam_uri = steam_uri
        self.stop_func = None
        self.cancelled = False
        self._runner = None

        self.file_id = file_id
        try:
            runner_id, appid, path = self.steam_uri.split(":", 2)
        except ValueError:
            raise ScriptingError("Malformed steam path: %s" % self.steam_uri)

        self.appid = appid
        self.path = path
        if runner_id == "$WINESTEAM":
            self.platform = "windows"
        else:
            self.platform = "linux"

    @property
    def runner(self):
        """Return the runner instance used by this install"""
        if not self._runner:
            if self.platform == "windows":
                self._runner = winesteam.winesteam()
            self._runner = steam.steam()
        return self._runner

    @property
    def steam_rel_path(self):
        """Return the relative path for data files"""
        _steam_rel_path = self.path.strip()
        if _steam_rel_path == "/":
            _steam_rel_path = "."
        return _steam_rel_path

    def on_steam_game_installed(self, _data, error):
        """Callback for Steam game installer, mostly for error handling
        since install progress is handled by _monitor_steam_game_install
        """
        if error:
            raise ScriptingError(str(error))
        self.emit("game-installed", self.appid)

    def install_steam_game(self):
        """Launch installation of a steam game"""
        if self.runner.get_game_path_from_appid(appid=self.appid):
            logger.info("Steam game %s is already installed")
            self.emit("game-installed", self.appid)
        else:
            logger.debug("Installing steam game %s", self.appid)
            self.runner.config = LutrisConfig(runner_slug=self.runner.name)
            # FIXME Find a way to bring back arch support
            # if "arch" in self.steam_data:
            #      steam_runner.config.game_config["arch"] = self.steam_data["arch"]
            AsyncCall(self.runner.install_game, self.on_steam_game_installed, self.appid)
            self.install_start_time = time.localtime()
            self.steam_poll = GLib.timeout_add(2000, self._monitor_steam_game_install)
            self.stop_func = lambda: self.runner.remove_game_data(appid=self.appid)

    def get_steam_data_path(self):
        """Return path of Steam files"""
        data_path = self.runner.get_game_path_from_appid(appid=self.appid)
        if not data_path or not os.path.exists(data_path):
            raise ScriptingError("Unable to get Steam data for game")
        return os.path.abspath(
            os.path.join(data_path, self.steam_rel_path)
        )

    def _monitor_steam_game_install(self):
        if self.cancelled:
            return False
        states = get_app_state_log(
            self.runner.steam_data_dir, self.appid, self.install_start_time
        )
        if states != self.prev_states:
            logger.debug("Steam installation status:")
            logger.debug(states)
        self.prev_states = states

        if states and states[-1].startswith("Fully Installed"):
            logger.debug("Steam game has finished installing")
            return False
        return True
