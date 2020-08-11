"""Steam service"""
import os
import re
from gettext import gettext as _

from lutris.config import LutrisConfig, make_game_config_id
from lutris.database.games import get_games_where
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths


class SteamGame(ServiceGame):

    """ServiceGame for Steam games"""

    service = "steam"
    installer_slug = "steam"
    excluded_appids = [
        "228980",  # Steamworks Common Redistributables
        "1070560",  # Steam Linux Runtime
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

    def create_config(self):
        """Create the game configuration for a Steam game"""
        game_config = LutrisConfig(runner_slug=self.runner, game_config_id=self.config_id)
        game_config.raw_game_config.update({"appid": self.appid})
        game_config.save()


class SteamService(BaseService):

    id = "steam"
    name = _("Steam")
    icon = "steam"
    online = False

    def __init__(self):
        super().__init__()
        self._lutris_games = None
        self._lutris_steamids = None

    @property
    def lutris_games(self):
        """Return all Steam games present in the Lutris library"""
        if not self._lutris_games:
            self._lutris_games = get_games_where(steamid__isnull=False, steamid__not="")
        return self._lutris_games

    @property
    def lutris_steamids(self):
        """Return the Steam IDs of the games installed in Lutris"""
        if not self._lutris_steamids:
            self._lutris_steamids = {str(game["steamid"]) for game in self.lutris_games}
        return self._lutris_steamids

    def load(self):
        """Return importable Steam games"""
        games = []
        steamapps_paths = get_steamapps_paths()
        for platform in ('linux', 'windows'):
            for steamapps_path in steamapps_paths[platform]:
                for appmanifest_file in get_appmanifests(steamapps_path):
                    app_manifest = AppManifest(os.path.join(steamapps_path, appmanifest_file))
                    if SteamGame.is_importable(app_manifest):
                        games.append(SteamGame.new_from_steam_game(app_manifest))
        for game in games:
            game.save()
        self.emit("service-games-loaded", self.id)

    def get_pga_game(self, game):
        """Return a PGA game if one is found"""
        for pga_game in self.lutris_games:
            if (
                str(pga_game["steamid"]) == game.appid
                and (pga_game["runner"] == game.runner or not pga_game["runner"]) and not pga_game["installed"]
            ):
                return pga_game
