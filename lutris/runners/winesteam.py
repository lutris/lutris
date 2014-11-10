# -*- coding:Utf-8 -*-
"""Runner for the Steam platform"""
import os
import time
import subprocess

from lutris import settings
from lutris.gui.dialogs import DownloadDialog
from lutris.runners import wine
from lutris.thread import LutrisThread
from lutris.util.log import logger
from lutris.util.steam import read_config, get_path_from_appmanifest
from lutris.util import system
from lutris.util.system import fix_path_case
from lutris.util.wineregistry import WineRegistry

# Redefine wine installer tasks
set_regedit = wine.set_regedit
create_prefix = wine.create_prefix
wineexec = wine.wineexec
winetricks = wine.winetricks

# Directly downloading from steam's cdn seems to be buggy with
# current implementation
# STEAM_INSTALLER_URL = "http://cdn.steampowered.com/download/SteamInstall.msi"
STEAM_INSTALLER_URL = "http://lutris.net/files/runners/SteamInstall.msi"


def download_steam(downloader=None, callback=None, callback_data=None):
    """Downloads steam with `downloader` then calls `callback`"""
    steam_installer_path = os.path.join(settings.TMP_PATH,
                                        "SteamInstall.msi")
    if not downloader:
        dialog = DownloadDialog(STEAM_INSTALLER_URL, steam_installer_path)
        dialog.run()
    else:
        downloader(STEAM_INSTALLER_URL,
                   steam_installer_path, callback, callback_data)
    return steam_installer_path


def is_running():
    return bool(system.get_pid('Steam.exe$'))


def shutdown():
    """ Shutdown Steam in a clean way.
        TODO: Detect wine binary
    """
    pid = system.get_pid('Steam.exe$')
    if not pid:
        return False
    cwd = system.get_cwd(pid)
    cmdline = system.get_command_line(pid)
    steam_exe = os.path.join(cwd, cmdline)
    logger.debug("Shutting winesteam: %s", steam_exe)
    system.execute(['wine', steam_exe, '-shutdown'])


def kill():
    system.kill_pid(system.get_pid('Steam.exe$'))


# pylint: disable=C0103
class winesteam(wine.wine):
    """ Runs Steam for Windows games """
    human_name = "Wine Steam"
    platform = "Steam for Windows"
    is_watchable = False  # Steam games pids are not parent of Lutris
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
            'label': 'Prefix'
        }
    ]

    def __init__(self, config=None):
        super(winesteam, self).__init__(config)
        self.own_game_remove_method = "Remove game data (through Wine Steam)"
        self.no_game_remove_warning = True

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
        appid = self.game_config.get('appid')
        for apps_path in self.get_steamapps_dirs():
            game_path = get_path_from_appmanifest(apps_path, appid)
            if game_path:
                return game_path
        logger.warning("Data path for SteamApp %s not found.", appid)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        return os.path.expanduser("~/")

    @property
    def launch_args(self):
        return ['"%s"' % self.get_executable(),
                '"%s"' % self.get_steam_path(), '-no-dwrite']

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
        if self.get_steam_path():
            return os.path.dirname(self.get_steam_path())

    def get_steam_path(self, prefix=None):
        """Return Steam exe's path"""
        if not prefix:
            prefix = os.path.expanduser("~/.wine")
        user_reg = os.path.join(prefix, "user.reg")
        if not os.path.exists(user_reg):
            return
        registry = WineRegistry(user_reg)
        steam_path = registry.query("Software/Valve/Steam", "SteamExe")
        if not steam_path:
            steam_path = self.get_open_command(registry)
            if not steam_path:
                return
        path = registry.get_unix_path(steam_path)
        return fix_path_case(path)

    def install(self, installer_path=None):
        logger.debug("Installing steam from %s", installer_path)
        if not self.is_wine_installed():
            super(winesteam, self).install()
        if not installer_path:
            installer_path = download_steam()
        prefix = self.get_default_prefix()
        self.msi_exec(installer_path, quiet=True, prefix=prefix)

    def is_wine_installed(self):
        return super(winesteam, self).is_installed()

    def is_installed(self):
        """Checks if wine is installed and if the steam executable is on the
           harddrive.
        """
        if not self.is_wine_installed() or not self.get_steam_path():
            return False
        return os.path.exists(self.get_steam_path())

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
        if self.steam_data_dir:
            main_dir = os.path.join(self.steam_data_dir, 'SteamApps')
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
                if os.path.exists(linux_path):
                    dirs.append(linux_path)
                i += 1
        return dirs

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
        """Return the default prefix' path. Create it if it doesn't exist"""
        winesteam_dir = os.path.join(settings.RUNNER_DIR, 'winesteam')
        # XXX I don't get the point of creating a 'prefix' subdirectory here.
        #     What could possibly go in the winesteam directory other than
        #     the prefix ? Why not have it directly in winesteam_dir?
        default_prefix = os.path.join(winesteam_dir, 'prefix')

        if not os.path.exists(default_prefix):
            self.create_prefix(default_prefix)
        return default_prefix

    def install_game(self, appid):
        command = self.launch_args + ["steam://install/%s" % appid]
        string = ' '.join(command)
        logger.debug("Thread running: %s", string)
        subprocess.Popen(string, shell=True)

    def validate_game(self, appid):
        command = self.launch_args + ["steam://validate/%s" % appid]
        string = ' '.join(command)
        subprocess.Popen(string, shell=True)

    def prelaunch(self):
        from lutris.runners import steam
        if steam.is_running():
            steam.shutdown()
            logger.info("Waiting for Steam to shutdown...")
            time.sleep(2)
            if steam.is_running():
                logger.info("Steam does not shutdown, killing it...")
                steam.kill()
                time.sleep(2)
                if steam.is_running():
                    logger.error("Failed to shutdown Steam for Windows :(")
                    return False
        return True

    def play(self):
        appid = self.game_config.get('appid') or ''
        args = self.game_config.get('args') or ''
        logger.debug("Checking Steam installation")
        self.prepare_launch()
        env = ["WINEDEBUG=fixme-all"]
        command = []
        prefix = self.game_config.get('prefix') or self.get_default_prefix()

        # TODO: Verify if a prefix exists that it's created with the correct
        # architecture
        env.append('WINEPREFIX="%s" ' % prefix)
        command += self.launch_args
        if appid:
            command += ['steam://rungameid/%s' % appid]
        if args:
            command += [args]
        return {'command': command, 'env': env}

    def stop(self):
        shutdown()
        time.sleep(2)
        super(winesteam, self).stop()

    def remove_game_data(self, **kwargs):
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        appid = self.game_config.get('appid')
        prefix = self.game_config.get('prefix')

        command = []

        # TODO: Verify if a prefix exists that it's created with the correct
        # architecture
        if not prefix:
            prefix = self.get_default_prefix()
        command.append('WINEPREFIX="%s" ' % prefix)
        command += self.launch_args
        command += ['steam://uninstall/%s' % appid]

        self.prepare_launch()
        thread = LutrisThread(' '.join(command), path=self.working_dir)
        thread.start()
