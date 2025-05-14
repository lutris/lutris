"""Module for handling the Zoom service"""

import json
import os
import time
import typing
from gettext import gettext as _
from typing import Any, Dict, List, Tuple

from lutris import settings
from lutris.exceptions import AuthenticationError
from lutris.installer import AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import i18n, system
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.strings import computer_size

if typing.TYPE_CHECKING:
    from lutris.installer.installer import LutrisInstaller


class ZoomSmallBanner(ServiceMedia):
    """Small size game logo"""

    service = "zoom"
    dest_path = os.path.join(settings.CACHE_DIR, "zoom/banners/small")
    file_patterns = ["%s.jpg"]
    api_field = "image"
    url_pattern = "%s"


class ZoomMediumBanner(ZoomSmallBanner):
    """Medium size game logo"""

    size = (200, 300)
    dest_path = os.path.join(settings.CACHE_DIR, "zoom/banners/medium")


class ZoomGame(ServiceGame):
    """Representation of a Zoom game"""

    service = "zoom"

    @classmethod
    def new_from_zoom_game(cls, zoom_game):
        """Return a Zoom game instance from the API info"""
        service_game = ZoomGame()
        logger.debug("Creating new Zoom game from %s", zoom_game)
        service_game.appid = str(zoom_game["product"]["id"])
        service_game.game_id = str(zoom_game["product"]["id"])
        service_game.slug = zoom_game["product"]["slug"]
        service_game.name = zoom_game["product"]["name"]

        details = {"image": zoom_game["product"]["search_image"]}
        service_game.details = json.dumps(details)
        return service_game


class ZoomService(OnlineService):
    """Service class for Zoom"""

    id = "zoom"
    name = _("Zoom")
    icon = "zoom"
    has_extras = False
    drm_free = True
    medias = {"banner": ZoomMediumBanner}
    default_format = "banner"

    embed_url = "https://www.zoom-platform.com"
    api_url = "https://www.zoom-platform.com"

    client_id = "46899977096215655"
    client_secret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    redirect_uris = ["https://abc.com"]

    login_success_url = "https://www.zoom-platform.com"
    cookies_path = os.path.join(settings.CACHE_DIR, ".zoom.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".zoom.token")
    cache_path = os.path.join(settings.CACHE_DIR, "zoom-library.json")

    runner_to_os_dict = {"wine": "windows", "linux": "linux"}

    def __init__(self):
        super().__init__()

        zoom_locales = {
            "en": "en-US",
            "de": "de-DE",
            "fr": "fr-FR",
            "pl": "pl-PL",
            "ru": "ru-RU",
            "zh": "zh-Hans",
        }
        self.locale = zoom_locales.get(i18n.get_lang(), "en-US")

    @property
    def login_url(self):
        """Return authentication URL"""
        return "https://www.zoom-platform.com/login"

    @property
    def credential_files(self) -> List[str]:
        return [self.cookies_path, self.token_path]

    def is_connected(self) -> bool:
        """Return whether the user is authenticated and if the service is available"""
        if self.load_cookies() is None:
            logger.debug("No cookies found")
            return False

        for coookie in self.load_cookies():
            if coookie.name == "zoom_platform_session":
                return True

        return False

    def is_authenticated(self):
        return self.is_connected()

    def load(self) -> List[ZoomGame]:
        """Load the user game library from the Zoom API"""
        if not self.is_connected():
            logger.error("User not connected to Zoom")
            return []
        games = [ZoomGame.new_from_zoom_game(game) for game in self.get_library().values()]
        for game in games:
            game.save()
        self.match_games()
        return games

    def login_callback(self, url) -> None:
        assert not self.is_login_in_progress
        return self.request_token(url)

    def request_token(self, url: str = "", refresh_token: str = "") -> None:
        SERVICE_LOGIN.fire(self)

    def load_token(self) -> dict:
        """Load token from disk"""
        if not os.path.exists(self.token_path):
            raise AuthenticationError("No Zoom token available")

        with open(self.token_path, encoding="utf-8") as token_file:
            token_content = json.loads(token_file.read())

        if not token_content:
            raise AuthenticationError("No Zoom token available")

        return token_content

    def get_token_age(self) -> float:
        """Return age of token"""
        token_stat = os.stat(self.token_path)
        token_modified = token_stat.st_mtime
        return time.time() - token_modified

    def make_request(self, url: str) -> Any:
        """Send a cookie authenticated HTTP request to Zoom"""
        request = Request(url, cookies=self.load_cookies())
        request.get()
        if request.content.startswith(b"<"):
            raise AuthenticationError("Token expired, please log in again")
        return request.json

    def make_api_request(self, url: str) -> Any:
        """Send a token authenticated request to Zoom"""
        token = self.load_token()

        # if self.get_token_age() > 2600:
        #    self.request_token(refresh_token=token["refresh_token"])
        #    token = self.load_token()
        headers = {"Authorization": "Bearer " + token["access_token"]}
        request = Request(url, headers=headers, cookies=self.load_cookies())
        request.get()
        logger.debug(request)
        logger.debug("Out: %s", request.json)
        return request.json

    def get_user_data(self) -> dict:
        """Return Zoom profile information"""
        url = "https://www.zoom-platform.com/account/library"
        return self.make_api_request(url)

    def get_library(self) -> Dict:
        """Return the user's library of Zoom games"""
        if system.path_exists(self.cache_path):
            logger.debug("Returning cached Zoom library")
            with open(self.cache_path, "r", encoding="utf-8") as zoom_cache:
                return json.load(zoom_cache)

        url = self.embed_url + "/public/profile/products"
        games = self.make_request(url)
        with open(self.cache_path, "w", encoding="utf-8") as zoom_cache:
            json.dump(games, zoom_cache)

        return games

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Generating installer for %s", db_game)

        system_config = {}
        game_config = {"exe": AUTO_WIN32_EXE}
        script = [
            {"autosetup_gog_game": "zoominstaller"},
        ]

        return {
            "name": db_game["name"],
            "version": "Zoom",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": "wine",
            "zoomid": db_game["appid"],
            "script": {
                "game": game_config,
                "system": system_config,
                "files": [{"zoominstaller": "N/A:Select the installer from Zoom"}],
                "installer": script,
            },
        }

    def get_installer_files(
        self, installer: "LutrisInstaller", installer_file_id: str, selected_extras: List[dict]
    ) -> Tuple[List[InstallerFileCollection], List[InstallerFile]]:
        logger.debug("Getting installer files for %s", installer_file_id)
        logger.debug("Installer: %s", installer)

        installer_files = self._get_installer(installer.game_slug, installer.service_appid)
        files = [InstallerFileCollection(installer.game_slug, installer_file_id, installer_files)]

        return files, []

    def _get_installer(self, game_slug: str, appid: str) -> List[InstallerFile]:
        # fetch the installer url using https://www.zoom-platform.com/public/profile/product/ + appid
        # and then parse the response to get the download url

        product_url = "https://www.zoom-platform.com/public/profile/product/%s" % appid
        json = self.make_request(product_url)
        logger.debug(json["files"]["windows"][0]["file_url"])
        installer_file_dict = {
            "url": json["files"]["windows"][0]["file_url"],
            "filename": json["files"]["windows"][0]["name"],
            "total_size": computer_size(json["files"]["windows"][0]["file_size"]),
        }

        installer_file = InstallerFile(
            game_slug,
            "zoominstaller",
            installer_file_dict,
        )
        file_list = [installer_file]
        return file_list

    def get_service_game(self, zoom_game: dict) -> ZoomGame:
        return ZoomGame.new_from_zoom_game(zoom_game)

    def get_game_details(self, product_id: str) -> dict:
        logger.debug("Getting game details for %s", product_id)
        return {}

    def get_installed_runner_name(self, db_game: dict) -> str:
        platforms = [platform.casefold() for platform in self.get_game_platforms(db_game)]
        return "linux" if "linux" in platforms else "wine"
