"""Module for handling the Zoom service"""

import json
import os
import typing
from gettext import gettext as _
from typing import Any, Dict, List, Tuple

from lutris import settings
from lutris.exceptions import AuthenticationError
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.runners import get_runner_human_name
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import i18n, system
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.strings import computer_size

if typing.TYPE_CHECKING:
    from lutris.installer.installer import LutrisInstaller


class ZoomBanner(ServiceMedia):
    """Small size game logo"""

    service = "zoomplatform"
    size = (200, 300)
    dest_path = os.path.join(settings.CACHE_DIR, "zoom/banners/")
    file_patterns = ["%s.jpg"]
    api_field = "image"
    url_pattern = "%s"


class ZoomGame(ServiceGame):
    """Representation of a Zoom game"""

    service = "zoomplatform"

    @classmethod
    def new_from_zoom_game(cls, zoom_game):
        """Return a Zoom game instance from the API info"""
        service_game = ZoomGame()
        service_game.appid = str(zoom_game["product"]["id"])
        service_game.game_id = str(zoom_game["product"]["id"])
        service_game.slug = zoom_game["product"]["slug"]
        service_game.name = zoom_game["product"]["name"]
        details = zoom_game["product"]
        details["image"] = zoom_game["product"]["search_image"]
        details["slug"] = zoom_game["product"]["slug"]
        service_game.details = json.dumps(details)
        return service_game


class ZoomService(OnlineService):
    """Service class for ZOOM Platform"""

    id = "zoomplatform"
    name = _("ZOOM Platform")
    icon = "zoom"
    has_extras = True
    drm_free = True
    medias = {"banner": ZoomBanner}
    default_format = "banner"

    embed_url = "https://www.zoom-platform.com"
    api_url = "https://www.zoom-platform.com"

    redirect_uris = []

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

    def make_request(self, url: str) -> Any:
        """Send a cookie authenticated HTTP request to Zoom"""
        request = Request(url, cookies=self.load_cookies())
        request.get()
        if request.content.startswith(b"<"):
            raise AuthenticationError("Token expired, please log in again")
        return request.json

    def make_api_request(self, url: str) -> Any:
        """Send a token authenticated request to Zoom"""
        request = Request(url, cookies=self.load_cookies())
        request.get()
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

    def get_extras(self, appid: str) -> Dict[str, List[dict]]:
        """Return a list of bonus content available for a Zoom ID and its DLCs"""
        logger.debug("Download extras for Zoom ID %s and its DLCs", appid)
        return {"extras": self._get_extra(appid)}

    def _get_extra(self, appid: str) -> List[dict]:
        # fetch the extra files urls using https://www.zoom-platform.com/public/profile/product/ + appid
        # and then parse the response to get the download url

        product_url = "https://www.zoom-platform.com/public/profile/product/%s" % appid
        json = self.make_request(product_url)
        print(json)

        all_extras = []
        for extra_type in ["manual", "misc", "soundtrack"]:
            files = json["files"][extra_type]
            print(files)

            for file in files:
                extra_file_dict = {
                    "name": file["name"],
                    "url": file["file_url"],
                    "filename": file["name"],  # we cannot use "path" here as it can include a directory
                    "total_size": computer_size(file["file_size"]),
                }
                all_extras.append(extra_file_dict)
        return all_extras

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("Generating installer for %s", db_game)
        details = json.loads(db_game["details"])
        platforms = details["operating_systems"]
        if "linux" in platforms:
            return self._generate_installer("linux", db_game)
        else:
            return self._generate_installer("wine", db_game)

    def generate_installers(self, db_game: Dict[str, Any]) -> List[dict]:
        details = json.loads(db_game["details"])
        platforms = details["operating_systems"]

        installers = []

        if "linux" in platforms:
            installers.append(self._generate_installer("linux", db_game))

        if "windows" in platforms:
            installers.append(self._generate_installer("wine", db_game))

        if len(installers) > 1:
            for installer in installers:
                runner_human_name = get_runner_human_name(installer["runner"])
                installer["version"] += " " + (runner_human_name or installer["runner"])

        return installers

    def _generate_installer(self, runner: str, db_game: Dict[str, Any]) -> Dict[str, Any]:
        slug = db_game["slug"]
        system_config = {}
        if runner == "linux":
            game_config = {"exe": AUTO_ELF_EXE}
            script = [
                {"extract": {"file": "zoominstaller", "dst": "$CACHE"}},
                {"merge": {"src": "$CACHE", "dst": "$GAMEDIR"}},
            ]
        else:
            game_config = {"exe": AUTO_WIN32_EXE}
            script = [
                {"autosetup_gog_game": "zoominstaller"},
            ]
        return {
            "name": db_game["name"],
            "version": "Zoom",
            "slug": slug,
            "game_slug": self.get_installed_slug(db_game),
            "runner": runner,
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
        platform = installer.runner
        if platform == "wine":
            platform = "windows"

        installer_files = self._get_installers(platform, installer.game_slug, installer.service_appid)
        files = [InstallerFileCollection(installer.game_slug, installer_file_id, installer_files)]
        extras = []

        if selected_extras:
            for selected_extra in selected_extras:
                extras.append(InstallerFile(installer.game_slug, selected_extra["name"], selected_extra))

        return files, extras

    def _get_installers(self, platform: str, game_slug: str, appid: str) -> List[InstallerFile]:
        # fetch the installer url using https://www.zoom-platform.com/public/profile/product/ + appid
        # and then parse the response to get the download url

        product_url = "https://www.zoom-platform.com/public/profile/product/%s" % appid
        json = self.make_request(product_url)
        # print(json)

        file_list = []
        files = json["files"][platform]
        print(files)
        assert len(files) == 1, "More than one file found for %s" % platform
        installer_file_dict = {
            "url": files[0]["file_url"],
            "filename": files[0]["name"],
            "total_size": computer_size(files[0]["file_size"]),
        }

        installer_file = InstallerFile(
            game_slug,
            "zoominstaller",
            installer_file_dict,
        )
        file_list.append(installer_file)
        return file_list

    def get_service_game(self, zoom_game: dict) -> ZoomGame:
        return ZoomGame.new_from_zoom_game(zoom_game)

    def get_game_details(self, product_id: str) -> dict:
        logger.debug("Getting game details for %s", product_id)
        return {}

    def get_installed_runner_name(self, db_game: dict) -> str:
        platforms = [platform.casefold() for platform in self.get_game_platforms(db_game)]
        return "linux" if "linux" in platforms else "wine"
