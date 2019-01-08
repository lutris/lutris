"""Steam service"""
import os
import re

from lutris import pga
from lutris.config import make_game_config_id, LutrisConfig
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths
from lutris.services.service_game import ServiceGame

NAME = "Steam"
ICON = "steam"
ONLINE = False


class SteamGame(ServiceGame):
    """SericeGame for Steam games"""
    store = "steam"
    installer_slug = "steam"
    excluded_appids = [
        "228980",  # Steamworks Common Redistributables
    ]

    @classmethod
    def new_from_steam_game(cls, appmanifest, game_id=None):
        """Return a Steam game instance from an AppManifest"""
        steam_game = SteamGame()
        steam_game.appid = str(appmanifest.steamid)
        steam_game.game_id = game_id
        steam_game.name = appmanifest.name
        steam_game.slug = appmanifest.slug
        steam_game.runner = appmanifest.get_runner_name()
        return steam_game

    @classmethod
    def new_from_lutris_id(cls, game_id):
        steam_game = SteamGame()
        steam_game.game_id = game_id
        return steam_game

    @property
    def config_id(self):
        return make_game_config_id(self.slug)

    @classmethod
    def is_importable(cls, appmanifest):
        """Return whether a Steam game should be imported"""
        if not appmanifest.is_installed():
            return False
        if appmanifest.steamid in cls.excluded_appids:
            return False
        if re.match(r"^Proton \d*", appmanifest.name):
            return False
        return True

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
            steamid=int(self.appid),
            installed=1,
            configpath=self.config_id,
            installer_slug=self.installer_slug,
        )
        self.create_config()
        return self.game_id

    def create_config(self):
        """Create the game configuration for a Steam game"""
        game_config = LutrisConfig(runner_slug=self.runner, game_config_id=self.config_id)
        game_config.raw_game_config.update({"appid": self.appid})
        game_config.save()


class SteamSyncer:
    platform = "linux"

    def __init__(self):
        self._lutris_games = None
        self._lutris_steamids = None

    @property
    def runner(self):
        return "steam" if self.platform == "linux" else "winesteam"

    @property
    def lutris_games(self):
        if not self._lutris_games:
            self._lutris_games = pga.get_games_where(steamid__isnull=False, steamid__not="")
        return self._lutris_games

    @property
    def lutris_steamids(self):
        if not self._lutris_steamids:
            self._lutris_steamids = {str(game["steamid"]) for game in self.lutris_games}
        return self._lutris_steamids

    def load(self, force_reload=False):
        """Return importable Steam games"""
        games = []
        steamapps_paths = get_steamapps_paths()
        for steamapps_path in steamapps_paths[self.platform]:
            for appmanifest_file in get_appmanifests(steamapps_path):
                app_manifest = AppManifest(os.path.join(steamapps_path, appmanifest_file))
                if SteamGame.is_importable(app_manifest):
                    games.append(SteamGame.new_from_steam_game(app_manifest))
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
        """Syncs Steam games to Lutris"""
        available_ids = set()  # Set of Steam appids seen while browsing AppManifests
        added_games = []
        for game in games:
            steamid = game.appid
            available_ids.add(steamid)
            if steamid not in self.lutris_steamids:
                added_games.append(game.install())
            else:
                pga_game = self.get_pga_game(game)
                if pga_game:
                    added_games.append(game.install(pga_game))

        if not full:
            return added_games

        removed_games = []
        unavailable_ids = self.lutris_steamids.difference(available_ids)
        for steamid in unavailable_ids:
            for pga_game in self.lutris_games:
                if (
                        str(pga_game["steamid"]) == steamid
                        and pga_game["installed"]
                        and pga_game["runner"] == self.runner
                ):
                    game = SteamGame.new_from_lutris_id(pga_game["id"])
                    game.uninstall()
                    removed_games.append(pga_game["id"])
        return (added_games, removed_games)


SYNCER = SteamSyncer
