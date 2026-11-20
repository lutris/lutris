"""Collection of installer files"""

import asyncio
import os
import time
from gettext import gettext as _
from pathlib import Path

from lutris.config import LutrisConfig
from lutris.installer.errors import ScriptingError
from lutris.runners import steam
from lutris.util.jobs import AsyncCall, schedule_repeating_at_idle
from lutris.util.log import logger
from lutris.util.notifications import NotificationSource
from lutris.util.steam.appmanifest import get_appmanifest_from_appid
from lutris.util.steam.config import get_steamapps_dirs
from lutris.util.steam.log import get_app_state_log


class SteamInstaller:
    """Handles installation of Steam games"""

    def __init__(self, steam_uri: str, file_id: str):
        """
        Params:
            steam_uri: Colon separated game info containing:
                    - $STEAM
                    - The Steam appid
                    - The relative path of files to retrieve
            file_id: The lutris installer internal id for the game files
        """
        self.game_installed = NotificationSource()
        self.game_state_changed = NotificationSource()
        self.steam_poll = None
        self.prev_states = []  # Previous states for the Steam installer
        self.state = ""
        self.install_start_time = None
        self.steam_uri = steam_uri
        self.cancelled = False
        self._runner = None

        self.file_id = file_id
        try:
            _steam, appid, path = self.steam_uri.split(":", 2)
        except ValueError as err:
            raise ScriptingError(_("Malformed steam path: %s") % self.steam_uri) from err

        self.appid = appid
        self.path = path
        self.platform = "linux"
        self.runner = steam.steam()

    @property
    def steam_rel_path(self) -> str:
        """Return the relative path for data files"""
        _steam_rel_path = self.path.strip()
        if _steam_rel_path == "/":
            _steam_rel_path = "."
        return _steam_rel_path

    async def wait_for_data(self) -> tuple[str, str]:
        """Ask Steam to install the game and wait for its root and requested data path."""
        if not (self.appid.isascii() and self.appid.isdecimal()):
            raise ScriptingError(_("Invalid Steam app ID: %s") % self.appid)
        root = await asyncio.to_thread(self._find_installed_root)
        if root is None:
            await asyncio.to_thread(self._request_install)
            while root is None:
                await asyncio.sleep(2)
                root = await asyncio.to_thread(self._find_installed_root)
        data_path = (root / self.steam_rel_path).resolve()
        if not data_path.is_relative_to(root) or not data_path.exists():
            raise ScriptingError(_("The requested files were not found in the Steam installation."))
        return str(root), str(data_path)

    def _request_install(self) -> None:
        self.runner.config = LutrisConfig(runner_slug=self.runner.name)
        self.runner.install_game(self.appid)

    def _find_installed_root(self) -> Path | None:
        for steamapps in get_steamapps_dirs():
            try:
                manifest = get_appmanifest_from_appid(steamapps, self.appid)
                if manifest and manifest.is_installed() and (path := manifest.get_install_path()):
                    return Path(path).resolve()
            except OSError, ValueError:
                # Steam may be replacing the manifest or library while this runs
                continue
        return None

    @staticmethod
    def on_steam_game_installed(_data, error):
        """Callback for Steam game installer, mostly for error handling
        since install progress is handled by _monitor_steam_game_install
        """
        if error:
            raise ScriptingError.wrap(error)

    def install_steam_game(self) -> None:
        """Launch installation of a steam game"""
        if self.runner.get_game_path_from_appid(appid=self.appid):
            logger.info("Steam game %s is already installed", self.appid)
            self.game_installed.fire(self)
        else:
            logger.debug("Installing steam game %s", self.appid)
            self.runner.config = LutrisConfig(runner_slug=self.runner.name)
            AsyncCall(self.runner.install_game, self.on_steam_game_installed, self.appid)
            self.install_start_time = time.localtime()
            self.steam_poll = schedule_repeating_at_idle(self._monitor_steam_game_install, interval_seconds=2.0)

    def stop_waiting(self, *_args: object) -> None:
        self.cancelled = True

    def get_steam_data_path(self):
        """Return path of Steam files"""
        data_path = self.runner.get_game_path_from_appid(appid=self.appid)
        if not data_path or not os.path.exists(data_path):
            logger.info("No path found for Steam game %s", self.appid)
            return ""
        return os.path.abspath(os.path.join(data_path, self.steam_rel_path))

    def _monitor_steam_game_install(self) -> bool:
        if self.cancelled:
            return False
        states = get_app_state_log(self.runner.steam_data_dir, self.appid, self.install_start_time)
        if states and states != self.prev_states:
            self.state = states[-1].split(",")[-1]
            logger.debug("Steam installation status: %s", states)
            self.game_state_changed.fire(self)  # Broadcast new state to listeners

        self.prev_states = states
        logger.debug(self.state)
        logger.debug(states)
        if self.state == "Fully Installed":
            logger.info("Steam game %s has been installed successfully", self.appid)
            self.game_installed.fire(self)
            return False
        return True
