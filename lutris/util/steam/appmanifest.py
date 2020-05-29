"""Steam appmanifest file hnadling"""
# Standard Library
import os
import re

# Lutris Modules
from lutris.util.log import logger
from lutris.util.steam.config import get_steamapps_paths
from lutris.util.steam.vdf import vdf_parse
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

    def __init__(self, appmanifest_path):
        self.appmanifest_path = appmanifest_path
        self.steamapps_path, filename = os.path.split(appmanifest_path)
        self.steamid = re.findall(r"(\d+)", filename)[-1]
        self.appmanifest_data = {}

        if path_exists(appmanifest_path):
            with open(appmanifest_path, "r") as appmanifest_file:
                self.appmanifest_data = vdf_parse(appmanifest_file, {})
        else:
            logger.error("Path to AppManifest file %s doesn't exist", appmanifest_path)

    def __repr__(self):
        return "<AppManifest: %s>" % self.appmanifest_path

    @property
    def app_state(self):
        """State of the app (dictionary containing game specific info)"""
        return self.appmanifest_data.get("AppState") or {}

    @property
    def user_config(self):
        """Return the user configuration part"""
        return self.app_state.get("UserConfig") or {}

    @property
    def name(self):
        """Return the game name from either the state or the user config"""
        _name = self.app_state.get("name")
        if not _name:
            _name = self.user_config.get("name")
        return _name

    @property
    def slug(self):
        """Return a slugified version of the name"""
        return slugify(self.name)

    @property
    def installdir(self):
        """Path where the game is installed"""
        return self.app_state.get("installdir")

    @property
    def states(self):
        """Return the states of a Steam game."""
        states = []
        state_flags = self.app_state.get("StateFlags", 0)
        state_flags = bin(int(state_flags))[:1:-1]
        for index, flag in enumerate(state_flags):
            if flag == "1":
                states.append(APP_STATE_FLAGS[index + 1])
        return states

    def is_installed(self):
        """True if the game is fully installed"""
        return "Fully Installed" in self.states

    def get_install_path(self):
        """Absolute path of the installation directory"""
        if not self.installdir:
            return None
        install_path = fix_path_case(os.path.join(self.steamapps_path, "common", self.installdir))
        if install_path:
            return install_path

        return None

    def get_platform(self):
        """Platform the game uses (linux or windows)"""
        steamapps_paths = get_steamapps_paths()
        if self.steamapps_path in steamapps_paths["linux"]:
            return "linux"
        if self.steamapps_path in steamapps_paths["windows"]:
            return "windows"
        raise ValueError("Can't find %s in %s" % (self.steamapps_path, steamapps_paths))

    def get_runner_name(self):
        """Runner used by the Steam game"""
        return "steam" if self.get_platform() == "linux" else "winesteam"


def get_appmanifest_from_appid(steamapps_path, appid):
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


def get_path_from_appmanifest(steamapps_path, appid):
    """Return the path where a Steam game is installed."""
    appmanifest = get_appmanifest_from_appid(steamapps_path, appid)
    if not appmanifest:
        return None
    return appmanifest.get_install_path()


def get_appmanifests(steamapps_path):
    """Return the list for all appmanifest files in a Steam library folder"""
    return [f for f in os.listdir(steamapps_path) if re.match(r"^appmanifest_\d+.acf$", f)]
