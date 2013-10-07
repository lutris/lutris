import os
from lutris.runners.runner import Runner
from lutris.util.system import get_pid, find_executable


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
        return os.path.dirname(find_executable(self.get_steam_path()))

    def install(self):
        steam_default_path = [opt["default_path"]
                              for opt in self.runner_options
                              if opt["option"] == "steam_path"][0]
        if os.path.exists(steam_default_path):
            self.settings["runner"]["steam_path"] = steam_default_path
            self.settings.save()

    def is_installed(self):
        return bool(find_executable(self.get_steam_path()))

    def is_launched(self):
        """ Checks if Steam is running """
        return bool(get_pid('steam'))

    def play(self):
        appid = self.settings.get('game', {}).get('appid')
        return {'command': [self.get_steam_path(), '-applaunch', appid]}

    def stop(self):
        os.call('steam -shutdown')
