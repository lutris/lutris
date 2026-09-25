"""Module for handling the DLsite service"""

import json
import os
from gettext import gettext as _
from typing import Any

from lutris import settings
from lutris.exceptions import AuthenticationError, UnavailableGameError
from lutris.installer import AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.downloader import SimpleDownloader
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger


class DlsiteBanner(ServiceMedia):
    """Game logo"""

    service = "dlsite"
    size = (200, 150)
    dest_path = os.path.join(settings.CACHE_DIR, "dlsite/banners")
    file_patterns = ["%s.jpg"]
    api_field = "image"

    def get_media_url(self, details: dict[str, Any]) -> str:
        work_files = details.get("work_files", {})
        if work_files and "main" in work_files:
            return work_files["main"]
        return ""


class DlsiteGame(ServiceGame):
    """Representation of a DLsite game"""

    service = "dlsite"

    @classmethod
    def new_from_dlsite_game(cls, dlsite_game):
        """Return a DLsite game instance from the API info"""
        service_game = DlsiteGame()
        service_game.appid = str(dlsite_game.get("workno", ""))

        name_dict = dlsite_game.get("name", {})
        # Prefer English name if available, fallback to Japanese, then whatever is first
        name = name_dict.get("en_US") or name_dict.get("ja_JP")
        if not name and name_dict:
            name = next(iter(name_dict.values()))
        if not name:
            name = service_game.appid

        service_game.slug = service_game.appid.lower()
        service_game.name = name
        service_game.details = json.dumps(dlsite_game)
        return service_game


class DlsiteService(OnlineService):
    """Service class for DLsite"""

    id = "dlsite"
    name = _("DLsite")
    icon = "dlsite"
    runner = "wine"
    has_extras = False
    drm_free = True
    medias = {"banner": DlsiteBanner}
    default_format = "banner"

    login_url = "https://play.dlsite.com/login"
    redirect_uris = ["https://play.dlsite.com/"]

    def is_login_complete(self, url):
        """Check if the given URL indicates that login is complete."""
        # Ensure we don't immediately match the login_url itself since it starts with the redirect URI
        if url.startswith(self.login_url):
            return False
        return any(url.startswith(r) for r in self.redirect_uris)

    def get_installed_slug(self, db_game: dict[str, Any]) -> str:
        """Use the RJ code (appid) as the default installation slug instead of the game name."""
        return db_game.get("appid", "").lower() or super().get_installed_slug(db_game)

    cookies_path = os.path.join(settings.CACHE_DIR, ".dlsite.auth")
    cache_path = os.path.join(settings.CACHE_DIR, "dlsite-library.json")

    @property
    def credential_files(self) -> list[str]:
        return [self.cookies_path]

    def login_callback(self, url):
        """Called after the user has logged in successfully"""
        SERVICE_LOGIN.fire(self)

    def is_connected(self) -> bool:
        """Return whether the user is authenticated and if the service is available"""
        if not self.is_authenticated():
            return False
        # Verify session
        url = "https://play.dlsite.com/api/v3/content/count"
        try:
            request = Request(url, headers={"Accept": "application/json"}, cookies=self.load_cookies())
            request.get()
            return True
        except HTTPError:
            return False

    def get_purchases(self) -> list[dict]:
        """Fetch all purchased works"""
        purchases = []
        url = "https://play.dlsite.com/api/v3/content/sales"
        request = Request(url, headers={"Accept": "application/json"}, cookies=self.load_cookies())
        try:
            request.get()
        except HTTPError as ex:
            if ex.code == 401:
                raise AuthTokenExpiredError("DLsite session expired, please log in again") from ex
            logger.error("Failed to fetch DLsite sales: %s", ex)
            return purchases

        data = request.json
        if data:
            purchases.extend(data)

        return purchases

    def get_works(self, work_ids: list[str]) -> list[dict]:
        """Fetch details for a list of work IDs in batches"""
        works = []
        batch_size = 50

        for i in range(0, len(work_ids), batch_size):
            batch = work_ids[i : i + batch_size]
            url = "https://play.dlsite.com/api/v3/content/works"

            request = Request(
                url,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                cookies=self.load_cookies(),
            )
            try:
                request.post(data=json.dumps(batch).encode("utf-8"))
                data = request.json
                if data and "works" in data:
                    works.extend(data["works"])
            except HTTPError as ex:
                logger.error("Failed to fetch DLsite works batch: %s", ex)

        return works

    def get_library(self):
        """Fetch user library from DLsite API"""
        purchases = self.get_purchases()
        work_ids = [p["workno"] for p in purchases if "workno" in p]

        if not work_ids:
            return []

        logger.info("Found %d purchases on DLsite", len(work_ids))
        works = self.get_works(work_ids)

        game_work_types = {"ACG", "ADV", "RPG", "STG", "SLN", "TBL", "PZL", "TYP", "ETC", "QZ"}
        games = [DlsiteGame.new_from_dlsite_game(work) for work in works if work.get("work_type") in game_work_types]
        return games

    def load(self):
        """Load the user game library from the DLsite API"""
        if not self.is_connected():
            logger.error("User not connected to DLsite")
            return []
        try:
            games = self.get_library()
        except AuthTokenExpiredError as ex:
            logger.warning("DLsite session expired during library load")
            raise ex
        for game in games:
            game.save()
        self.match_games()
        return games

    def get_installer_files(self, installer, installer_file_id):
        """Get the download URLs for the game directly from DLsite"""
        import urllib.request
        from urllib.parse import urlparse

        workno = installer.service_appid
        if not workno:
            return []

        works = self.get_works([workno])
        if not works:
            raise UnavailableGameError(_("Could not fetch game details from DLsite"))

        site_id = works[0].get("site_id", "maniax")

        url = f"https://www.dlsite.com/{site_id}/download/=/product_id/{workno}.html"
        logger.info("Fetching DLsite download URL: %s", url)

        cookies = self.load_cookies()
        if not cookies:
            raise AuthenticationError(_("DLsite cookies not found. Please log in again."))

        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with opener.open(req) as response:
                final_url = response.url
                filename = os.path.basename(urlparse(final_url).path)
                if not filename or filename.endswith(".html"):
                    filename = f"{workno}.zip"

        except urllib.error.HTTPError as ex:
            logger.error("Failed to resolve DLsite download: %s", ex)
            raise UnavailableGameError(_("Could not resolve download link. Ensure you own this game.")) from ex

        cookie_str = "; ".join([f"{c.name}={c.value}" for c in cookies])
        cookie_headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

        return [
            InstallerFile(
                installer.game_slug,
                installer_file_id,
                {
                    "url": final_url,
                    "filename": filename,
                    "downloader": lambda f, dl_url=final_url, hdrs=cookie_headers: SimpleDownloader(
                        dl_url, f.download_file, overwrite=True, headers=hdrs
                    ),
                },
            )
        ]

    def generate_installer(self, db_game: dict[str, Any]) -> dict[str, Any]:
        return self._generate_installer(db_game)

    def generate_installers(self, db_game: dict[str, Any]) -> list[dict]:
        return [self._generate_installer(db_game)]

    def _generate_installer(self, db_game: dict[str, Any]) -> dict[str, Any]:
        slug = db_game["slug"]
        game_config = {"exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR/pfx"}
        script = [
            {"task": {"name": "create_prefix", "prefix": "$GAMEDIR/pfx"}},
            {"install_or_extract": "dlsitegame"},
        ]
        return {
            "name": db_game["name"],
            "version": "DLsite",
            "slug": slug,
            "game_slug": self.get_installed_slug(db_game),
            "runner": "wine",
            "appid": db_game["appid"],
            "script": {
                "game": game_config,
                "files": [{"dlsitegame": "N/A:Please download the game manually from DLsite and select the file here"}],
                "installer": script,
            },
        }

    def get_game_release_date(self, db_game: dict) -> str:
        details = db_game.get("details")
        if details:
            sales_date = json.loads(details).get("sales_date")
            regist_date = json.loads(details).get("regist_date")
            date = sales_date or regist_date
            if date and len(date) >= 10:
                # Return as YYYY-MM-DD
                return date[:10]
        return ""
