"""Legendary (Epic Store) runner"""
# Standard Library
import os
import subprocess

# Lutris Modules
from lutris import settings
from lutris.command import MonitoredCommand
from lutris.runners import wine
from lutris.runners.commands.wine import create_prefix
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import split_arguments
from lutris.util.wine.wine import WINE_DEFAULT_ARCH
from lutris.exceptions import LutrisError
from lutris.gui.dialogs import ErrorDialog, NoticeDialog

# Using a fixed version for now
# TODO: get the tagged releases from github and offer multiple versions to install
LEGENDARY_DOWNLOAD_URL = ("https://github.com/derrod/legendary/releases/download/0.0.10/legendary")


def is_running():
    """Return whether Legendary is running"""
    return bool(system.get_pid("legendary$"))


def kill():
    """Force kills Legendary"""
    if is_running():
        system.kill_pid(system.get_pid("legendary$"))


# pylint: disable=C0103
class legendary(wine.wine):
    description = "Runs Epic Store games using wine"
    multiple_versions = False
    human_name = "Legendary (Epic Store)"
    platforms = ["Windows"]
    runnable_alone = False
    base_dir = os.path.join(settings.RUNNER_DIR, "legendary")  # might contain version in the future
    runner_executable = os.path.join(base_dir, "legendary")
    # depends_on = wine.wine
    default_arch = WINE_DEFAULT_ARCH
    game_options = [
        {
            "option": "appid",
            "type": "string",
            "label": "Application ID",
            "help": (
                "The application name can be retrieved from epic launcher's logfiles"
                "after creating a shortcut from within the launcher."
                "app name for <i>Celeste</i> is: <b>Salt</b>"
            ),
        },
        {
            "option": "prefix",
            "type": "directory_chooser",
            "label": "Game prefix",
            "default": os.path.join(base_dir, "prefix"),
            "help": (
                'The default prefix for games (also named "bottle") used by Wine.\n'
                "It's a directory containing a set of files and "
                "folders making up a confined Windows environment."
            ),
        },
        {
            "option": "offline",
            "label": "Launch game without online authentication",
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": (
                "Only works for games, that do not use DRM"
            ),
        },
        {
            "option": "skip_update_check",
            "label": "Skip checking for updates when launching this game",
            "type": "bool",
            "default": False,
            "advanced": True
        },
        {
            "option": "args",
            "type": "string",
            "label": "Arguments",
            "advanced": True,
            "help": "Start parameters to use (in addition to the required ones)",
        },
    ]

    def __init__(self, config=None):
        super(legendary, self).__init__(config)
        if os.path.isfile(self.base_dir):
            os.remove(self.base_dir)
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)
        self.own_game_remove_method = "Remove game data"
        self.no_game_remove_warning = True

# log_level = debug
# ; maximum shared memory (in MiB) to use for installation
# max_memory = 1024
# ; default install directory
# install_dir = /mnt/tank/games
        legendary_options = [            
            {
                "option": "auth_token",
                "type": "string",
                "label": "Authentication token",
                "advanced": True,
                "help": (
                    "Authentication token for Epic Store."
                    "Get it by starting the runner or calling `legendary auth`"
                ),
            },
            {
                "option": "log_level",
                "label": "Log Level",
                "type": "choice",
                "choices": [
                    ("Critical", "critical"),
                    ("Error", "error"),
                    ("Warning", "warning"),
                    ("Info", "info"),
                    ("Debug", "debug"),
                ],
                "default": "warning",
                "advanced": True,
            },
        ]
        for option in reversed(legendary_options):
            self.runner_options.insert(0, option)

    def __repr__(self):
        return "Legendary (Epic Store) runner (%s)" % self.config

    @property
    def appid(self):
        """EGS AppID used to uniquely identify games"""
        return self.game_config.get("appid") or ""

    def create_default_prefix(self, prefix_dir, arch=None):
        """Create the default prefix for Legendary

        Args:
            prefix_path (str): Destination of the default prefix
            arch (str): Optional architecture for the prefix, defaults to win64
        """
        logger.debug("Creating default legendary wine prefix")
        arch = arch or self.default_arch

        if not system.path_exists(os.path.dirname(prefix_dir)):
            os.makedirs(os.path.dirname(prefix_dir))
        create_prefix(prefix_dir, arch=arch, wine_path=self.get_executable())

    def get_default_prefix(self, arch):
        """Return the default prefix' path."""
        return self.runner_config["default_prefix" % arch]

    def get_or_create_default_prefix(self, arch=None):
        """Return the default prefix' path. Create it if it doesn't exist"""
        if not arch or arch == "auto":
            arch = self.default_arch
        prefix = self.get_default_prefix(arch=arch)
        if not system.path_exists(prefix):
            self.create_default_prefix(prefix, arch=arch)
        return prefix

    @property
    def browse_dir(self):
        """Return the path to open with the Browse Files action."""
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        return self.game_path

    @property
    def working_dir(self):
        """Return the working directory of legendary."""
        return os.path.dirname(self.runner_executable)

    @property
    def game_path(self):
        raise NotImplementedError()  # TODO

    def get_executable(self, version=None, fallback=True):
        return self.runner_executable

    def install(self, version=None, downloader=None, callback=None):
        installer_path = self.runner_executable

        def on_downloaded(*_args):
            logger.info("Downloaded legendary runner")
            os.chmod(installer_path, 0o744)
            NoticeDialog('To use this runner, authenticate it at "Import Games" first.')
            if callback:
                callback()

        downloader(LEGENDARY_DOWNLOAD_URL, installer_path, on_downloaded)

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if Legendary executable is on the drive"""
        # if not super().is_installed(version=version, fallback=fallback, min_version=min_version):
        #     return False
        return system.path_exists(self.runner_executable)

    def install_game(self, appid):
        """Install a game with Legendary"""
        if not appid:
            raise ValueError("Missing appid in legendary.install_game")
        
        process = subprocess.run(
            [   
                self.runner_executable, "install", 
                "--base-path", self.default_path,
                appid
            ],
            capture_output=True,
            text=True,
            input="y",
            check=True
        )
        # Todo: check for failure, report console output

    def prelaunch(self):
        logger.info("Setting up the wine environment")
        return super().prelaunch()

    def get_command(self):
        """Return the command used to launch a EGS game"""
        game_args = self.game_config.get("args") or ""
        game_id = self.game_config.get("appid")
        command = [self.runner_executable, "launch", game_id]
        for arg in split_arguments(game_args):
            command.append(arg)
        return command

    def play(self):
        """Run a game"""
        if self.runner_config.get("x360ce-path"):
            self.setup_x360ce(self.runner_config["x360ce-path"])

        return {"env": self.get_env(os_env=False), "command": self.get_command()}

    def remove_game_data(self, game_path=None):
        """Uninstall a game from Legendary"""
        if not self.is_installed():
            logger.warning("Trying to remove a Legendary (Epic Store) game but it's not installed.")
            return False
        kill()
        subprocess.run(
            [self.runner_executable, "uninstall", self.appid],
            capture_output=True,
            text=True,
            input="y",
            check=True,
        )
        # Todo: check for failure, report console output

    def get_available_games(self):
        """List games available to the connected account"""
        if not self.is_installed():
            raise LutrisError("Legendary (Epic Store) runner is required")
