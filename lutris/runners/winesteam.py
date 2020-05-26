"""Steam for Windows runner"""
# Standard Library
import os
import time

# Lutris Modules
from lutris import settings
from lutris.command import MonitoredCommand
from lutris.runners import wine
from lutris.runners.commands.wine import (  # noqa: F401 pylint: disable=unused-import
    create_prefix, delete_registry_key, install_cab_component, set_regedit, set_regedit_file, winecfg, wineexec,
    winekill, winetricks
)
from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam.appmanifest import get_path_from_appmanifest
from lutris.util.steam.config import read_config
from lutris.util.strings import split_arguments
from lutris.util.wine.registry import WineRegistry
from lutris.util.wine.wine import WINE_DEFAULT_ARCH

STEAM_INSTALLER_URL = ("https://lutris.nyc3.cdn.digitaloceanspaces.com/runners/winesteam/SteamSetup.exe")


def is_running():
    """Return whether Steam is running"""
    return bool(system.get_pid("Steam.exe$"))


def kill():
    """Force kills Steam"""
    system.kill_pid(system.get_pid("Steam.exe$"))


# pylint: disable=C0103
class winesteam(wine.wine):
    description = "Runs Steam for Windows games"
    multiple_versions = False
    human_name = "Wine Steam"
    platforms = ["Windows"]
    runnable_alone = True
    depends_on = wine.wine
    default_arch = WINE_DEFAULT_ARCH
    game_options = [
        {
            "option":
            "appid",
            "type":
            "string",
            "label":
            "Application ID",
            "help": (
                "The application ID can be retrieved from the game's "
                "page at steampowered.com. Example: 235320 is the "
                "app ID for <i>Original War</i> in: \n"
                "http://store.steampowered.com/app/<b>235320</b>/"
            ),
        },
        {
            "option": "args",
            "type": "string",
            "label": "Arguments",
            "help": "Command line arguments used when launching the game",
        },
        {
            "option":
            "prefix",
            "type":
            "directory_chooser",
            "label":
            "Prefix",
            "help": (
                'The prefix (also named "bottle") used by Wine.\n'
                "It's a directory containing a set of files and "
                "folders making up a confined Windows environment."
            ),
        },
        {
            "option":
            "arch",
            "type":
            "choice",
            "label":
            "Prefix architecture",
            "choices": [("Auto", "auto"), ("32-bit", "win32"), ("64-bit", "win64")],
            "default":
            "auto",
            "help": (
                "The architecture of the Windows environment.\n"
                "32-bit is recommended unless running "
                "a 64-bit only game."
            ),
        },
        {
            "option":
            "nolaunch",
            "type":
            "bool",
            "default":
            False,
            "label":
            "Do not launch game, only open Steam",
            "help": (
                "Opens Steam with the current settings without running the game, "
                "useful if a game has several launch options."
            ),
        },
        {
            "option": "run_without_steam",
            "label": "DRM free mode (Do not launch Steam)",
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": "Run the game directly without Steam, requires the game binary path to be set",
        },
        {
            "option": "steamless_binary",
            "type": "file",
            "label": "Game binary path",
            "advanced": True,
            "help": "Path to the game executable (Required by DRM free mode)",
        },
    ]

    def __init__(self, config=None):
        super(winesteam, self).__init__(config)
        self.own_game_remove_method = "Remove game data (through Wine Steam)"
        self.no_game_remove_warning = True
        winesteam_options = [
            {
                "option":
                "steam_path",
                "type":
                "directory_chooser",
                "label":
                "Custom Steam location",
                "help": (
                    "Choose a folder containing Steam.exe\n"
                    "By default, Lutris will look for a Windows Steam "
                    "installation into ~/.wine or will install it in "
                    "its own custom Wine prefix."
                ),
            },
            {
                "option": "quit_steam_on_exit",
                "label": "Stop Steam after game exits",
                "type": "bool",
                "default": True,
                "help": "Shut down Steam after the game has quit.",
            },
            {
                "option": "args",
                "type": "string",
                "label": "Arguments",
                "advanced": True,
                "help": ("Extra command line arguments used when "
                         "launching Steam"),
            },
            {
                "option": "default_win32_prefix",
                "type": "directory_chooser",
                "label": "Default Wine prefix (32bit)",
                "default": os.path.join(settings.RUNNER_DIR, "winesteam/prefix"),
                "help": "Default prefix location for Steam (32 bit)",
                "advanced": True,
            },
            {
                "option": "default_win64_prefix",
                "type": "directory_chooser",
                "label": "Default Wine prefix (64bit)",
                "default": os.path.join(settings.RUNNER_DIR, "winesteam/prefix64"),
                "help": "Default prefix location for Steam (64 bit)",
                "advanced": True,
            },
        ]
        for option in reversed(winesteam_options):
            self.runner_options.insert(0, option)

    def __repr__(self):
        return "Winesteam runner (%s)" % self.config

    @property
    def appid(self):
        """Steam AppID used to uniquely identify games"""
        return self.game_config.get("appid") or ""

    @property
    def prefix_path(self):
        _prefix = self.game_config.get("prefix") or self.get_or_create_default_prefix(arch=self.game_config.get("arch"))
        return os.path.expanduser(_prefix)

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        return self.game_path

    @property
    def game_path(self):
        if not self.appid:
            return None
        return self.get_game_path_from_appid(self.appid)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        if self.game_config.get("run_without_steam"):
            steamless_binary = self.game_config.get("steamless_binary")
            if steamless_binary and os.path.isfile(steamless_binary):
                return os.path.dirname(steamless_binary)
        return os.path.expanduser("~/")

    @property
    def launch_args(self):
        """Provide launch arguments for Steam"""
        steam_path = self.get_steam_path()
        if not steam_path:
            raise RuntimeError("Can't find a Steam executable")
        return [
            self.get_executable(),
            steam_path,
            "-no-cef-sandbox",
            "-console",
        ] + split_arguments(self.runner_config.get("args") or "")

    @staticmethod
    def get_open_command(registry):
        """Return Steam's Open command, useful for locating steam when it has
           been installed but not yet launched"""
        value = registry.query("Software/Classes/steam/Shell/Open/Command", "default")
        if not value:
            return None
        parts = value.split('"')
        return parts[1].strip("\\")

    def get_steam_config(self):
        """Return the "Steam" part of Steam's config.vfd as a dict"""
        steam_data_dir = self.steam_data_dir
        if not steam_data_dir:
            return None
        return read_config(steam_data_dir)

    @property
    def steam_data_dir(self):
        """Return dir where Steam files lie"""
        steam_path = self.get_steam_path()
        if steam_path:
            steam_dir = os.path.dirname(steam_path)
            if os.path.isdir(steam_dir):
                return steam_dir

    def get_steam_path(self):
        """Return Steam exe's path"""
        custom_path = self.runner_config.get("steam_path") or ""
        if custom_path:
            custom_path = os.path.abspath(os.path.expanduser(os.path.join(custom_path, "Steam.exe")))
            if system.path_exists(custom_path):
                return custom_path

        candidates = [
            self.get_default_prefix(arch="win64"),
            self.get_default_prefix(arch="win32"),
            os.path.expanduser("~/.wine"),
        ]
        for prefix in candidates:
            # Try the default install path
            for default_path in [
                "drive_c/Program Files (x86)/Steam/Steam.exe",
                "drive_c/Program Files/Steam/Steam.exe",
            ]:
                steam_path = os.path.join(prefix, default_path)
                if system.path_exists(steam_path):
                    return steam_path

            # Try from the registry key
            user_reg = os.path.join(prefix, "user.reg")
            if not system.path_exists(user_reg):
                continue
            registry = WineRegistry(user_reg)
            steam_path = registry.query("Software/Valve/Steam", "SteamExe")
            if not steam_path:
                steam_path = self.get_open_command(registry)
                if not steam_path:
                    continue
            return system.fix_path_case(registry.get_unix_path(steam_path))
        return ""

    def install(self, version=None, downloader=None, callback=None):
        installer_path = os.path.join(settings.TMP_PATH, "SteamSetup.exe")

        def on_steam_downloaded(*_args):
            prefix = self.get_or_create_default_prefix()

            # Install CJK fonts in the Steam prefix before Steam
            winetricks("cjkfonts", prefix=prefix, wine_path=self.get_executable())
            wineexec(
                installer_path,
                args="/S",
                prefix=prefix,
                wine_path=self.get_executable(),
            )
            if callback:
                callback()

        downloader(STEAM_INSTALLER_URL, installer_path, on_steam_downloaded)

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if wine is installed and if the steam executable is on the drive"""
        if not super().is_installed(version=version, fallback=fallback, min_version=min_version):
            return False
        if not system.path_exists(self.get_default_prefix(arch=self.default_arch)):
            return False
        return system.path_exists(self.get_steam_path())

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        steam_config = self.get_steam_config()
        if steam_config:
            apps = steam_config["apps"]
            return apps.keys()

    def get_game_path_from_appid(self, appid):
        """Return the game directory"""
        for apps_path in self.get_steamapps_dirs():
            logger.debug("Checking for game %s in %s", appid, apps_path)
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                logger.debug("Game found in %s", game_path)
                return game_path
        logger.warning("Data path for SteamApp %s not found.", appid)

    def get_steamapps_dirs(self):
        """Return a list of the Steam library main + custom folders."""
        dirs = []
        # Main steamapps dir
        steam_data_dir = self.steam_data_dir
        if steam_data_dir:
            main_dir = os.path.join(steam_data_dir, "steamapps")
            main_dir = system.fix_path_case(main_dir)
            if main_dir and os.path.isdir(main_dir):
                dirs.append(os.path.abspath(main_dir))
        # Custom dirs
        steam_config = self.get_steam_config()
        if steam_config:
            i = 1
            while "BaseInstallFolder_%s" % i in steam_config:
                path = steam_config["BaseInstallFolder_%s" % i] + "/steamapps"
                linux_path = self.parse_wine_path(path, self.prefix_path)
                linux_path = system.fix_path_case(linux_path)
                if linux_path and os.path.isdir(linux_path):
                    dirs.append(os.path.abspath(linux_path))
                i += 1
        return dirs

    def get_default_steamapps_path(self):
        """Return the default path used for storing Steam games"""
        steamapps_paths = self.get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]

    def create_default_prefix(self, prefix_dir, arch=None):
        """Create the default prefix for Steam

        Not sure Steam will keep on working on 32bit prefixes for long.

        Args:
            prefix_path (str): Destination of the default prefix
            arch (str): Optional architecture for the prefix, defaults to win64
        """
        logger.debug("Creating default winesteam prefix")
        arch = arch or self.default_arch

        if not system.path_exists(os.path.dirname(prefix_dir)):
            os.makedirs(os.path.dirname(prefix_dir))
        create_prefix(prefix_dir, arch=arch, wine_path=self.get_executable())

    def get_default_prefix(self, arch):
        """Return the default prefix' path."""
        return self.runner_config["default_%s_prefix" % arch]

    def get_or_create_default_prefix(self, arch=None):
        """Return the default prefix' path. Create it if it doesn't exist"""
        if not arch or arch == "auto":
            arch = self.default_arch
        prefix = self.get_default_prefix(arch=arch)
        if not system.path_exists(prefix):
            self.create_default_prefix(prefix, arch=arch)
        return prefix

    def install_game(self, appid, generate_acf=False):
        """Install a game with Steam"""
        if not appid:
            raise ValueError("Missing appid in winesteam.install_game")
        system.execute(self.launch_args + ["steam://install/%s" % appid], env=self.get_env())

    def validate_game(self, appid):
        """Validate game files with Steam"""
        if not appid:
            raise ValueError("Missing appid in winesteam.validate_game")
        system.execute(self.launch_args + ["steam://validate/%s" % appid], env=self.get_env())

    def force_shutdown(self):
        """Forces a Steam shutdown, double checking its exit status and raising
        an error if it cannot be killed"""

        def has_steam_shutdown(times=10):
            for _ in range(1, times + 1):
                time.sleep(1)
                if not is_running():
                    return True

        # Stop existing winesteam to prevent Wine prefix/version problems
        if is_running():
            logger.info("Waiting for Steam to shutdown...")
            self.shutdown()
            if not has_steam_shutdown():
                logger.info("Forcing Steam shutdown")
                kill()
                if not has_steam_shutdown(5):
                    logger.error("Failed to shut down Wine Steam :(")

    def prelaunch(self):
        super().prelaunch()
        try:
            self.force_shutdown()
        except RuntimeError:
            return False
        return True

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env(os_env=False)}

    def get_command(self):
        """Return the command used to launch a Steam game"""
        game_args = self.game_config.get("args") or ""
        game_binary = self.game_config.get("steamless_binary")
        if self.game_config.get("run_without_steam") and game_binary:
            # Start without steam
            if not system.path_exists(game_binary):
                raise FileNotFoundError(2, "Game binary not found", game_binary)
            command = [self.get_executable(), game_binary]
            for arg in split_arguments(game_args):
                command.append(arg)
        else:
            # Start through steam
            command = self.launch_args
            if self.game_config.get("nolaunch"):
                command.append("steam://open/games/details")
            elif not game_args:
                command.append("steam://rungameid/%s" % self.appid)
            else:
                command.append("-applaunch")
                command.append(self.appid)
                for arg in split_arguments(game_args):
                    command.append(arg)
        return command

    def play(self):
        """Run a game"""
        if self.runner_config.get("x360ce-path"):
            self.setup_x360ce(self.runner_config["x360ce-path"])
        try:
            return {"env": self.get_env(os_env=False), "command": self.get_command()}
        except FileNotFoundError as ex:
            return {"error": "FILE_NOT_FOUND", "file": ex.filename}

    def shutdown(self):
        """Orders Steam to shutdown"""
        logger.info("Shutting down Steam")
        shutdown_command = MonitoredCommand(
            (self.launch_args + ["-shutdown"]),
            runner=self,
            env=self.get_env(os_env=False),
        )
        shutdown_command.start()

    def on_game_stop(self):
        """TODO: Call this once it is possible to monitor Steam games"""
        if bool(self.runner_config.get("quit_steam_on_exit")):
            logger.debug("Game configured to stop Steam on exit")
            self.shutdown()
            return True
        return False

    def remove_game_data(self, appid=None, **kwargs):
        """Uninstall a game from Steam"""
        if not self.is_installed():
            logger.warning("Trying to remove a winesteam game but it's not installed.")
            return False
        self.force_shutdown()
        uninstall_command = MonitoredCommand(
            (self.launch_args + ["steam://uninstall/%s" % (appid or self.appid)]),
            runner=self,
            env=self.get_env(os_env=False),
        )
        uninstall_command.start()
