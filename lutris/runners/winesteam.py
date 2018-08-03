# -*- coding: utf-8 -*-
"""Runner for the Steam platform"""
import os
import time
import shlex
import subprocess

from lutris import settings
from lutris.gui.dialogs import DownloadDialog
from lutris.runners import wine
from lutris.thread import LutrisThread
from lutris.util.process import Process
from lutris.util import system
from lutris.util.log import logger
from lutris.util.steam import get_app_state_log, read_config
from lutris.services.steam import get_path_from_appmanifest
from lutris.util.wineregistry import WineRegistry

# Redefine wine installer tasks
set_regedit = wine.set_regedit
set_regedit_file = wine.set_regedit_file
delete_registry_key = wine.delete_registry_key
create_prefix = wine.create_prefix
wineexec = wine.wineexec
winetricks = wine.winetricks
winecfg = wine.winecfg
winekill = wine.winekill

STEAM_INSTALLER_URL = "http://lutris.net/files/runners/SteamInstall.msi"


def get_steam_installer_dest():
    return os.path.join(settings.TMP_PATH, "SteamInstall.msi")


def is_running():
    pid = system.get_pid('Steam.exe$')
    if pid:
        # If process is defunct, don't consider it as running
        process = Process(pid)
        return process.state != 'Z'
    else:
        return False


def kill():
    system.kill_pid(system.get_pid('Steam.exe$'))


# pylint: disable=C0103
class winesteam(wine.wine):
    description = "Runs Steam for Windows games"
    multiple_versions = False
    human_name = "Wine Steam"
    platforms = ['Windows']
    runnable_alone = True
    depends_on = wine.wine
    default_arch = 'win64'
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
            'help': ("Command line arguments used when launching the game")
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
        },
        {
            'option': 'nolaunch',
            'type': 'bool',
            'default': False,
            'label': 'Do not launch game, only open Steam',
            'help': ("Opens Steam with the current settings without running the game, "
                     "useful if a game has several launch options.")
        },
        {
            'option': 'steamless_binary',
            'type': 'file',
            'label': 'Steamless binary',
            'advanced': True,
            'help': ("Steamless binary for running the game directly")
        },
    ]

    def __init__(self, config=None):
        super(winesteam, self).__init__(config)
        self.own_game_remove_method = "Remove game data (through Wine Steam)"
        self.no_game_remove_warning = True
        winesteam_options = [
            {
                'option': 'steam_path',
                'type': 'directory_chooser',
                'label': 'Custom Steam location',
                'help': ("Choose a folder containing Steam.exe\n"
                         "By default, Lutris will look for a Windows Steam "
                         "installation into ~/.wine or will install it in "
                         "its own custom Wine prefix.")
            },
            {
                'option': 'quit_steam_on_exit',
                'label': "Stop Steam after game exits",
                'type': 'bool',
                'default': True,
                'help': ("Shut down Steam after the game has quit.")
            },
            {
                'option': 'run_without_steam',
                'label': 'Run without Steam (if possible)',
                'type': 'bool',
                'default': False,
                'help': ("If a steamless binary is available launches the game "
                         "directly instead of launching it through Steam")
            },
            {
                'option': 'args',
                'type': 'string',
                'label': 'Arguments',
                'advanced': True,
                'help': ("Extra command line arguments used when "
                         "launching Steam")
            },
            {
                'option': 'default_win32_prefix',
                'type': 'directory_chooser',
                'label': 'Default Wine prefix (32bit)',
                'default': os.path.join(settings.RUNNER_DIR, 'winesteam/prefix'),
                'help': "Default prefix location for Steam (32 bit)",
                'advanced': True
            },
            {
                'option': 'default_win64_prefix',
                'type': 'directory_chooser',
                'label': 'Default Wine prefix (64bit)',
                'default': os.path.join(settings.RUNNER_DIR, 'winesteam/prefix64'),
                'help': "Default prefix location for Steam (64 bit)",
                'advanced': True
            },
        ]
        for option in reversed(winesteam_options):
            self.runner_options.insert(0, option)

    def __repr__(self):
        return "Winesteam runner (%s)" % self.config

    @property
    def appid(self):
        return self.game_config.get('appid') or ''

    @property
    def prefix_path(self):
        _prefix = self.game_config.get('prefix') or self.get_or_create_default_prefix(
            arch=self.game_config.get('arch')
        )
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
        return self.get_game_path_from_appid(self.appid)

    @property
    def working_dir(self):
        """Return the working directory to use when running the game."""
        if self.runner_config['run_without_steam']:
            steamless_binary = self.game_config.get('steamless_binary')
            if steamless_binary and os.path.isfile(steamless_binary):
                return os.path.dirname(steamless_binary)
        return os.path.expanduser("~/")

    @property
    def launch_args(self):
        args = [self.get_executable(), self.get_steam_path()]

        # Try to fix Steam's browser. Never worked but it's supposed to...
        args.append('-no-cef-sandbox')

        steam_args = self.runner_config.get('args') or ''
        if steam_args:
            for arg in shlex.split(steam_args):
                args.append(arg)

        return args

    def get_open_command(self, registry):
        """Return Steam's Open command, useful for locating steam when it has
           been installed but not yet launched"""
        value = registry.query("Software/Classes/steam/Shell/Open/Command",
                               "default")
        if not value:
            return
        parts = value.split("\"")
        return parts[1].strip('\\')

    def get_steam_config(self):
        """Return the "Steam" part of Steam's config.vfd as a dict"""
        steam_data_dir = self.steam_data_dir
        if not steam_data_dir:
            return
        return read_config(steam_data_dir)

    @property
    def steam_data_dir(self):
        """Return dir where Steam files lie"""
        steam_path = self.get_steam_path()
        if steam_path:
            steam_dir = os.path.dirname(steam_path)
            if os.path.isdir(steam_dir):
                return steam_dir

    def get_steam_path(self, prefix=None):
        """Return Steam exe's path"""
        custom_path = self.runner_config.get('steam_path') or ''
        if custom_path:
            custom_path = os.path.abspath(os.path.expanduser(os.path.join(custom_path, 'Steam.exe')))
            if os.path.exists(custom_path):
                return custom_path

        candidates = [
            self.get_default_prefix(arch='win64'),
            self.get_default_prefix(arch='win32'),
            os.path.expanduser("~/.wine")
        ]
        for prefix in candidates:
            # Try the default install path
            for default_path in [
                "drive_c/Program Files (x86)/Steam/Steam.exe",
                "drive_c/Program Files/Steam/Steam.exe",
            ]:
                steam_path = os.path.join(prefix, default_path)
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
            return system.fix_path_case(
                registry.get_unix_path(steam_path)
            )

    def install(self, version=None, downloader=None, callback=None):
        installer_path = get_steam_installer_dest()

        def on_steam_downloaded(*args):
            prefix = self.get_or_create_default_prefix()
            self.msi_exec(installer_path,
                          quiet=True,
                          prefix=prefix,
                          wine_path=self.get_executable(),
                          working_dir="/tmp",
                          blocking=True)
            if callback:
                callback()

        if downloader:
            downloader(STEAM_INSTALLER_URL, installer_path, on_steam_downloaded)
        else:
            dialog = DownloadDialog(STEAM_INSTALLER_URL, installer_path)
            dialog.run()
            on_steam_downloaded()

    def is_wine_installed(self, version=None, fallback=True, min_version=None):
        return super(winesteam, self).is_installed(version=version, fallback=fallback, min_version=min_version)

    def is_installed(self, version=None, fallback=True, min_version=None):
        """Checks if wine is installed and if the steam executable is on the
           harddrive.
        """
        wine_installed = self.is_wine_installed(version, fallback, min_version=min_version)
        if not wine_installed:
            logger.warning('wine is not installed')
            return False
        steam_path = self.get_steam_path()
        if not os.path.exists(self.get_default_prefix()):
            return False
        return system.path_exists(steam_path)

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        steam_config = self.get_steam_config()
        if steam_config:
            apps = steam_config['apps']
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
            main_dir = os.path.join(steam_data_dir, 'steamapps')
            main_dir = system.fix_path_case(main_dir)
            if main_dir and os.path.isdir(main_dir):
                dirs.append(os.path.abspath(main_dir))
        # Custom dirs
        steam_config = self.get_steam_config()
        if steam_config:
            i = 1
            while ('BaseInstallFolder_%s' % i) in steam_config:
                path = steam_config['BaseInstallFolder_%s' % i] + '/steamapps'
                linux_path = self.parse_wine_path(path, self.prefix_path)
                linux_path = system.fix_path_case(linux_path)
                if linux_path and os.path.isdir(linux_path):
                    dirs.append(os.path.abspath(linux_path))
                i += 1
        return dirs

    def get_default_steamapps_path(self):
        steamapps_paths = self.get_steamapps_dirs()
        if steamapps_paths:
            return steamapps_paths[0]

    def create_prefix(self, prefix_dir, arch=None):
        logger.debug("Creating default winesteam prefix")
        if not arch:
            arch = self.default_arch
        wine_path = self.get_executable()

        if not os.path.exists(os.path.dirname(prefix_dir)):
            os.makedirs(os.path.dirname(prefix_dir))
        create_prefix(prefix_dir, arch=arch, wine_path=wine_path)

    def get_default_prefix(self, arch=None):
        """Return the default prefix' path."""
        return self.runner_config['default_%s_prefix' % (arch or self.default_arch)]

    def get_or_create_default_prefix(self, arch=None):
        """Return the default prefix' path. Create it if it doesn't exist"""
        if not arch or arch == 'auto':
            arch = self.default_arch
        prefix = self.get_default_prefix(arch=arch)
        if not os.path.exists(prefix):
            self.create_prefix(prefix, arch=arch)
        return prefix

    def install_game(self, appid, generate_acf=False):
        if not appid:
            raise ValueError("Missing appid in winesteam.install_game")
        command = self.launch_args + ["steam://install/%s" % appid]
        subprocess.Popen(command, env=self.get_env())

    def validate_game(self, appid):
        if not appid:
            raise ValueError("Missing appid in winesteam.validate_game")
        command = self.launch_args + ["steam://validate/%s" % appid]
        subprocess.Popen(command, env=self.get_env())

    def prelaunch(self):
        super(winesteam, self).prelaunch()

        def check_shutdown(is_running, times=10):
            for x in range(1, times + 1):
                time.sleep(1)
                if not is_running():
                    return True
        # Stop existing winesteam to prevent Wine prefix/version problems
        if is_running():
            logger.info("Waiting for Steam to shutdown...")
            self.shutdown()
            if not check_shutdown(is_running):
                logger.info("Wine Steam does not shut down, killing it...")
                kill()
                if not check_shutdown(is_running, 5):
                    logger.error("Failed to shut down Wine Steam :(")
                    return False
        return True

    def get_run_data(self):
        return {'command': self.launch_args, 'env': self.get_env(os_env=False)}

    def play(self):
        self.game_launch_time = time.localtime()
        game_args = self.game_config.get('args') or ''

        launch_info = {}
        launch_info['env'] = self.get_env(os_env=False)

        if self.runner_config.get('x360ce-path'):
            self.setup_x360ce(self.runner_config['x360ce-path'])

        steamless_binary = self.game_config.get('steamless_binary')
        if self.runner_config['run_without_steam'] and steamless_binary:
            # Start without steam
            if not os.path.exists(steamless_binary):
                return {'error': 'FILE_NOT_FOUND', 'file': steamless_binary}
            command = [self.get_executable()]
            runner_args = self.runner_config.get('args') or ''
            if runner_args:
                for arg in shlex.split(runner_args):
                    command.append(arg)
            command.append(steamless_binary)
            if game_args:
                for arg in shlex.split(game_args):
                    command.append(arg)

        else:
            # Start through steam
            command = self.launch_args
            if self.game_config.get('nolaunch'):
                command.append('steam://open/games/details')
            elif not game_args:
                command.append('steam://rungameid/%s' % self.appid)
            else:
                command.append('-applaunch')
                command.append(self.appid)
                if game_args:
                    for arg in shlex.split(game_args):
                        command.append(arg)
        launch_info['command'] = command
        return launch_info

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
        logger.debug("Stopping all winesteam processes")
        super(winesteam, self).stop()

    def killall_on_exit(self):
        return bool(self.runner_config.get('quit_steam_on_exit'))

    def stop(self):
        if self.killall_on_exit():
            logger.debug("Game configured to stop Steam on exit")
            self.shutdown()
            return True
        return False

    def remove_game_data(self, appid=None, **kwargs):
        if not self.is_installed():
            installed = self.install_dialog()
            if not installed:
                return False
        appid = appid if appid else self.appid

        env = self.get_env(os_env=False)
        command = self.launch_args + ['steam://uninstall/%s' % appid]
        self.prelaunch()
        thread = LutrisThread(command, runner=self, env=env, watch=False)
        thread.start()
