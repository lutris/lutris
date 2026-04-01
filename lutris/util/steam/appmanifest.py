"""Steam appmanifest file handling"""

import os
import re
from typing import Any

from lutris.util.log import logger
from lutris.util.steam.vdfutils import vdf_parse
from lutris.util.strings import slugify
from lutris.util.system import fix_path_case, path_exists

APP_STATE_FLAGS = [
    "Invalid",
    "Uninstalled",
    "Update Required",
    "Fully Installed",
    "Encrypted",
    "Locked",
    "Files Missing",
    "AppRunning",
    "Files Corrupt",
    "Update Running",
    "Update Paused",
    "Update Started",
    "Uninstalling",
    "Backup Running",
    "Reconfiguring",
    "Validating",
    "Adding Files",
    "Preallocating",
    "Downloading",
    "Staging",
    "Committing",
    "Update Stopping",
]


class AppManifest:
    """Representation of an AppManifest file from Steam"""

    def __init__(self, appmanifest_path: str):
        self.appmanifest_path = appmanifest_path
        self.steamapps_path, filename = os.path.split(appmanifest_path)
        self.steamid = re.findall(r"(\d+)", filename)[-1]
        self.appmanifest_data = {}

        if path_exists(appmanifest_path):
            with open(appmanifest_path, "r", encoding="utf-8") as appmanifest_file:
                self.appmanifest_data = vdf_parse(appmanifest_file, {})
        else:
            logger.error("Path to AppManifest file %s doesn't exist", appmanifest_path)

    def __repr__(self) -> str:
        return "<AppManifest: %s>" % self.appmanifest_path

    @property
    def app_state(self) -> dict[str, Any]:
        """State of the app (dictionary containing game specific info)"""
        return self.appmanifest_data.get("AppState") or {}

    @property
    def user_config(self) -> dict[str, Any]:
        """Return the user configuration part"""
        return self.app_state.get("UserConfig") or {}

    @property
    def name(self) -> str:
        """Return the game name from either the state or the user config"""
        _name = str(self.app_state.get("name"))
        if not _name:
            _name = str(self.user_config.get("name"))
        return _name

    @property
    def slug(self) -> str:
        """Return a slugified version of the name"""
        return slugify(self.name)

    @property
    def installdir(self) -> str:
        """Path where the game is installed"""
        return str(self.app_state.get("installdir"))

    @property
    def states(self) -> list[str]:
        """Return the states of a Steam game."""
        states = []
        state_flags = self.app_state.get("StateFlags", 0)
        state_flags = bin(int(state_flags))[:1:-1]
        for index, flag in enumerate(state_flags):
            if flag == "1":
                states.append(APP_STATE_FLAGS[index + 1])
        return states

    def is_installed(self) -> bool:
        """True if the game is fully installed"""
        return "Fully Installed" in self.states

    def get_install_path(self) -> str | None:
        """Absolute path of the installation directory"""
        if not self.installdir:
            return None
        install_path = fix_path_case(os.path.join(self.steamapps_path, "common", self.installdir))
        if install_path and path_exists(install_path):
            return install_path
        return None


def get_appmanifest_from_appid(steamapps_path: str, appid: str) -> AppManifest | None:
    """Given the steam apps path and appid, return the corresponding appmanifest"""
    if not steamapps_path:
        raise ValueError("steamapps_path is mandatory")
    if not path_exists(steamapps_path):
        raise IOError("steamapps_path must be a valid directory")
    if not appid:
        raise ValueError("Missing mandatory appid")
    appmanifest_path = os.path.join(steamapps_path, "appmanifest_%s.acf" % appid)
    if not path_exists(appmanifest_path):
        return None
    return AppManifest(appmanifest_path)


def get_path_from_appmanifest(steamapps_path: str, appid: str) -> str | None:
    """Return the path where a Steam game is installed."""
    appmanifest = get_appmanifest_from_appid(steamapps_path, appid)
    if not appmanifest:
        return None
    return appmanifest.get_install_path()


def get_appmanifests(steamapps_path: str) -> list[str]:
    """Return the list for all appmanifest files in a Steam library folder"""
    return [f for f in os.listdir(steamapps_path) if re.match(r"^appmanifest_\d+.acf$", f)]
