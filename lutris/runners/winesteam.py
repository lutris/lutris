# -*- coding: utf-8 -*-
"""Runner for the Steam platform"""
import os
import time
import subprocess

from lutris import settings
from lutris.gui.dialogs import DownloadDialog
from lutris.runners import wine
from lutris.thread import LutrisThread
from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam import (get_app_state_log, get_path_from_appmanifest,
                               read_config)
from lutris.util.wineregistry import WineRegistry

# Redefine wine installer tasks
set_regedit = wine.set_regedit
create_prefix = wine.create_prefix
wineexec = wine.wineexec
winetricks = wine.winetricks

STEAM_INSTALLER_URL = "http://lutris.net/files/runners/SteamSetup.exe"


def get_steam_installer_dest():
    return os.path.join(settings.TMP_PATH, "SteamSetup.exe")


def download_steam(downloader=None, callback=None, callback_data=None):
    """Downloads steam with `downloader` then calls `callback`"""
    steam_installer_path = get_steam_installer_dest()
    if not downloader:
        dialog = DownloadDialog(STEAM_INSTALLER_URL, steam_installer_path)
        dialog.run()
    else:
        downloader(STEAM_INSTALLER_URL,
                   steam_installer_path, callback, callback_data)
    return steam_installer_path


def is_running():
    return bool(system.get_pid('Steam.exe$'))


def kill():
    system.kill_pid(system.get_pid('Steam.exe$'))


# pylint: disable=C0103
class winesteam(wine.wine):
    description = "Runs Steam for Windows games"
    multiple_versions = False
    human_name = "Wine Steam"
    platform = "Steam for Windows"
    runnable_alone = True
    game_options = [
        {
            'option': 'appid',
            'type': 'string',
            'label': 'Application ID',
            'help': ("The application ID can be retrieved from the game's "
                     "page at steampowered.com. Example: 235320 is the "
                     "app ID for <i>Original War</i> in: \n"
                     "http://store.steampowered.com/app/<b>235320</b>/")
        },
        {
            'option': 'args',
            'type': 'string',
            'label': 'Arguments',
            'help': ("Windows command line arguments used when launching "
                     "Steam")
        },
        {
            'option': 'prefix',
            'type': 'directory_chooser',
            'label': 'Prefix',
            'help': ("The prefix (also named \"bottle\") used by Wine.\n"
                     "It's a directory containing a set of files and "
                     "folders making up a confined Windows environment.")
        },
        {
            'option': 'arch',
            'type': 'choice',
            'label': 'Prefix architecture',
            'choices': [('Auto', 'auto'),
                        ('32-bit', 'win32'),
                        ('64-bit', 'win64')],
            'default': 'auto',
            'help': ("The architecture of the Windows environment.\n"
                     "32-bit is recommended unless running "
                     "a 64-bit only game.")
        }
    ]

    def __init__(self, config=None):
        super(winesteam, self).__init__(config)
        self.own_game_remove_method = "Remove game data (through Wine Steam)"
        self.no_game_remove_warning = True
        self.runner_options.insert(
            0,
            {
                'option': 'steam_path',
                'type': 'directory_chooser',
                'label': 'Custom Steam location',
                'help': ("Choose a folder containing Steam.exe\n"
                         "By default, Lutris will look for a Windows Steam "
                         "installation into ~/.wine or will install it in "
                         "its own custom Wine prefix.")
            },
        )
        self.runner_options.insert(
            1,
            {
                'option': 'quit_steam_on_exit',
                'label': "Stop Steam after game exits",
                'type': 'bool',
                'default': False,
                'help': ("Shut down Steam after the game has quit.")
            },
        )

    def __repr__(self):
        return "Winesteam runner (%s)" % self.config

    @property
    def appid(self):
        return self.game_config.get('appid') or ''

    @property
    def prefix_path(self):
        _prefix = self.game_config.get('prefix') or self.get_default_prefix()
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
            return
        for apps_path in self.get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, self.appid)
            if game_path:
                return game_path
        logger.warning("Data path for SteamApp %s not found.", self.appid)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.expanduser("~/")

    @property
    def launch_args(self):
        return [self.get_executable(), self.get_steam_path(), '-no-dwrite']

    def get_open_command(self, registry):
        """Return Steam's Open command, useful for locating steam when it has
           been installed but not yet launched"""
        value = registry.query("Software/Classes/steam/Shell/Open/Command",
                               "default")
        if not value:
            return
        parts = value.split("\"")
        return parts[1].strip('\\')

    @property
    def steam_config(self):
        """Return the "Steam" part of Steam's config.vfd as a dict"""
        if not self.get_steam_path():
            return
        steam_path = os.path.dirname(self.get_steam_path())
        return read_config(steam_path)

    @property
    def steam_data_dir(self):
        """Return dir where Steam files lie"""
        steam_path = self.get_steam_path()
        if steam_path:
            return os.path.dirname(steam_path)

    def get_steam_path(self, prefix=None):
        """Return Steam exe's path"""
        custom_path = self.runner_config.get('steam_path') or ''
        if custom_path:
            custom_path = os.path.join(custom_path, 'Steam.exe')
            if os.path.exists(custom_path):
                return custom_path

        candidates = [self.get_default_prefix(), os.path.expanduser("~/.wine")]
        for prefix in candidates:
            # Try the default install path
            steam_path = os.path.join(prefix,
                                      "drive_c/Program Files/Steam/Steam.exe")
            if os.path.exists(steam_path):
                return steam_path

            # Try from the registry key
            user_reg = os.path.join(prefix, "user.reg")
            if not os.path.exists(user_reg):
                continue
            registry = WineRegistry(user_reg)
            steam_path = registry.query("Software/Valve/Steam", "SteamExe")
            if not steam_path:
                steam_path = self.get_open_command(registry)
                if not steam_path:
                    continue
            path = registry.get_unix_path(steam_path)
            path = system.fix_path_case(path)
            if path:
                return path

    def install(self, installer_path=None):
        logger.debug("Installing steam from %s", installer_path)
        if not self.is_wine_installed():
            super(winesteam, self).install()
        prefix = self.get_or_create_default_prefix()
        if not self.get_steam_path():
            if not installer_path:
                installer_path = get_steam_installer_dest()
                download_steam()
            wineexec(installer_path, args='/q', prefix=prefix,
                     wine_path=self.get_executable())
            logger.debug("Winesteam installed")
        return True

    def is_wine_installed(self):
        return super(winesteam, self).is_installed()

    def is_installed(self):
        """Checks if wine is installed and if the steam executable is on the
           harddrive.
        """
        steam_path = self.get_steam_path()
        if not (steam_path
                and os.path.exists(self.get_default_prefix())
                and self.is_wine_installed()):
            return False
        return os.path.exists(steam_path)

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        config = self.steam_config
        if config:
            apps = config['apps']
            return apps.keys()

    def get_game_path_from_appid(self, appid):
        """Return the game directory"""
        for apps_path in self.get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                return game_path
        logger.warning("Data path for SteamApp %s not found.", appid)

    def get_steamapps_dirs(self):
        """Return a list of the Steam library main + custom folders."""
        dirs = []
        # Main steamapps dir
        steam_data_dir = self.steam_data_dir
        if steam_data_dir:
            main_dir = os.path.join(steam_data_dir, 'SteamApps')
            main_dir = system.fix_path_case(main_dir)
            if main_dir:
                dirs.append(main_dir)
        # Custom dirs
        steam_config = self.steam_config
        if steam_config:
            i = 1
            while ('BaseInstallFolder_%s' % i) in steam_config:
                path = steam_config['BaseInstallFolder_%s' % i] + '/SteamApps'
                linux_path = self.parse_wine_path(path, self.prefix_path)
                linux_path = system.fix_path_case(linux_path)
                if linux_path:
                    dirs.append(linux_path)
                i += 1
        return dirs

    def get_default_steamapps_path(self):
        steamapps_paths = self.get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]

    def create_prefix(self, prefix_dir):
        logger.debug("Creating default winesteam prefix")
        wine_dir = os.path.dirname(self.get_executable())

        if not os.path.exists(os.path.dirname(prefix_dir)):
            os.makedirs(os.path.dirname(prefix_dir))
        create_prefix(prefix_dir, arch=self.wine_arch, wine_dir=wine_dir)

        # Fix steam text display
        set_regedit("HKEY_CURRENT_USER\Software\Valve\Steam",
                    'DWriteEnable', '0', 'REG_DWORD',
                    wine_path=self.get_executable(),
                    prefix=prefix_dir)

    def get_default_prefix(self):
        """Return the default prefix' path."""
        winesteam_dir = os.path.join(settings.RUNNER_DIR, 'winesteam')
        return os.path.join(winesteam_dir, 'prefix')

    def get_or_create_default_prefix(self):
        """Return the default prefix' path. Create it if it doesn't exist"""
        default_prefix = self.get_default_prefix()
        if not os.path.exists(default_prefix):
            self.create_prefix(default_prefix)
        return default_prefix

    def install_game(self, appid):
        command = self.launch_args + ["steam://install/%s" % appid]
        subprocess.Popen(command, env=self.get_env())

    def validate_game(self, appid):
        command = self.launch_args + ["steam://validate/%s" % appid]
        subprocess.Popen(command, env=self.get_env())

    def prelaunch(self):
        def check_shutdown(is_running, times=10):
            for x in range(1, times):
                time.sleep(1)
                if not is_running():
                    return True
        # Stop Wine Steam to prevent Wine prefix/version problems
        if is_running():
            logger.info("Waiting for Steam to shutdown...")
            self.shutdown()
            if not check_shutdown(is_running):
                logger.info("Wine Steam does not shut down, killing it...")
                kill()
                if not check_shutdown(is_running, 5):
                    logger.error("Failed to shut down Wine Steam :(")
                    return False
        # Stop Linux Steam
        from lutris.runners import steam
        if steam.is_running():
            logger.info("Waiting for Steam shutdown...")
            steam.shutdown()
            if not check_shutdown(steam.is_running):
                logger.info("Steam does not shut down, killing it...")
                steam.kill()
                if not check_shutdown(steam.is_running, 5):
                    logger.error("Failed to shut down Steam :(")
                    return False
        return True

    def get_run_data(self):
        return {'command': self.launch_args, 'env': self.get_env(full=False)}

    def play(self):
        self.game_launch_time = time.localtime()
        args = self.game_config.get('args') or ''
        command = self.launch_args
        if self.appid:
            command.append('steam://rungameid/%s' % self.appid)
        if args:
            command.append(args)
        return {'command': command, 'env': self.get_env(full=False)}

    def watch_game_process(self):
        if not self.appid or not hasattr(self, 'game_launch_time'):
            return True
        state_log = get_app_state_log(self.steam_data_dir, self.appid,
                                      self.game_launch_time)
        if not state_log:
            return True
        state = state_log.pop()
        if state == "Fully Installed,":
            return False
        return True

    def shutdown(self):
        """Shutdown Steam in a clean way."""
        pid = system.get_pid('Steam.exe$')
        if not pid:
            return
        p = subprocess.Popen(self.launch_args + ['-shutdown'],
                             env=self.get_env())
        p.wait()

    def stop(self):
        if self.runner_config.get('quit_steam_on_exit'):
            self.shutdown()
            for x in range(1, 10):
                time.sleep(1)
                if is_running():
                    break
            super(winesteam, self).stop()

    def remove_game_data(self, appid=None, **kwargs):
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        appid = appid if appid else self.appid

        env = self.get_env(full=False)
        command = self.launch_args + ['steam://uninstall/%s' % appid]
        self.prelaunch()
        thread = LutrisThread(command, runner=self, env=env)
        thread.start()
