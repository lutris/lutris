"""Epic Store for Windows runner"""
import os
import time
import shlex

from lutris import settings
from lutris.runners import wine
from lutris.command import MonitoredCommand
from lutris.util import system
from lutris.util.log import logger
from lutris.util.egs.config import get_egs_data_path
from lutris.util.egs.appmanifest import get_appmanifest_from_appid
from lutris.util.steam.config import read_config
from lutris.util.steam.appmanifest import get_path_from_appmanifest
from lutris.util.wine.registry import WineRegistry
from lutris.util.wine.wine import WINE_DEFAULT_ARCH
from lutris.runners.commands.wine import (  # noqa pylint: disable=unused-import
    set_regedit,
    set_regedit_file,
    delete_registry_key,
    create_prefix,
    wineexec,
    winetricks,
    winecfg,
    winekill,
    install_cab_component,
)

EPICGAMES_INSTALLER_URL = "https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncherInstaller.msi"
DX_2010_ARCHIVE_URL = "https://lutris.net/files/tools/directx-2010.tar.gz"
# Manifest files: HKEY_LOCAL_MACHINE/Software\Wow6432Node\Epic Games\EpicGamesLauncher -> AppDataPath
# -> drive_c/ProgramData/Epic/EpicGamesLauncher/Data/


def is_running():
    return bool(system.get_pid("EpicGamesLaunch$"))


def kill():
    system.kill_pid(system.get_pid("EpicGamesLaunch$$"))


# pylint: disable=C0103
class wineegs(wine.wine):
    description = "Runs EGS for Windows games"
    multiple_versions = False
    human_name = "Wine EGS"
    platforms = ["Windows"]
    runnable_alone = True
    depends_on = wine.wine
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
            "option": "args",
            "type": "string",
            "label": "Arguments",
            "help": "Command line arguments used when launching the game",
        },
        {
            "option": "run_without_egs",
            "label": "DRM free mode (Do not launch EGS)",
            "type": "bool",
            "default": False,
            "advanced": True,
            "help": (
                "Run the game directly without EGS. Requires executable to be set."
            ),
        }
    ]

    def __init__(self, config=None):
        super(wineegs, self).__init__(config)
        # self.own_game_remove_method = "Remove game data (through Wine EGS)"
        # self.no_game_remove_warning = True

        wineegs_options = [
            # {
            #     "option": "egs_path",
            #     "type": "directory_chooser",
            #     "label": "Custom EGS location",
            #     "help": (
            #         "Choose a folder containing EpicGamesLauncher.exe\n"
            #         "By default, Lutris will look for a wine EGS "
            #         "installation into ~/.wine or will install it in "
            #         "its own custom Wine prefix."
            #     ),
            # },
            # {
            #     "option": "quit_egs_on_exit",
            #     "label": "Stop EGS after game exits",
            #     "type": "bool",
            #     "default": True,
            #     "help": "Shut down EGS after the game has quit.",
            # },
            {
                "option": "args",
                "type": "string",
                "label": "Arguments",
                "advanced": True,
                "help": ("Extra command line arguments used when " "launching EGS"),
            },
            {
                "option": "default_win32_prefix",
                "type": "directory_chooser",
                "label": "Default Wine prefix (32bit)",
                "default": os.path.join(settings.RUNNER_DIR, "wineegs/prefix"),
                "help": "Default prefix location for EGS (32 bit)",
                "advanced": True,
            },
            {
                "option": "default_win64_prefix",
                "type": "directory_chooser",
                "label": "Default Wine prefix (64bit)",
                "default": os.path.join(settings.RUNNER_DIR, "wineegs/prefix64"),
                "help": "Default prefix location for EGS (64 bit)",
                "advanced": True,
            },
        ]
        for option in reversed(wineegs_options):
            self.runner_options.insert(0, option)

    def __repr__(self):
        return "WineEGS runner (%s)" % self.config

    @property
    def appid(self):
        return self.game_config.get("appid") or ""

    @property
    def prefix_path(self):
        _prefix = self.game_config.get("prefix") or self.get_or_create_default_prefix(
            arch=self.game_config.get("arch")
        )
        return os.path.expanduser(_prefix)

    @property
    def system_registry(self):
        system_reg = os.path.join(self.prefix_path, "system.reg")
        if not system.path_exists(system_reg):
            return None
        reg = WineRegistry(system_reg)
        return reg

    @property
    def game_manifest(self):
        egs_data_path = get_egs_data_path()
        return get_appmanifest_from_appid(egs_data_path, self.appid)

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
        """Return the game directory"""
        if not self.appid:
            return None
        #TODO: using registry is taking a long time when opening settings
        game_path = self.system_registry.get_unix_path(self.game_manifest.installdir)
        game_path = os.path.abspath(system.fix_path_case(game_path))
        if game_path:
            logger.debug("Game found in %s", game_path)
            return game_path
        logger.warning("Data path for EGS game %s not found.", appid)

    @property
    def game_exe(self):
        """Return the game's executable's path."""
        if not self.appid:
            return None
        game_exe = os.path.join(self.game_path, self.game_manifest.executable)
        if game_exe:
            logger.debug("Game executable found in %s", game_exe)
            return game_exe
        logger.warning("Executable for EGS game %s not found.", appid)
        

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        if self.game_config.get("run_without_egs"):
             return self.game_path
        return os.path.expanduser("~/")

    @property
    def launch_args(self):
        """Provide launch arguments for EGS"""
        return [
            self.get_executable(),
            self.get_egs_path(),
            "-opengl",
        ] + shlex.split(self.runner_config.get("args") or "")

    @staticmethod
    def get_open_command(registry):
        """Return EGS Open command, useful for locating EGS when it has
           been installed but not yet launched"""
        value = registry.query(
            "Software/Classes/com.epicgames.launcher/shell/open/command", "default")
        if not value:
            return None
        parts = value.split('"')
        return parts[1].strip("\\")

    @property
    def egs_data_path(self):
        """Return dir where EGS files lie"""
        default_path = "drive_c/ProgramData/Epic/EpicGamesLauncher/Data"
        egs_data_path = os.path.join(self.prefix_path, default_path)
        if egs_data_path:
            if os.path.isdir(egs_data_path):
                return egs_data_path

    @property
    def egs_path(self):
        """Return dir where EGS executable lies"""
        egs_path = self.get_egs_path()
        if egs_path:
            egs_dir = os.path.dirname(egs_path)
            if os.path.isdir(egs_dir):
                return egs_dir

    def get_egs_path(self):
        """Return EGS exe's path"""
        custom_path = self.runner_config.get("egs_path") or ""
        if custom_path:
            custom_path = os.path.abspath(
                os.path.expanduser(os.path.join(
                    custom_path, "EpicGamesLauncher.exe"))
            )
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
                    "drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win64/EpicGamesLauncher.exe",
                    "drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe"
            ]:
                egs_path = os.path.join(prefix, default_path)
                if system.path_exists(egs_path):
                    return egs_path

            # Try from the registry key            
            egs_path = self.get_open_command(self.system_registry)
            if not egs_path:
                continue
            return system.fix_path_case(self.system_registry.get_unix_path(egs_path))

    def install(self, version=None, downloader=None, callback=None):
        installer_path = os.path.join(
            settings.TMP_PATH, "EpicGamesLauncherInstaller.msi")

        def on_egs_downloaded(*_args):
            prefix = self.get_or_create_default_prefix()
            # Install dependencies
            winetricks(
                "cjkfonts arial dotnet48 d3dx9",
                prefix=prefix,
                wine_path=self.get_executable()
            )
            wineexec(
                "msiexec",
                args=f"/i {installer_path} /q",
                prefix=prefix,
                wine_path=self.get_executable(),
                exclude_processes=["EpicGamesLauncher.exe"]
            )
            if callback:
                callback()

        downloader(EPICGAMES_INSTALLER_URL,
                   installer_path, on_egs_downloaded)

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if wine is installed and if the epic games launcher executable is on the drive"""
        if not super().is_installed(version=version, fallback=fallback, min_version=min_version):
            return False
        if not system.path_exists(self.get_default_prefix(arch=self.default_arch)):
            return False
        return system.path_exists(self.get_egs_path())

    def create_default_prefix(self, prefix_dir, arch=None):
        """Create the default prefix for EGS
        Args:
            prefix_path (str): Destination of the default prefix
            arch (str): Optional architecture for the prefix, defaults to win64
        """
        logger.debug("Creating default wineegs prefix")
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
        raise NotImplementedError("Cannot install EGS games yet.")
        # if not appid:
        #     raise ValueError("Missing appid in wineegs.install_game")
        # system.execute(
        #     # self.launch_args + ["steam://install/%s" % appid],
        #     env=self.get_env()
        # )

    def validate_game(self, appid):
        raise(NotImplementedError("Not supported by EGS"))

    def force_shutdown(self):
        """Forces a EGS shutdown, double checking its exit status and raising
        an error if it cannot be killed"""
        def has_egs_shutdown(times=10):
            for _ in range(1, times + 1):
                time.sleep(1)
                if not is_running():
                    return True

        # Stop existing wineegs to prevent Wine prefix/version problems
        if is_running():
            logger.info("Waiting for EGS to shutdown...")
            self.shutdown()
            if not has_egs_shutdown():
                logger.info("Forcing EGS shutdown")
                kill()
                if not has_egs_shutdown(5):
                    logger.error("Failed to shut down Wine EGS :(")

    def prelaunch(self):
        super().prelaunch()
        try:
            self.force_shutdown()
        except RuntimeError:
            return False
        return True

    def get_run_data(self):
        return {"command": self.launch_args, "env": self.get_env(os_env=False)}

    def get_egs_command(self):
        game_args = self.game_config.get("args") or ""
        command = self.launch_args
        command.append("com.epicgames.launcher://apps/%s?action=launch&silent=true" % self.appid)
        return command

    def play(self):
        if self.runner_config.get("x360ce-path"):
            self.setup_x360ce(self.runner_config["x360ce-path"])
        
        # Start without EGS
        if self.game_config.get("run_without_egs"):
            return super(wineegs, self).play()
        # Start through EGS
        else:
            try:            
                return {
                    "env": self.get_env(os_env=False),
                    "command": self.get_egs_command()
                }
            except FileNotFoundError as ex:
                return {"error": "FILE_NOT_FOUND", "file": ex.filename}

    def shutdown(self):
        """Orders EGS to shutdown"""
        raise(NotImplementedError("Not supported by EGS"))
        # logger.info("Shutting down Steam")
        # shutdown_command = MonitoredCommand(
        #     (self.launch_args + ["-shutdown"]),
        #     runner=self,
        #     env=self.get_env(os_env=False)
        # )
        # shutdown_command.start()

    # def remove_game_data(self, appid=None, **kwargs):
    #     raise(NotImplementedError("Not supported by EGS"))
