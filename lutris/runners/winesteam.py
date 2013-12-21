# -*- coding:Utf-8 -*-
"""Runner for the Steam platform"""
import os
import time
import subprocess

from gi.repository import Gdk

from lutris.gui.dialogs import DirectoryDialog
from lutris.runners.wine import wine
from lutris.util.log import logger
from lutris.util.steam import read_config, get_game_data_path
from lutris.util import system
from lutris.config import LutrisConfig


def is_running():
    return bool(system.get_pid('Steam.exe'))


def shutdown():
    """ Shutdown Steam in a clean way.
        TODO: Detect wine binary
    """
    pid = system.get_pid('Steam.exe')
    if not pid:
        return False
    cwd = system.get_cwd(pid)
    cmdline = system.get_command_line(pid)
    steam_exe = os.path.join(cwd, cmdline)
    logger.debug("Shutting winesteam: %s", steam_exe)
    system.execute(['wine', steam_exe, '-shutdown'])


def kill():
    system.kill_pid(system.get_pid('Steam.exe'))


# pylint: disable=C0103
class winesteam(wine):
    """ Runs Steam for Windows games """

    #installer_url = "http://cdn.steampowered.com/download/SteamInstall.msi"
    installer_url = "http://lutris.net/files/runners/SteamInstall.msi"

    def __init__(self, settings=None):
        super(winesteam, self).__init__(settings)
        self.platform = "Steam (Windows)"
        config = LutrisConfig(runner=self.__class__.__name__)
        self.game_path = config.get_path()
        self.arguments = []
        self.game_options = [
            {'option': 'appid', 'type': 'string', 'label': 'appid'},
            {'option': 'args', 'type': 'string', 'label': 'arguments'},
            {'option': 'prefix', 'type': 'directory_chooser',
             'label': 'Prefix'}
        ]
        self.settings = settings

    def install(self, installer_path=None):
        if installer_path:
            self.msi_exec(installer_path, quiet=True)
        Gdk.threads_enter()
        dlg = DirectoryDialog('Where is Steam located?')
        self.game_path = dlg.folder
        Gdk.threads_leave()
        config = LutrisConfig(runner='winesteam')
        config.runner_config = {'system': {'game_path': self.game_path}}
        config.save(config_type='runner')

    def is_installed(self):
        """ Checks if wine is installed and if the steam executable is on the
            harddrive.
        """
        if not self.check_depends() or not self.game_path:
            return False
        return self.game_path and os.path.exists(self.steam_path)

    @property
    def steam_path(self):
        return os.path.join(self.game_path, "Steam.exe")

    @property
    def launch_args(self):
        return [self.get_wine_path(), '"%s"' % self.steam_path, '-no-dwrite']

    def get_steam_config(self):
        if not self.game_path:
            return
        return read_config(self.game_path)

    def get_appid_list(self):
        """Return the list of appids of all user's games"""
        config = self.get_steam_config()
        if config:
            apps = config['apps']
            return apps.keys()

    def get_game_data_path(self, appid):
        steam_config = self.get_steam_config()
        return get_game_data_path(steam_config, appid)

    def install_game(self, appid):
        subprocess.Popen(self.launch_args + ["steam://install/%s" % appid])

    def validate_game(self, appid):
        subprocess.Popen(self.launch_args + ["steam://validate/%s" % appid])

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
        if not self.check_depends():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.depends}
        if not self.is_installed():
            return {'error': 'RUNNER_NOT_INSTALLED',
                    'runner': self.__class__.__name__}

        appid = self.settings['game']['appid']
        if 'args' in self.settings['game']:
            self.args = self.settings['game']['args']
        else:
            self.args = ""
        logger.debug("Checking Steam installation")
        self.prepare_launch()
        command = ["WINEDEBUG=fixme-all"]
        prefix = self.settings['game'].get('prefix', "")
        if os.path.exists(prefix):
            command.append("WINEPREFIX=\"%s\" " % prefix)
        command += self.launch_args
        return {
            'command': command + ['-applaunch', appid, self.args]
        }

    def stop(self):
        shutdown()
