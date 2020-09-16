"""Steam service"""
import os
import re
from gettext import gettext as _

from lutris.config import LutrisConfig, make_game_config_id
from lutris.database.games import get_games_where
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame, ServiceMedia
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths


class SteamBanner(ServiceMedia):
    size = (184, 69)


class SteamIcon(ServiceMedia):
    size = (32, 32)


class SteamGame(ServiceGame):

    """ServiceGame for Steam games"""

    service = "steam"
    installer_slug = "steam"
    excluded_appids = [
        "228980",  # Steamworks Common Redistributables
        "1070560",  # Steam Linux Runtime
    ]
    medias = {
        "banner": SteamBanner,
        "icon": SteamIcon
    }

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

    @property
    def lutris_games(self):
        """Get all Lutris games with a Steam ID"""
        if not self._lutris_games:
            self._lutris_games = get_games_where(steamid__isnull=False, steamid__not="")
        return self._lutris_games

    def get_lutris_games_by_appid(self):
        """Return Lutris games keyed by Steam AppID"""
        lutris_steamid_map = {}
        for lutris_game in self.lutris_games:
            lutris_steamid_map[lutris_game["steamid"]] = lutris_game
        return lutris_steamid_map

    def load(self):
        """Return importable Steam games"""
        games = []
        steamapps_paths = get_steamapps_paths()
        for platform in ('linux', 'windows'):
            for steamapps_path in steamapps_paths[platform]:
                for appmanifest_file in get_appmanifests(steamapps_path):
                    app_manifest = AppManifest(os.path.join(steamapps_path, appmanifest_file))
                    if SteamGame.is_importable(app_manifest):
                        logger.debug("Found Steam game %s", app_manifest)
                        games.append(SteamGame.new_from_steam_game(app_manifest))

        steam_map = self.get_lutris_games_by_appid()
        for game in games:
            if game.appid in steam_map:
                game.lutris_slug = steam_map[game.appid]["slug"]
                logger.debug("Attached Lutris slug %s", game.lutris_slug)
            game.save()
        self.emit("service-games-loaded", self.id)
