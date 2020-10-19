"""Steam service"""
import json
import os
import re
from gettext import gettext as _

from gi.repository import Gio

from lutris import settings
from lutris.database.games import get_games
from lutris.game import Game
from lutris.installer.installer_file import InstallerFile
from lutris.services.base import BaseService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.log import logger
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths
from lutris.util.strings import slugify


class SteamBanner(ServiceMedia):
    service = "steam"
    size = (184, 69)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/banners")
    file_pattern = "%s.jpg"
    api_field = "appid"
    url_pattern = "http://cdn.akamai.steamstatic.com/steam/apps/%s/capsule_184x69.jpg"


class SteamCover(ServiceMedia):
    service = "steam"
    size = (200, 300)
    dest_path = os.path.join(settings.CACHE_DIR, "steam/covers")
    file_pattern = "%s.jpg"
    api_field = "appid"
    url_pattern = "http://cdn.steamstatic.com/steam/apps/%s/library_600x900.jpg"


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
        "cover": SteamCover,
    }
    default_format = "banner"
    is_loading = False

    def load(self):
        """Return importable Steam games"""
        if self.is_loading:
            logger.warning("Steam games are already loading")
            return
        self.is_loading = True
        self.emit("service-games-load")
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
        self.is_loading = False
        logger.debug("Steam games loaded")
        self.emit("service-games-loaded")

    def get_installer_files(self, installer, installer_file_id):
        steam_uri = "$WINESTEAM:%s:." if installer.runner == "winesteam" else "$STEAM:%s:."
        appid = str(installer.script["game"]["appid"])
        return [
            InstallerFile(installer.game_slug, "steam_game", {
                "url": steam_uri % appid,
                "filename": appid
            })
        ]

    def generate_installer(self, db_game):
        """Generate a basic Steam installer"""
        return {
            "name": db_game["name"],
            "version": "Steam",
            "slug": slugify(db_game["name"]) + "-steam",
            "game_slug": slugify(db_game["name"]),
            "runner": "steam",
            "appid": db_game["appid"],
            "script": {
                "game": {"appid": db_game["appid"]}
            }
        }

    def install(self, db_game):
        appid = db_game["appid"]
        db_games = get_games(filters={"steamid": appid, "installed": "1"})
        existing_game = self.match_existing_game(db_games, appid)
        if existing_game:
            logger.debug("Found steam game: %s", existing_game)
            game = Game(existing_game["id"])
            game.save()
            return
        service_installers = self.get_installers_from_api(appid)
        if not service_installers:
            service_installers = [self.generate_installer(db_game)]
        application = Gio.Application.get_default()
        application.show_installer_window(service_installers, service=self, appid=appid)
