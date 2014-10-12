# -*- coding:Utf-8 -*-
"""Synchronization of the game library with the server and other platforms."""
import os

from lutris import api, pga
from lutris.game import Game
from lutris.runners.steam import steam
from lutris.runners.winesteam import winesteam


class Sync(object):
    def __init__(self):
        self.library = pga.get_games()

    def sync_all(self, caller):
        api.sync(caller)
        self.sync_steam(caller)

    def sync_steam(self, caller):
        steam_ = steam()
        winesteam_ = winesteam()

        # Get installed steamapps
        installed_steamapps = self._get_installed_steamapps(steam_)
        installed_winesteamapps = self._get_installed_steamapps(winesteam_)

        for game_info in self.library:
            game = Game(game_info['slug'])
            steamid = game_info['steamid']
            installed_in_steam = steamid in installed_steamapps
            installed_in_winesteam = steamid in installed_winesteamapps

            # Set installed (steam linux only)
            if installed_in_steam and not game_info['installed']:
                pga.add_or_update(game_info['name'], 'steam',
                                  game_info['slug'],
                                  installed=1)
                game.config.game_config.update({'game':
                                                {'appid': str(steamid)}})
                game.config.save()
                caller.view.set_installed(game)
                continue

            # Set uninstalled
            if not (installed_in_steam or installed_in_winesteam) \
               and game_info['installed'] \
               and game_info['runner'] in ['steam', 'winesteam']:
                pga.add_or_update(game_info['name'], '',
                                  game_info['slug'],
                                  installed=0)
                caller.view.set_uninstalled(game_info['slug'])

    @staticmethod
    def _get_installed_steamapps(runner):
        if not runner.is_installed():
            return []
        installed = []
        dirs = runner.get_steamapps_dirs()
        for dir_ in dirs:
            files = os.listdir(dir_)
            for file_ in files:
                if 'appmanifest_' == file_[0:12]:
                    steamid = int(file_[12:-4])
                    installed.append(steamid)
        return installed
