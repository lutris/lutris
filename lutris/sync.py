# -*- coding:Utf-8 -*-
"""Synchronization of the game library with the server and other platforms."""
import os
import re

from lutris import api, pga
from lutris.game import Game
from lutris.runners.steam import steam
from lutris.runners.winesteam import winesteam
from lutris.util import resources
from lutris.util.log import logger
from lutris.util.steam import vdf_parse


class Sync(object):
    def __init__(self):
        self.library = pga.get_games()

    def sync_all(self, caller):
        self.sync_from_remote(caller)
        self.sync_steam_local(caller)

    def sync_from_remote(self, caller=None):
        """Synchronize from remote to local library.

        :param caller: The LutrisWindow object
        :return: The synchronized games (slugs)
        :rtype: set of strings
        """
        logger.debug("Syncing game library")
        # Get local library
        local_slugs = set([game['slug'] for game in self.library])
        logger.debug("%d games in local library", len(local_slugs))
        # Get remote library
        remote_library = api.get_library()
        remote_slugs = set([game['slug'] for game in remote_library])
        logger.debug("%d games in remote library (inc. unpublished)",
                     len(remote_slugs))

        not_in_local = remote_slugs.difference(local_slugs)

        added = self.sync_missing_games(not_in_local, remote_library, caller)
        updated = self.sync_game_details(remote_library, caller)
        return added.update(updated)

    @staticmethod
    def sync_missing_games(not_in_local, remote_library, caller=None):
        """Get missing games in local library from remote library.

        :param caller: The LutrisWindow object
        :return: The slugs of the added games
        :rtype: set
        """
        if not not_in_local:
            return set()

        for game in remote_library:
            slug = game['slug']
            # Sync
            if slug in not_in_local:
                logger.debug("Adding to local library: %s", slug)
                pga.add_game(
                    game['name'], slug=slug, year=game['year'],
                    updated=game['updated'], steamid=game['steamid']
                )
                if caller:
                    caller.add_game_to_view(slug)
            else:
                not_in_local.discard(slug)
        logger.debug("%d games added", len(not_in_local))
        return not_in_local

    @staticmethod
    def sync_game_details(remote_library, caller):
        """Update local game details,

        :param caller: The LutrisWindow object
        :return: The slugs of the updated games.
        :rtype: set
        """
        if not remote_library:
            return set()
        updated = set()

        # Get remote games (TODO: use this when switched API to DRF)
        # remote_games = get_games(sorted(local_slugs))
        # if not remote_games:
        #     return set()

        for game in remote_library:
            slug = game['slug']
            sync = False
            sync_icons = True
            local_game = pga.get_game_by_slug(slug)
            if not local_game:
                continue

            # Sync updated
            if game['updated'] > local_game['updated']:
                sync = True
            # Sync new DB fields
            else:
                for key, value in local_game.iteritems():
                    if value or key not in game:
                        continue
                    if game[key]:
                        sync = True
                        sync_icons = False
            if not sync:
                continue

            logger.debug("Syncing details for %s" % slug)
            pga.add_or_update(
                local_game['name'], local_game['runner'], slug,
                year=game['year'], updated=game['updated'],
                steamid=game['steamid']
            )
            caller.view.update_row(game)

            # Sync icons (TODO: Only update if icon actually updated)
            if sync_icons:
                resources.download_icon(slug, 'banner', overwrite=True,
                                        callback=caller.on_image_downloaded)
                resources.download_icon(slug, 'icon', overwrite=True,
                                        callback=caller.on_image_downloaded)
                updated.add(slug)

        logger.debug("%d games updated", len(updated))
        return updated

    def sync_steam_local(self, caller):
        """Sync Steam games in library with Steam and Wine Steam"""
        logger.debug("Syncing local steam games")
        steam_ = steam()
        winesteam_ = winesteam()

        # Get installed steamapps
        installed_steamapps = self._get_installed_steamapps(steam_)
        installed_winesteamapps = self._get_installed_steamapps(winesteam_)

        for game_info in self.library:
            runner = game_info['runner']
            game = Game(game_info['slug'])
            steamid = game_info['steamid']
            installed_in_steam = steamid in installed_steamapps
            installed_in_winesteam = steamid in installed_winesteamapps

            # Set installed
            if not game_info['installed']:
                if not installed_in_steam:  # (Linux Steam only)
                    continue
                logger.debug("Setting %s as installed" % game_info['name'])
                pga.add_or_update(game_info['name'], 'steam',
                                  game_info['slug'],
                                  installed=1)
                game.config.game_config.update({'game':
                                                {'appid': str(steamid)}})
                game.config.save()
                caller.view.set_installed(Game(game_info['slug']))

            # Set uninstalled
            elif not (installed_in_steam or installed_in_winesteam):
                if runner not in ['steam', 'winesteam']:
                    continue
                if runner == 'steam' and not steam_.is_installed():
                    continue
                if runner == 'winesteam' and not winesteam_.is_installed():
                    continue
                logger.debug("Setting %s as uninstalled" % game_info['name'])
                pga.add_or_update(game_info['name'], '',
                                  game_info['slug'],
                                  installed=0)
                caller.view.set_uninstalled(game_info['slug'])

    @staticmethod
    def _get_installed_steamapps(runner):
        """Return a list of appIDs of the installed Steam games."""
        if not runner.is_installed():
            return []
        installed = []
        dirs = runner.get_steamapps_dirs()
        for dirname in dirs:
            appmanifests = [f for f in os.listdir(dirname)
                            if re.match(r'^appmanifest_\d+.acf$', f)]
            for filename in appmanifests:
                basename, ext = os.path.splitext(filename)
                steamid = int(basename[12:])
                appmanifest_path = os.path.join(
                    dirname, "appmanifest_%s.acf" % str(steamid)
                )
                with open(appmanifest_path, "r") as appmanifest_file:
                    appmanifest = vdf_parse(appmanifest_file, {})
                appstate = appmanifest.get('AppState') or {}
                is_installed = appstate.get('LastOwner') or '0'
                if not is_installed == '0':
                    installed.append(steamid)
        return installed
