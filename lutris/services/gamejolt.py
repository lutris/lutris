"""GameJolt service"""

import json
import os
from gettext import gettext as _
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from lutris import settings
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.runners import get_runner_human_name
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.downloader import Downloader
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.strings import slugify

GAMEJOLT_API_URL = "https://gamejolt.com/site-api"
GAMEJOLT_HEADERS = {"x-gj-client-version": "2.0.0"}


class GameJoltCoverart(ServiceMedia):
    """GameJolt game thumbnail"""

    service = "gamejolt"
    size = (315, 178)
    dest_path = os.path.join(settings.CACHE_DIR, "gamejolt/coverart")
    file_patterns = ["%s.webp"]

    def get_media_url(self, details: Dict[str, Any]) -> Optional[str]:
        return details.get("img_thumbnail") or None


class GameJoltCoverartSmall(GameJoltCoverart):
    """GameJolt game thumbnail, smaller"""

    size = (189, 107)


class GameJoltGame(ServiceGame):
    """GameJolt game"""

    service = "gamejolt"

    @classmethod
    def new(cls, game_data):
        """Return a GameJolt game instance from the API info"""
        service_game = GameJoltGame()
        service_game.appid = str(game_data["id"])
        service_game.slug = slugify(game_data["title"])
        service_game.name = game_data["title"]
        service_game.details = json.dumps(game_data)
        return service_game


class GameJoltService(OnlineService):
    """Service class for GameJolt"""

    id = "gamejolt"
    name = _("GameJolt")
    icon = "gamejolt"
    online = True
    drm_free = True
    medias = {
        "coverart_small": GameJoltCoverartSmall,
        "coverart_med": GameJoltCoverart,
    }
    default_format = "coverart_med"

    login_url = "https://gamejolt.com/login"
    redirect_uris = []  # We use is_login_complete() instead
    cookies_path = os.path.join(settings.CACHE_DIR, ".gamejolt.auth")
    cache_path = os.path.join(settings.CACHE_DIR, "gamejolt-library.json")

    login_window_width = 460
    login_window_height = 700

    platforms_by_runner = {"linux": "Linux", "wine": "Windows"}

    def is_login_complete(self, url):
        """Detect login completion for both OAuth and username+password flows.
        After login, GameJolt redirects to the home page regardless of method."""
        return url.rstrip("/") == "https://gamejolt.com"

    def login_callback(self, url):
        """Called after successful login"""
        logger.debug("GameJolt login callback from: %s", url)
        SERVICE_LOGIN.fire(self)

    def is_connected(self):
        """Check if service is connected"""
        if not self.is_authenticated():
            return False
        try:
            response = self._api_request("/web/touch")
            if not isinstance(response, dict):
                return False
            user = response.get("user")
            if not user:
                logger.warning("GameJolt session not valid")
                return False
            logger.debug("GameJolt connected as: %s", user.get("username", "?"))
            return True
        except Exception as ex:
            logger.warning("Not connected to GameJolt: %s", ex)
            return False

    def _api_request(self, path, method="GET", data=None):
        """Make an authenticated request to the GameJolt site API.
        Returns the raw JSON response (envelope with payload, user, etc.)."""
        url = GAMEJOLT_API_URL + path
        cookies = self.load_cookies()
        request = Request(url, headers=GAMEJOLT_HEADERS, cookies=cookies)
        if method == "POST":
            request.post(data or {})
        else:
            request.get()
        return request.json

    def _get_payload(self, response):
        """Extract the payload from an API response envelope."""
        if isinstance(response, dict) and "payload" in response:
            return response["payload"]
        return response

    def _get_username(self):
        """Get the logged in username from the touch endpoint"""
        response = self._api_request("/web/touch")
        if isinstance(response, dict) and response.get("user"):
            return response["user"].get("username")
        return None

    def load(self):
        """Load the user's GameJolt library"""
        if not self.is_connected():
            logger.error("User not connected to GameJolt")
            return

        games = self._get_library_games()
        result = []
        seen = set()
        for game_data in games:
            game_id = game_data.get("id")
            if game_id in seen:
                continue
            seen.add(game_id)

            if not self._has_downloadable_builds(game_data):
                continue

            game = GameJoltGame.new(game_data)
            game.save()
            result.append(game)
        logger.debug("GameJolt: loaded %d games with downloadable builds", len(result))
        return result

    def _get_library_games(self):
        """Fetch games from the user's library, preferring a 'Lutris' playlist"""
        try:
            library = self._api_request("/web/library")
        except HTTPError:
            logger.error("Failed to fetch GameJolt library")
            return []

        if not library:
            return []

        payload = self._get_payload(library)
        if isinstance(payload, dict):
            collections = payload.get("collections", [])
        else:
            collections = []

        # Look for a playlist named "Lutris" (case-insensitive)
        lutris_playlist = None
        for collection in collections:
            if collection.get("name", "").casefold() == "lutris":
                lutris_playlist = collection
                break

        if lutris_playlist:
            playlist_id = lutris_playlist.get("id")
            if playlist_id:
                return self._fetch_playlist_games(playlist_id)

        # No Lutris playlist — fetch followed + owned games
        username = self._get_username()
        if not username:
            logger.error("Could not determine GameJolt username")
            return []

        followed = self._fetch_paginated_games(f"/web/library/games/followed/@{username}")
        owned = self._fetch_paginated_games(f"/web/library/games/owned/@{username}")

        # Merge, deduplicating by ID
        seen_ids = set()
        merged = []
        for game in followed + owned:
            gid = game.get("id")
            if gid not in seen_ids:
                seen_ids.add(gid)
                merged.append(game)
        return merged

    def _fetch_playlist_games(self, playlist_id):
        """Fetch all games from a specific playlist"""
        return self._fetch_paginated_games(f"/web/library/games/playlist/{playlist_id}")

    def _fetch_paginated_games(self, path):
        """Fetch games from a paginated GameJolt API endpoint"""
        games = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            url = f"{path}{separator}page={page}"
            try:
                response = self._api_request(url)
            except HTTPError:
                logger.error("Failed to fetch games from %s", path)
                break

            if not response:
                break

            payload = self._get_payload(response)
            if isinstance(payload, dict):
                page_games = payload.get("games", [])
                per_page = payload.get("perPage", 0)
            else:
                page_games = []
                per_page = 0

            if not page_games:
                break

            games.extend(page_games)

            if not per_page or len(page_games) < per_page:
                break
            page += 1
        return games

    @staticmethod
    def _has_downloadable_builds(game_data):
        """Check if a game has compatibility info indicating downloadable builds"""
        compatibility = game_data.get("compatibility")
        if not compatibility:
            return False
        for key in ("os_linux", "os_linux_64", "os_windows", "os_windows_64"):
            if compatibility.get(key):
                return True
        return False

    @staticmethod
    def _get_runners_from_compatibility(compatibility):
        """Return list of runners based on compatibility dict"""
        runners = []
        if not compatibility:
            return runners
        if compatibility.get("os_linux") or compatibility.get("os_linux_64"):
            runners.append("linux")
        if compatibility.get("os_windows") or compatibility.get("os_windows_64"):
            runners.append("wine")
        return runners

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        details = json.loads(db_game["details"])
        compatibility = details.get("compatibility", {})
        runners = self._get_runners_from_compatibility(compatibility)
        if runners:
            return self._generate_installer(runners[0], db_game)
        return {}

    def generate_installers(self, db_game: Dict[str, Any]) -> List[dict]:
        details = json.loads(db_game["details"])
        compatibility = details.get("compatibility", {})
        runners = self._get_runners_from_compatibility(compatibility)
        installers = [self._generate_installer(runner, db_game) for runner in runners]

        if len(installers) > 1:
            for installer in installers:
                runner_human_name = get_runner_human_name(installer["runner"])
                installer["version"] += " " + (runner_human_name or installer["runner"])

        return installers

    def _generate_installer(self, runner, db_game: Dict[str, Any]) -> Dict[str, Any]:
        if runner == "linux":
            game_config = {"exe": AUTO_ELF_EXE}
            script = [
                {"extract": {"file": "gamejoltbuild", "dst": "$CACHE"}},
                {"merge": {"src": "$CACHE", "dst": "$GAMEDIR"}},
            ]
        elif runner == "wine":
            slug = db_game["slug"]
            game_config = {"exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR/pfx"}
            script = [
                {"task": {"name": "create_prefix"}},
                {
                    "extract_or_run": {
                        "file": "gamejoltbuild",
                        "dst": "$CACHE",
                        "merge_dst": f"$GAMEDIR/{slug}",
                    }
                },
            ]
        else:
            return {}

        return {
            "name": db_game["name"],
            "version": "GameJolt",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": runner,
            "gamejoltid": db_game["appid"],
            "script": {
                "files": [{"gamejoltbuild": "N/A:Select the build from GameJolt"}],
                "game": game_config,
                "installer": script,
            },
        }

    def get_installed_runner_name(self, db_game: Dict[str, Any]) -> str:
        details = json.loads(db_game["details"])
        compatibility = details.get("compatibility", {})
        runners = self._get_runners_from_compatibility(compatibility)
        return runners[0] if runners else ""

    def get_game_platforms(self, db_game: dict) -> List[str]:
        details = db_game.get("details")
        if not details:
            return []
        details = json.loads(details)
        compatibility = details.get("compatibility", {})
        runners = self._get_runners_from_compatibility(compatibility)
        return [self.platforms_by_runner[r] for r in runners]

    def _fetch_game_overview(self, appid):
        """Fetch and return game overview payload from the API"""
        try:
            response = self._api_request(f"/web/discover/games/overview/{appid}")
            return self._get_payload(response)
        except HTTPError as ex:
            logger.error("Failed to fetch game overview for %s: %s", appid, ex)
            return None

    def get_installer_files(self, installer, installer_file_id):
        """Replace the placeholder file with a download URL from GameJolt"""
        appid = installer.service_appid
        runner = installer.runner
        files = []

        overview = self._fetch_game_overview(appid)
        if not overview:
            return files

        builds = overview.get("builds", [])
        if not builds:
            logger.warning("No builds found for GameJolt game %s", appid)
            return files

        # Filter builds by platform
        matching_builds = []
        for build in builds:
            if runner == "linux" and (build.get("os_linux") or build.get("os_linux_64")):
                matching_builds.append(build)
            elif runner == "wine" and (build.get("os_windows") or build.get("os_windows_64")):
                matching_builds.append(build)

        if not matching_builds:
            logger.warning("No matching builds for runner %s in game %s", runner, appid)
            return files

        # Pick the best build: prefer 64-bit, non-demo, largest file
        best_build = self._pick_best_build(matching_builds, runner)
        if not best_build:
            return files

        build_id = best_build.get("id")
        if not build_id:
            return files

        # Get download URL
        try:
            dl_response = self._get_payload(
                self._api_request(
                    f"/web/discover/games/builds/get-download-url/{build_id}",
                    method="POST",
                )
            )
        except HTTPError as ex:
            logger.error("Failed to get download URL for build %s: %s", build_id, ex)
            return files

        if isinstance(dl_response, dict):
            download_url = dl_response.get("url") or dl_response.get("downloadUrl")
        else:
            download_url = None

        if not download_url:
            logger.warning("No download URL returned for build %s", build_id)
            return files

        # Use the filename from the download URL rather than primary_file,
        # since GameJolt wraps downloads in tar.gz compression.
        url_path = urlparse(download_url).path
        filename = os.path.basename(url_path) if url_path else "gamejoltbuild"

        cookies = self.load_cookies()
        cookie_headers = {}
        if cookies:
            cookie_headers = {"Cookie": "; ".join(f"{c.name}={c.value}" for c in cookies)}

        files.append(
            InstallerFile(
                installer.game_slug,
                installer_file_id,
                {
                    "url": download_url,
                    "filename": filename,
                    "downloader": lambda f, url=download_url, headers=cookie_headers: Downloader(
                        url, f.download_file, overwrite=True, headers=headers
                    ),
                },
            )
        )
        return files

    def _pick_best_build(self, builds, runner):
        """Pick the best build from a list of matching builds"""

        def build_score(build):
            score = 0
            # Prefer 64-bit
            if runner == "linux" and build.get("os_linux_64"):
                score += 10
            elif runner == "wine" and build.get("os_windows_64"):
                score += 10
            # Prefer non-demo
            if build.get("type") != "downloadable" or build.get("is_demo"):
                score -= 20
            # Prefer larger files (more likely to be complete)
            primary_file = build.get("primary_file", {})
            if primary_file:
                score += min(int(primary_file.get("filesize", 0)) // (1024 * 1024), 100)
            return score

        return max(builds, key=build_score)

    def get_store_url(self, db_game: dict) -> str:
        details = db_game.get("details")
        if details:
            game_data = json.loads(details)
            slug = game_data.get("slug", "")
            game_id = game_data.get("id", "")
            if slug and game_id:
                return f"https://gamejolt.com/games/{slug}/{game_id}"
        return ""

    def get_installed_slug(self, db_game):
        return db_game["slug"]
