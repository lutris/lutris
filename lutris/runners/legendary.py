"""Legendary (Epic Store) runner"""
# Standard Library
import os
import time

# Lutris Modules
from lutris import settings
from lutris.command import MonitoredCommand
from lutris.runners import wine
from lutris.runners.commands.wine import create_prefix, wineexec, winetricks
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import split_arguments
from lutris.util.wine.registry import WineRegistry
from lutris.util.wine.wine import WINE_DEFAULT_ARCH

# Using a fixed version for now
# TODO: get the tagged releases from github and offer multiple versions to install
LEGENDARY_DOWNLOAD_URL = ("https://github.com/derrod/legendary/releases/download/0.0.10/legendary")


def is_running():
    """Return whether Legendary is running"""
    return bool(system.get_pid("legendary$"))


def kill():
    """Force kills Legendary"""
    system.kill_pid(system.get_pid("legendary$"))


# pylint: disable=C0103
class legendary(wine.wine):
    description = "Runs Epic Store games using wine"
    multiple_versions = False
    human_name = "Legendary (Epic Store)"
    platforms = ["Windows"]
    runnable_alone = True
    runner_executable = os.path.join(settings.RUNNER_DIR, "legendary")
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
            "label": "Prefix",
            "help": (
                'The prefix (also named "bottle") used by Wine.\n'
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
        self.own_game_remove_method = "Remove game data"
        self.no_game_remove_warning = True

# log_level = debug
# ; maximum shared memory (in MiB) to use for installation
# max_memory = 1024
# ; default install directory
# install_dir = /mnt/tank/games
        legendary_options = [
            {
                "option": "game_install_dir",
                "type": "directory_chooser",
                "label": "Default game install directory",
                "default": os.path.join(os.path.expanduser("~"), "Games"),
                "help": (
                    "Choose a folder for games to be installed in"
                ),
            },
            {
                "option": "auth_token",
                "type": "string",
                "label": "Authentication token",
                "advanced": True,
                "help": "Authentication token for Epic Store. Get it by starting the runner or calling `legendary auth`",
            },
            {
                "option": "log_level",
                "label": "Log Level",
                "type": "choice",
                "choices": [
                    ("Critical","critical"), 
                    ("Error","error"), 
                    ("Warning","warning"), 
                    ("Info","info"), 
                    ("Debug","debug"),
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


    def install(self, version=None, downloader=None, callback=None):
        installer_path = self.runner_executable
        def on_downloaded(*_args):
            logger.info("Downloaded legendary runner")
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
        install_command = MonitoredCommand(
            ([self.runner_executable, "install", appid]),
            runner=self,
            env=self.get_env(os_env=False),
        )        
        install_command.start()

    def prelaunch(self):
        # super().prelaunch()
        try:
            self.force_shutdown()
        except RuntimeError:
            return False
        return True

    def get_run_data(self):
        """This is only use to trigger authentication when starting the runner. Do not use this for starting games!"""
        return {"command": [self.runner_executable ,"auth"]}

    def get_command(self):
        """Return the command used to launch a EGS game"""
        game_args = self.game_config.get("args") or ""
        game_id = self.game_config.appid
        command = [self.runner_executable, "launch", game_id]
        for arg in split_arguments(game_args):
            command.append(arg)
        return command

    def play(self):
        """Run a game"""
        if self.runner_config.get("x360ce-path"):
            self.setup_x360ce(self.runner_config["x360ce-path"])

        return {"env": self.get_env(os_env=False), "command": self.get_command()}


    def remove_game_data(self, appid=None, **kwargs):
        """Uninstall a game from Legendary"""
        if not self.is_installed():
            logger.warning("Trying to remove a Legendary (Epic Store) game but it's not installed.")
            return False
        self.force_shutdown()
        uninstall_command = MonitoredCommand(
            ([self.runner_executable, "uninstall", appid]),
            runner=self,
            env=self.get_env(os_env=False),
        )        
        uninstall_command.start()
