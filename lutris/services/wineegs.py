"""EGS service"""
import os
import re
import json

from lutris import pga
from lutris.config import make_game_config_id, LutrisConfig
from lutris.runners import wineegs
from lutris.util.log import logger
from lutris.util.egs.appmanifest import AppManifest, get_appmanifests, get_unix_path
from lutris.util.egs.config import get_egs_data_path
# from lutris.util.steam.config import get_steamapps_paths

from lutris.services.service_game import ServiceGame

NAME = "Epic Games Store"
ICON = "wineegs"
ONLINE = False


class EGSGame(ServiceGame):
    """ServiceGame for EGS games"""
    store = "egs"
    installer_slug = "egs"
    runner = "wineegs"

    @classmethod
    def new_from_egs_game(cls, appmanifest, game_id=None):
        """Return a EGS game instance from an AppManifest"""
        egs_game = EGSGame()
        egs_game.appid = str(appmanifest.appid)
        egs_game.game_id = game_id
        egs_game.name = appmanifest.name
        # TODO: service_game.icon?
        egs_game.slug = appmanifest.slug
        egs_game.runner = EGSGame.runner
        egs_game.details = json.dumps(appmanifest.appmanifest_data)
        return egs_game

    def __hash__(self):
        return hash((self.runner, self.appid))

    def __eq__(self, other):
        return isinstance(other, EGSGame) and self.runner == other.runner and self.appid == other.appid

    @classmethod
    def new_from_lutris_id(cls, game_id):
        egs_game = EGSGame()
        egs_game.game_id = game_id
        return egs_game

    @property
    def config_id(self):
        return make_game_config_id(self.slug)

    @classmethod
    def is_importable(cls, prefix, appmanifest):
        """Return whether a EGS game should be imported"""
        # Installation still in progress / not started
        if not appmanifest.is_installed():
            return False

        # check, if the game directory exists. 
        # EGS might not clean up manifest files if a game directory is manually deleted.
        # this could create duplicate manifests when installing the game again
        try:
            game_path = get_unix_path(prefix, appmanifest.installdir)
            dir_exists = os.path.exists(game_path)
            return dir_exists
        except Exception:
            logger.warn("Directory %s not found in prefix %s.", appmanifest.installdir, prefix)
            return False

    def install(self, updated_info=None):
        """Add an installed game to the library

        Params:
            updated_info (dict): Optional dictonary containing existing data not to overwrite
        """
        if updated_info:
            name = updated_info["name"]
            slug = updated_info["slug"]
        else:
            name = self.name
            slug = self.slug
        self.game_id = pga.add_or_update(
            id=self.game_id,
            name=name,
            runner=self.runner,
            slug=slug,
            steamid=self.appid,
            installed=1,
            configpath=self.config_id,
            installer_slug=self.installer_slug,
        )
        self.create_config()
        return self.game_id

    def create_config(self):
        """Create the game configuration for a EGS game"""
        game_config = LutrisConfig(
            runner_slug=self.runner, game_config_id=self.config_id)
        game_config.raw_game_config.update({
                "appid": self.appid
                })
        game_config.save()


class EGSSyncer:
    platform = "linux"

    def __init__(self):
        self._lutris_games = None
        self._lutris_egsids = None

    @property
    def runner(self):
        return "wineegs"

    @property
    def lutris_games(self):
        if not self._lutris_games:            
            self._lutris_games = pga.get_games_where(
                runner=EGSGame.runner,
                installer_slug=EGSGame.installer_slug
            )
        return self._lutris_games

    @property
    def lutris_egsids(self):
        if not self._lutris_egsids:
            self._lutris_egsids = {
                # TODO: using steamid here until egsid is available in DB or a better solution
                str(game["steamid"]) for game in self.lutris_games} 
        return self._lutris_egsids

    def load(self, force_reload=False):
        """Return importable EGS games"""
        egs_runner = wineegs.wineegs()
        games = set([])
        egs_data_path = get_egs_data_path()
        for appmanifest_file in get_appmanifests(egs_data_path):
            app_manifest = AppManifest(appmanifest_file)
            if EGSGame.is_importable(egs_runner.prefix_path, app_manifest):
                games.add(EGSGame.new_from_egs_game(app_manifest))
        return games

    def get_pga_game(self, game):
        """Return a PGA game if one is found"""
        for pga_game in self.lutris_games:
            if (
                    str(pga_game["steamid"]) == game.appid
                    and pga_game["runner"] == self.runner
                    and not pga_game["installed"]
            ):
                return pga_game

    def sync(self, games, full=False):
        """Syncs EGS games to Lutris"""
        available_ids = set()  # Set of Steam appids seen while browsing AppManifests
        added_games = []
        for game in games:
            egsid = game.appid
            available_ids.add(egsid)
            pga_game = self.get_pga_game(game)

            if pga_game:
                if egsid in self.lutris_egsids and pga_game["installed"] != 1 and pga_game["installed"]:
                    added_games.append(game.install())

            if egsid not in self.lutris_egsids:
                added_games.append(game.install())
            else:
                if pga_game:
                    added_games.append(game.install(pga_game))

        if not full:
            return added_games, games

        removed_games = []
        unavailable_ids = self.lutris_egsids.difference(available_ids)
        for egsid in unavailable_ids:
            for pga_game in self.lutris_games:
                if (
                        str(pga_game["steamid"]) == egsid
                        and pga_game["installed"]
                        and pga_game["runner"] == self.runner
                ):
                    game = EGSGame.new_from_lutris_id(pga_game["id"])
                    game.uninstall()
                    removed_games.append(pga_game["id"])
        return (added_games, removed_games)


SYNCER = EGSSyncer
