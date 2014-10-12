# -*- coding:Utf-8 -*-
"""Synchronization of the game library with the server and other platforms."""
import os

from lutris.util.log import logger
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
        logger.debug("Syncing local steam games")
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
                logger.debug("Setting %s as installed" % game_info['name'])
                pga.add_or_update(game_info['name'], 'steam',
                                  game_info['slug'],
                                  installed=1)
                game.config.game_config.update({'game':
                                                {'appid': str(steamid)}})
                game.config.save()
                caller.view.set_installed(Game(game_info['slug']))
                continue

            # Set uninstalled
            if not (installed_in_steam or installed_in_winesteam) \
               and game_info['installed'] \
               and game_info['runner'] in ['steam', 'winesteam']:
                logger.debug("Setting %s as uninstalled" % game_info['name'])
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
        for dirname in dirs:
            files = os.listdir(dirname)
            for filename in files:
                if filename.startswith('appmanifest_'):
                    basename, ext = os.path.splitext(filename)
                    try:
                        steamid = int(basename[12:])
                    except ValueError:
                        logger.error("Invalid SteamID for %s", filename)
                        continue
                    installed.append(steamid)
        return installed
