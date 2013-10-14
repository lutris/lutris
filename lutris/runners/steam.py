import os
import time
import subprocess
from lutris.runners.runner import Runner
from lutris.util.log import logger
from lutris.util import system


def shutdown():
    """ Cleanly quit Steam """
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
        return os.path.dirname(system.find_executable(self.get_steam_path()))

    def install(self):
        steam_default_path = [opt["default_path"]
                              for opt in self.runner_options
                              if opt["option"] == "steam_path"][0]
        if os.path.exists(steam_default_path):
            self.settings["runner"]["steam_path"] = steam_default_path
            self.settings.save()

    def is_installed(self):
        return bool(system.find_executable(self.get_steam_path()))

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
        return True

    def play(self):
        appid = self.settings.get('game', {}).get('appid')
        return {'command': [self.get_steam_path(), '-applaunch', appid]}

    def stop(self):
        shutdown()
