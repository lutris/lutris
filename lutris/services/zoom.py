"""Module for handling the Zoom service"""

import json
import os
import time
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
from lutris.util import system
from lutris.util.http import Request
from lutris.util.log import logger
from lutris.util.strings import computer_size

if typing.TYPE_CHECKING:
    from lutris.installer.installer import LutrisInstaller


class ZoomCover(ServiceMedia):
    """Small size game logo"""

    service = "zoomplatform"
    size = (200, 300)
    dest_path = os.path.join(settings.CACHE_DIR, "zoom/cover/")
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
        service_game.appid = str(zoom_game["id"])
        service_game.game_id = str(zoom_game["id"])
        service_game.slug = zoom_game["slug"]
        service_game.name = zoom_game["name"]
        details = zoom_game
        details["image"] = zoom_game["poster_url"]
        details["slug"] = zoom_game["slug"]
        service_game.details = json.dumps(details)
        return service_game


class ZoomService(OnlineService):
    """Service class for ZOOM Platform"""

    id = "zoomplatform"
    name = _("ZOOM Platform")
    icon = "zoom"
    has_extras = True
    drm_free = True
    medias = {"coverart": ZoomCover}
    default_format = "coverart"

    embed_url = "https://www.zoom-platform.com"
    api_url = "https://www.zoom-platform.com"

    redirect_uris = ["https://www.zoom-platform.com/account?li_token="]

    login_success_url = "https://www.zoom-platform.com/account?li_token="
    token_path = os.path.join(settings.CACHE_DIR, ".zoom.token")
    cookies_path = os.path.join(settings.CACHE_DIR, ".zoom.auth")
    cache_path = os.path.join(settings.CACHE_DIR, "zoom-library.json")

    runner_to_os_dict = {"wine": "windows", "linux": "linux"}

    @property
    def login_url(self):
        """Return authentication URL"""
        return f"{self.embed_url}/login?li=lutris&return_li_token=true"

    @property
    def credential_files(self) -> List[str]:
        return [self.cookies_path, self.token_path]

    def is_connected(self) -> bool:
        """Return whether the user is authenticated and if the service is available"""

        try:
            request = self.make_request(f"{self.api_url}/li/loggedin")
        except AuthenticationError:
            logger.debug("User is not authenticated")
            return False

        logger.debug("User is authenticated: %s", request)
        return True

    def is_authenticated(self):
        return self.is_connected()

    def load(self) -> List[ZoomGame]:
        """Load the user game library from the Zoom API"""
        if not self.is_connected():
            logger.error("User not connected to Zoom")
            return []
        games = [ZoomGame.new_from_zoom_game(game) for game in self.get_library()]
        for game in games:
            game.save()
        self.match_games()
        return games

    def login_callback(self, url) -> None:
        if "li_token=" not in url:
            logger.error("Login callback URL does not contain 'li_token'")
            return

        token = url.split("li_token=")[-1]
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(token)

        assert not self.is_login_in_progress
        SERVICE_LOGIN.fire(self)

    def load_token(self) -> str:
        """Load token from disk"""
        if not os.path.exists(self.token_path):
            raise AuthenticationError("No Zoom token available")

        with open(self.token_path, encoding="utf-8") as token_file:
            token_content = token_file.read()

        if not token_content:
            raise AuthenticationError("No Zoom token available")

        return token_content

    def make_request(self, url: str) -> Any:
        """Send a token authenticated HTTP request to Zoom"""

        token = self.load_token()
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}

        request = Request(url, headers=headers)
        request.get()
        return request.json

    def get_library(self) -> List[Dict]:
        """Return the user's library of Zoom games"""
        if system.path_exists(self.cache_path):
            logger.debug("Returning cached Zoom library")
            with open(self.cache_path, "r", encoding="utf-8") as zoom_cache:
                return json.load(zoom_cache)

        url = f"{self.api_url}/li/games"
        response = self.make_request(url)
        current_page = response.get("current_page", 0)
        total_pages = response.get("total_pages", 0)

        games = response["games"]
        while current_page < total_pages - 1:
            time.sleep(1)  # Avoid hitting the API too fast, until HTTP 429 is handled in the Request class
            logger.debug("Fetching additional pages of Zoom library")
            current_page += 1
            next_page_url = f"{url}?page={current_page}"
            response = self.make_request(next_page_url)
            games.extend(response["games"])

        # print(games)
        with open(self.cache_path, "w", encoding="utf-8") as zoom_cache:
            json.dump(games, zoom_cache)

        return games

    def get_extras(self, appid: str) -> Dict[str, List[dict]]:
        """Return a list of bonus content available for a Zoom ID and its DLCs"""
        logger.debug("Download extras for Zoom ID %s and its DLCs", appid)
        return {"extras": self._get_extra(appid)}

    def _get_extra(self, appid: str) -> List[dict]:
        # fetch the extra files urls and then parse the response to get the download url

        files_request = self.make_request(f"{self.api_url}/li/game/{appid}/files")
        # print(product_request)

        all_extras = []
        for extra_type in ["manual", "misc", "soundtrack"]:
            files = files_request[extra_type]
            for file in files:
                download_request = self.make_request(f"{self.api_url}/li/download/{file['id']}")
                extra_file_dict = {
                    "name": file["name"],
                    "url": download_request["url"],
                    "filename": file["name"],  # we cannot use "path" here as it can include a directory
                    "total_size": computer_size(file["size"]),
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
                {"autosetup_zoom_platform": "zoominstaller"},
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
        # fetch the installer url and then parse the response to get the download url

        files_request = self.make_request(f"{self.api_url}/li/game/{appid}/files")
        # print(json)

        file_list = []
        files = files_request[platform]
        print(files)
        assert len(files) == 1, "More than one file found for %s" % platform  # TODO: Handle multiple files
        json = self.make_request(f"{self.api_url}/li/download/{files[0]['id']}")

        installer_file_dict = {
            "url": json["url"],
            "filename": files[0]["name"],
            "total_size": computer_size(files[0]["size"]),
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
