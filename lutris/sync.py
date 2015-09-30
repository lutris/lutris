# -*- coding:Utf-8 -*-
"""Synchronization of the game library with server and local data."""
import os
import re

from lutris import api, config, pga
from lutris.runners.steam import steam
from lutris.runners.winesteam import winesteam
from lutris.util import resources
from lutris.util.log import logger
from lutris.util.steam import vdf_parse


class Sync(object):
    def __init__(self):
        self.library = pga.get_games()

    def sync_all(self):
        added, updated = self.sync_from_remote()
        installed, uninstalled = self.sync_steam_local()
        return added, updated, installed, uninstalled

    def sync_from_remote(self):
        """Synchronize from remote to local library.

        :return: The added and updated games (slugs)
        :rtype: tuple of sets
        """
        logger.debug("Syncing game library")
        # Get local library
        local_slugs = set([game['slug'] for game in self.library])
        logger.debug("%d games in local library", len(local_slugs))
        # Get remote library
        try:
            remote_library = api.get_library()
        except Exception as e:
            logger.debug("Error while downloading the remote library: %s" % e)
            remote_library = {}
        remote_slugs = set([game['slug'] for game in remote_library])
        logger.debug("%d games in remote library (inc. unpublished)",
                     len(remote_slugs))

        not_in_local = remote_slugs.difference(local_slugs)

        added = self.sync_missing_games(not_in_local, remote_library)
        updated = self.sync_game_details(remote_library)
        if added:
            self.library = pga.get_games()
        return (added, updated)

    @staticmethod
    def sync_missing_games(not_in_local, remote_library):
        """Get missing games in local library from remote library.

        :return: The slugs of the added games
        :rtype: set
        """
        if not not_in_local:
            return set()

        missing_slugs = set()
        missing = []
        for game in remote_library:
            slug = game['slug']
            if slug in not_in_local:
                logger.debug("Adding to local library: %s", slug)
                missing_slugs.add(slug)
                missing.append(
                    {'name': game['name'],
                     'slug': slug,
                     'year': game['year'],
                     'updated': game['updated'],
                     'steamid': game['steamid']}
                )
        pga.add_games_bulk(missing)
        logger.debug("%d games added", len(missing))
        return missing_slugs

    @staticmethod
    def sync_game_details(remote_library):
        """Update local game details,

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

            # Sync icons (TODO: Only update if icon actually updated)
            if sync_icons:
                resources.download_icon(slug, 'banner', overwrite=True)
                resources.download_icon(slug, 'icon', overwrite=True)
                updated.add(slug)

        logger.debug("%d games updated", len(updated))
        return updated

    def sync_steam_local(self):
        """Sync Steam games in library with Steam and Wine Steam"""
        logger.debug("Syncing local steam games")
        steamrunner = steam()
        winesteamrunner = winesteam()
        installed = set()
        uninstalled = set()

        # Get installed steamapps
        installed_steamapps = self._get_installed_steamapps(steamrunner)
        installed_winesteamapps = self._get_installed_steamapps(winesteamrunner)

        for game_info in self.library:
            slug = game_info['slug']
            runner = game_info['runner']
            steamid = game_info['steamid']
            installed_in_steam = steamid in installed_steamapps
            installed_in_winesteam = steamid in installed_winesteamapps

            # Set installed
            if not game_info['installed']:
                if not installed_in_steam:  # (Linux Steam only)
                    continue
                logger.debug("Setting %s as installed" % game_info['name'])
                pga.add_or_update(game_info['name'], 'steam', slug,
                                  installed=1)
                game_config = config.LutrisConfig(runner_slug='steam',
                                                  game_slug=game_info['slug'])
                game_config.raw_game_config.update({'appid': str(steamid)})
                game_config.save()
                installed.add(slug)

            # Set uninstalled
            elif not (installed_in_steam or installed_in_winesteam):
                if runner not in ['steam', 'winesteam']:
                    continue
                if runner == 'steam' and not steamrunner.is_installed():
                    continue
                if runner == 'winesteam' and not winesteamrunner.is_installed():
                    continue
                logger.debug("Setting %s as uninstalled" % game_info['name'])
                pga.add_or_update(game_info['name'], '',
                                  game_info['slug'],
                                  installed=0)
                uninstalled.add(slug)
        return (installed, uninstalled)

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
