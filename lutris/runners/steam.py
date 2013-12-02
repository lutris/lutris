import os
import time
import subprocess
from lutris.runners.runner import Runner
from lutris.util.log import logger
from lutris.util import system
from lutris.util.steam import get_game_data_path, read_config, get_default_acf, to_vdf


def shutdown():
    """ Cleanly quit Steam """
    logger.debug("Shutting down Steam")
    subprocess.call(['steam', '-shutdown'])


def kill():
    """ Force quit Steam """
    system.kill_pid(system.get_pid('steam'))


def is_running():
    """ Checks if Steam is running """
    return bool(system.get_pid('steam'))


class steam(Runner):
    """ Runs Steam for Linux games """
    platform = "Steam Games"
    package = "steam"
    game_options = [
        {
            "option": 'appid',
            'label': "Application ID",
            "type": "string",
        }
    ]
    runner_options = [
        {
            "option": "steam_path",
            "type": "file_chooser",
            'label': "Steam executable",
            "default_path": "steam",
        }
    ]

    def get_steam_path(self):
        runner = self.__class__.__name__
        runner_config = self.settings.get(runner, {})
        return runner_config.get('steam_path', 'steam')

    def get_game_path(self):
        """ Return location of Steam directory """
        return os.path.expanduser('~/.local/share/Steam')

    def get_game_data_path(self, appid):
        steam_config = self.get_steam_config()
        return get_game_data_path(steam_config, appid)

    def get_steam_config(self):
        return read_config(self.get_game_path())

    def install(self):
        steam_default_path = [opt["default_path"]
                              for opt in self.runner_options
                              if opt["option"] == "steam_path"][0]
        if os.path.exists(steam_default_path):
            self.settings["runner"]["steam_path"] = steam_default_path
            self.settings.save()
        else:
            super(steam, self).install()

    def is_installed(self):
        return bool(system.find_executable(self.get_steam_path()))

    def install_game(self, appid):
        logger.debug("Installing steam game %s", appid)
        acf_data = get_default_acf(appid, appid)
        acf_content = to_vdf(acf_data)
        acf_path = os.path.join(self.get_game_path(), "SteamApps",
                                "appmanifest_%s.acf" % appid)
        with open(acf_path, "w") as acf_file:
            acf_file.write(acf_content)
        if is_running():
            shutdown()
            time.sleep(5)
        else:
            logger.debug("Steam not running")
        subprocess.Popen(["steam", "steam://preload/%s" % appid])

    def prelaunch(self):
        from lutris.runners import winesteam
        if winesteam.is_running():
            winesteam.shutdown()
            logger.info("Waiting for Steam to shutdown...")
            time.sleep(2)
            if winesteam.is_running():
                logger.info("Steam does not shutdown, killing it...")
                winesteam.kill()
                time.sleep(2)
                if winesteam.is_running():
                    logger.error("Failed to shutdown Steam for Windows :(")
                    return False
        else:
            logger.debug("winesteam not running")
        return True

    def play(self):
        appid = self.settings.get('game', {}).get('appid')
        return {'command': [self.get_steam_path(), '-applaunch', appid]}

    def stop(self):
        shutdown()
