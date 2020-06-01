"""Legendary (Epic Store) runner"""
# Standard Library
import os
import subprocess
from subprocess import CalledProcessError

# Third Party Libraries
import requests

# Lutris Modules
from lutris import pga, settings
from lutris.config import LutrisConfig
from lutris.gui.dialogs import ErrorDialog, NoticeDialog
from lutris.runners import wine
# TODO: those imports are unused, but without them the install scripts cannot call e.g. "create_prefix"
from lutris.runners.commands.wine import create_prefix, winecfg, wineexec, winekill, winetricks  # noqa: F401
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import split_arguments
from lutris.util.wine.wine import WINE_DEFAULT_ARCH
from lutris.exceptions import LutrisError
from lutris.util.jobs import thread_safe_call

# TODO: maybe offer multiple versions to install
LEGENDARY_RELEASES_URL = ("https://api.github.com/repos/derrod/legendary/releases/latest")


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
    # depends_on = wine.wine #TODO: do we need this? it seems to install wine, even if i have it already
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
            "option": "skip_version_check",
            "label": "Skip checking for updates when launching this game",
            "type": "bool",
            "default": False,
            "advanced": True
        }
    ] + [
        o for o in wine.wine.game_options   # inherit all optins for wine games
        if o.get("option") != "exe"  # ...except the "exe" path.
    ]

    # Make sure to prioritize Lutris runtime environment since the
    # Wine executable is not built for the user's system libraries.
    system_options_override = [{"option": "prefer_system_libs", "default": False}]

    def __init__(self, config=None):
        super(legendary, self).__init__(config)
        if os.path.isfile(self.base_dir):
            os.remove(self.base_dir)
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)
        self.own_game_remove_method = "Remove game data"
        self.no_game_remove_warning = True

        def egs_sync_callback(widget, option, config):
            target_value = widget.get_active()
            response = self.set_egs_sync(target_value)
            return widget, option, response

# log_level = debug
# ; maximum shared memory (in MiB) to use for installation
# max_memory = 1024
# ; default install directory
# install_dir = /mnt/tank/games
        legendary_options = [
            {
                "option": "egs_sync",
                "label": "Epic Store sync",
                "type": "extended_bool",
                "callback": egs_sync_callback,
                "default": False,
                "active": True,
                "help": (
                    "If you have installed EGS in Lutris, you can enable "
                    "this setting to synchronize installed games."
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
        return self.runner_config["default_%s_prefix" % arch]

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

    def get_executable(self, version=None, fallback=True):
        return self.runner_executable

    def get_latest_release(self):
        binary_asset_name = 'legendary'
        r = requests.get(LEGENDARY_RELEASES_URL)
        release = r.json()
        latest_binary = next((x for x in release.get('assets') if x.get('name') == binary_asset_name), None)
        return latest_binary.get('browser_download_url')

    def install(self, version=None, downloader=None, callback=None):
        installer_path = self.runner_executable

        def on_downloaded(*_args):
            logger.info("Downloaded legendary runner")
            os.chmod(installer_path, 0o744)
            NoticeDialog('To use this runner, authenticate it at "Import Games" first.')
            if callback:
                callback()

        downloader(self.get_latest_release(), installer_path, on_downloaded)

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if Legendary executable is on the drive"""
        # if not super().is_installed(version=version, fallback=fallback, min_version=min_version):
        #     return False
        return system.path_exists(self.runner_executable)

    def is_game_installed(self, appid):
        """Checks if a game is already installed in legendary"""
        process = subprocess.run(
            [self.runner_executable, "list-installed", "--csv"],
            capture_output=True,
            text=True,
            check=True
        )
        lines = process.stdout.splitlines()[1:]  # skip the csv header
        installed_apps = [line.split(",")[0] for line in lines]

        return appid in installed_apps

    def install_game(self, appid, target_path):
        """Install a game with Legendary"""
        if not appid:
            raise ValueError("Missing appid in legendary.install_game")

        if self.is_game_installed(appid):
            raise RuntimeError(f"The game with id:{appid} is already installed.")

        subprocess.run(
            [
                self.runner_executable, "install",
                "--game-folder", target_path,
                appid
            ],
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

        launch_args = [
            "--wine", super().get_executable(),  # this is the wine executable
            "--wine-prefix", self.prefix_path,
        ]
        if self.game_config.get("offline") is True:
            launch_args.append("--offline")

        if self.game_config.get("skip_version_check") is True:
            launch_args.append("--skip-version-check")

        command = [
            self.runner_executable, "launch",
            *launch_args,
            game_id
        ]

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

    def set_egs_sync(self, target_state):
        try:
            if target_state:
                self.enable_egs_sync()
                return True
            else:
                self.disable_egs_sync()
                return False
        except CalledProcessError:
            return not target_state
        except LutrisError:
            return False

    def enable_egs_sync(self):
        subprocess.run(
            [
                self.runner_executable,
                "egl-sync", "--yes"
                "--egl-wine-prefix", self.get_egs_prefix()
            ],
            check=True,
        )

    def disable_egs_sync(self):
        subprocess.run(
            [
                self.runner_executable,
                "egl-sync", "--unlink"
            ],
            check=True
        )

    def get_egs_prefix(self):
        egs_query = pga.get_games_by_slug("epic-games-store")
        if len(egs_query) < 1:
            error = "Epic store needs to be installed in Lutris first."
            thread_safe_call(lambda: ErrorDialog(error))
            raise LutrisError(error)

        egs = egs_query[0]
        egs_config = LutrisConfig(runner_slug=egs.get("runner"), game_config_id=egs.get("configpath"))
        prefix = egs_config.game_config.get("prefix")
        return os.path.expanduser(prefix)
