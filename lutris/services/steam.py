"""Steam service"""
import json
import os
import re
from gettext import gettext as _

from lutris import settings
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame, ServiceMedia
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths


class SteamBanner(ServiceMedia):
    service = "steam"
    size = (184, 69)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/banners")
    file_pattern = "%s.jpg"
    api_field = "appid"
    url_pattern = "http://cdn.akamai.steamstatic.com/steam/apps/%s/capsule_184x69.jpg"


class SteamBannerLarge(ServiceMedia):
    service = "steam"
    size = (460, 215)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/header")
    file_pattern = "%s.jpg"
    api_field = "appid"
    url_pattern = "https://cdn.cloudflare.steamstatic.com/steam/apps/%s/header.jpg"


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
        appid = str(appmanifest.steamid)
        steam_game = SteamGame()
        steam_game.appid = appid
        steam_game.game_id = game_id
        steam_game.name = appmanifest.name
        steam_game.slug = appmanifest.slug
        steam_game.runner = appmanifest.get_runner_name()
        steam_game.details = json.dumps({"appid": appid})
        return steam_game

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


class SteamService(BaseService):

    id = "steam"
    name = _("Steam")
    icon = "steam"
    online = False
    medias = {
        "banner": SteamBanner,
        "banner_large": SteamBannerLarge,
    }
    default_format = "banner"

    def load(self):
        """Return importable Steam games"""
        logger.debug("Loading Steam games from local install")
        games = []
        steamapps_paths = get_steamapps_paths()
        for platform in ('linux', 'windows'):
            for steamapps_path in steamapps_paths[platform]:
                for appmanifest_file in get_appmanifests(steamapps_path):
                    app_manifest = AppManifest(os.path.join(steamapps_path, appmanifest_file))
                    if SteamGame.is_importable(app_manifest):
                        games.append(SteamGame.new_from_steam_game(app_manifest))
        logger.debug("Saving Steam games...")
        for game in games:
            game.save()
        logger.debug("Steam games loaded")
        self.emit("service-games-loaded")
