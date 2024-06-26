"""Module for handling the GOG service"""

import json
import os
import time
from collections import defaultdict
from gettext import gettext as _
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse

from lxml import etree

from lutris import settings
from lutris.exceptions import AuthenticationError, UnavailableGameError
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.installer.installer_file_collection import InstallerFileCollection
from lutris.runners import get_runner_human_name
from lutris.services.base import SERVICE_LOGIN, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import i18n, system
from lutris.util.http import HTTPError, Request, UnauthorizedAccessError
from lutris.util.log import logger
from lutris.util.strings import human_size, slugify


class GogSmallBanner(ServiceMedia):
    """Small size game logo"""

    service = "gog"
    size = (100, 60)
    dest_path = os.path.join(settings.CACHE_DIR, "gog/banners/small")
    file_patterns = ["%s.jpg"]
    api_field = "image"
    url_pattern = "https:%s_prof_game_100x60.jpg"


class GogMediumBanner(GogSmallBanner):
    """Medium size game logo"""

    size = (196, 110)
    dest_path = os.path.join(settings.CACHE_DIR, "gog/banners/medium")
    url_pattern = "https:%s_196.jpg"


class GogLargeBanner(GogSmallBanner):
    """Big size game logo"""

    size = (392, 220)
    dest_path = os.path.join(settings.CACHE_DIR, "gog/banners/large")
    url_pattern = "https:%s_392.jpg"


class GOGGame(ServiceGame):
    """Representation of a GOG game"""

    service = "gog"

    @classmethod
    def new_from_gog_game(cls, gog_game):
        """Return a GOG game instance from the API info"""
        service_game = GOGGame()
        service_game.appid = str(gog_game["id"])
        service_game.slug = gog_game["slug"]
        service_game.name = gog_game["title"]
        service_game.details = json.dumps(gog_game)
        return service_game


class GOGService(OnlineService):
    """Service class for GOG"""

    id = "gog"
    name = _("GOG")
    icon = "gog"
    has_extras = True
    drm_free = True
    medias = {"banner_small": GogSmallBanner, "banner": GogMediumBanner, "banner_large": GogLargeBanner}
    default_format = "banner"

    embed_url = "https://embed.gog.com"
    api_url = "https://api.gog.com"

    client_id = "46899977096215655"
    client_secret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    redirect_uri = "https://embed.gog.com/on_login_success?origin=client"

    login_success_url = "https://www.gog.com/on_login_success"
    cookies_path = os.path.join(settings.CACHE_DIR, ".gog.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".gog.token")
    cache_path = os.path.join(settings.CACHE_DIR, "gog-library.json")

    runner_to_os_dict = {"wine": "windows", "linux": "linux"}

    def __init__(self):
        super().__init__()

        gog_locales = {
            "en": "en-US",
            "de": "de-DE",
            "fr": "fr-FR",
            "pl": "pl-PL",
            "ru": "ru-RU",
            "zh": "zh-Hans",
        }
        self.locale = gog_locales.get(i18n.get_lang(), "en-US")

    @property
    def login_url(self):
        """Return authentication URL"""
        params = {
            "client_id": self.client_id,
            "layout": "client2",
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        return "https://auth.gog.com/auth?" + urlencode(params)

    @property
    def credential_files(self):
        return [self.cookies_path, self.token_path]

    def is_connected(self):
        """Return whether the user is authenticated and if the service is available"""
        if not self.is_authenticated():
            return False
        try:
            user_data = self.get_user_data()
        except UnauthorizedAccessError:
            logger.warning("GOG token is invalid")
            return False
        return user_data and "username" in user_data

    def load(self):
        """Load the user game library from the GOG API"""
        if not self.is_connected():
            logger.error("User not connected to GOG")
            return
        games = [GOGGame.new_from_gog_game(game) for game in self.get_library()]
        for game in games:
            game.save()
        self.match_games()
        return games

    def login_callback(self, url):
        return self.request_token(url)

    def request_token(self, url="", refresh_token=""):
        """Get authentication token from GOG"""
        if refresh_token:
            grant_type = "refresh_token"
            extra_params = {"refresh_token": refresh_token}
        else:
            grant_type = "authorization_code"
            parsed_url = urlparse(url)
            response_params = dict(parse_qsl(parsed_url.query))
            if "code" not in response_params:
                logger.error("code not received from GOG")
                logger.error(response_params)
                return
            extra_params = {
                "code": response_params["code"],
                "redirect_uri": self.redirect_uri,
            }

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": grant_type,
        }
        params.update(extra_params)
        url = "https://auth.gog.com/token?" + urlencode(params)
        request = Request(url)
        try:
            request.get()
        except HTTPError as http_error:
            logger.error(http_error)
            logger.error("Failed to get token.")
            logger.warning("Clearing existing credentials")
            self.logout()
            return

        token = request.json
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(json.dumps(token))
        if not refresh_token:
            SERVICE_LOGIN.fire(self)

    def load_token(self):
        """Load token from disk"""
        if not os.path.exists(self.token_path):
            raise AuthenticationError("No GOG token available")
        with open(self.token_path, encoding="utf-8") as token_file:
            token_content = json.loads(token_file.read())
        return token_content

    def get_token_age(self):
        """Return age of token"""
        token_stat = os.stat(self.token_path)
        token_modified = token_stat.st_mtime
        return time.time() - token_modified

    def make_request(self, url):
        """Send a cookie authenticated HTTP request to GOG"""
        request = Request(url, cookies=self.load_cookies())
        request.get()
        if request.content.startswith(b"<"):
            raise AuthenticationError("Token expired, please log in again")
        return request.json

    def make_api_request(self, url):
        """Send a token authenticated request to GOG"""
        try:
            token = self.load_token()
        except AuthenticationError:
            return
        if self.get_token_age() > 2600:
            self.request_token(refresh_token=token["refresh_token"])
            token = self.load_token()
            if not token:
                logger.warning(
                    "Request to %s cancelled because the GOG token could not be acquired",
                    url,
                )
                return
        headers = {"Authorization": "Bearer " + token["access_token"]}
        request = Request(url, headers=headers, cookies=self.load_cookies())
        try:
            request.get()
        except HTTPError:
            logger.error("Failed to request %s", url)
            return
        return request.json

    def get_user_data(self):
        """Return GOG profile information"""
        url = "https://embed.gog.com/userData.json"
        return self.make_api_request(url)

    def get_library(self):
        """Return the user's library of GOG games"""
        if system.path_exists(self.cache_path):
            logger.debug("Returning cached GOG library")
            with open(self.cache_path, "r", encoding="utf-8") as gog_cache:
                return json.load(gog_cache)

        total_pages = 1
        games = []
        page = 1
        while page <= total_pages:
            products_response = self.get_products_page(page=page)
            page += 1
            total_pages = products_response["totalPages"]
            games += products_response["products"]
        with open(self.cache_path, "w", encoding="utf-8") as gog_cache:
            json.dump(games, gog_cache)
        return games

    def get_service_game(self, gog_game):
        return GOGGame.new_from_gog_game(gog_game)

    def get_products_page(self, page=1, search=None):
        """Return a single page of games"""
        if not self.is_authenticated():
            raise AuthenticationError("User is not logged in")
        params = {"mediaType": "1"}
        if page:
            params["page"] = page
        if search:
            params["search"] = search
        url = self.embed_url + "/account/getFilteredProducts?" + urlencode(params)
        return self.make_request(url)

    def get_game_dlcs(self, product_id):
        """Return the list of DLC products for a game"""
        game_details = self.get_game_details(product_id)
        if not game_details["dlcs"]:
            return []
        all_products_url = game_details["dlcs"]["expanded_all_products_url"]
        return self.make_api_request(all_products_url)

    def get_game_details(self, product_id):
        """Return game information for a given game"""
        if not product_id:
            raise ValueError("Missing product ID")
        logger.info("Getting game details for %s", product_id)
        url = "{}/products/{}?expand=downloads&locale={}".format(self.api_url, product_id, self.locale)
        return self.make_api_request(url)

    def get_download_info(self, downlink):
        """Return file download information, a list of dict containing the 'url' and
        'filename' for each file."""
        logger.info("Getting download info for %s", downlink)
        try:
            response = self.make_api_request(downlink)
        except HTTPError as ex:
            logger.error("HTTP error: %s", ex)
            return []
        if not response:
            logger.error("No download info obtained for %s", downlink)
            return []

        expanded = []
        for field in ("checksum", "downlink"):
            field_url = response[field]
            parsed = urlparse(field_url)
            query = dict(parse_qsl(parsed.query))
            filename = os.path.basename(query.get("path") or parsed.path)
            expanded.append({"url": response[field], "filename": filename})
        return expanded

    def get_downloads(self, gogid):
        """Return all available downloads for a GOG ID"""
        if not gogid:
            logger.warning("Unable to get GOG data because no GOG ID is available")
            return {}
        gog_data = self.get_game_details(gogid)
        if not gog_data:
            logger.warning("Unable to get GOG data for game %s", gogid)
            return {}
        return gog_data["downloads"]

    def get_extras(self, gogid):
        """Return a list of bonus content available for a GOG ID and its DLCs"""
        logger.debug("Download extras for GOG ID %s and its DLCs", gogid)
        game = self.get_game_details(gogid)
        if not game:
            logger.warning("Unable to get GOG data for game %s", gogid)
            return []
        dlcs = self.get_game_dlcs(gogid)
        products = [game, *dlcs] if dlcs else [game]
        all_extras = {}
        for product in products:
            # Extras for DLCs you don't own are listed, but are not installable.
            if product.get("is_installable"):
                extras = [
                    {
                        "name": download.get("name", "").strip().capitalize(),
                        "type": download.get("type", "").strip(),
                        "total_size": download.get("total_size", 0),
                        "id": str(download["id"]),
                        "downlinks": [f.get("downlink") for f in download.get("files") or []],
                    }
                    for download in product["downloads"].get("bonus_content") or []
                ]
                if extras:
                    all_extras[product.get("title", "").strip()] = extras
        return all_extras

    def get_installers(self, downloads, runner, language="en"):
        """Return available installers for a GOG game"""
        # Filter out Mac installers
        gog_installers = [installer for installer in downloads.get("installers", []) if installer["os"] != "mac"]
        filter_os = self.runner_to_os_dict.get(runner)
        # If it's a Linux game, also filter out Windows games
        if filter_os:
            gog_installers = [installer for installer in gog_installers if installer["os"] == filter_os]
        return [
            installer
            for installer in gog_installers
            if installer["language"] == self.determine_language_installer(gog_installers, language)
        ]

    def get_update_versions(self, gog_id: str, runner_name: Optional[str]):
        """Return updates available for a game, keyed by patch version"""

        filter_os = self.runner_to_os_dict.get(runner_name) if runner_name else None

        games_detail = self.get_game_details(gog_id)
        patches = games_detail["downloads"]["patches"]
        if not patches:
            logger.info("No patches for %s", games_detail)
            return {}
        patch_versions = defaultdict(list)
        for patch in patches:
            if filter_os:
                patch_os = patch.get("os")
                if patch_os and filter_os != patch_os.casefold():
                    continue
            patch_versions[patch["name"]].append(patch)
        return patch_versions

    def determine_language_installer(self, gog_installers, default_language="en"):
        """Return locale language string if available in gog_installers"""
        language = i18n.get_lang()
        gog_installers = [installer for installer in gog_installers if installer["language"] == language]
        if not gog_installers:
            language = default_language
        return language

    def query_download_links(self, download):
        """Convert files from the GOG API to a format compatible with lutris installers"""
        download_links = []
        for game_file in download.get("files", []):
            downlink = game_file.get("downlink")
            if not downlink:
                logger.error("No download information for %s", game_file)
                continue
            for info in self.get_download_info(downlink):
                download_links.append(
                    {
                        "name": download.get("name", ""),
                        "os": download.get("os", ""),
                        "type": download.get("type", ""),
                        "total_size": download.get("total_size", 0),
                        "id": str(game_file["id"]),
                        "url": info["url"],
                        "filename": info["filename"],
                    }
                )
        return download_links

    def get_extra_files(self, installer, selected_extras):
        extra_files = []
        for extra in selected_extras:
            if extra.get("downlinks"):
                links = [info for link in extra.get("downlinks") for info in self.get_download_info(link)]
            elif str(extra["id"]) in selected_extras:
                links = self.query_download_links(extra)
            else:
                links = []

            if not links:
                logger.error("No download link for bonus content '%s' could be obtained.", extra.get("name"))

            for link in links:
                if link["filename"].endswith(".xml"):
                    # GOG gives a link for checksum XML files for bonus content
                    # but downloading them results in a 404 error.
                    continue
                extra_files.append(
                    InstallerFile(
                        installer.game_slug,
                        str(extra["id"]),
                        {
                            "url": link["url"],
                            "filename": link["filename"],
                        },
                    )
                )
        return extra_files

    def _get_installer_links(self, installer, downloads):
        """Return links to downloadable files from a list of downloads"""
        try:
            gog_installers = self.get_installers(downloads, installer.runner)
            if not gog_installers:
                return []
            if len(gog_installers) > 1:
                logger.warning("More than 1 GOG installer found, picking first.")
            _installer = gog_installers[0]
            return self.query_download_links(_installer)
        except HTTPError as err:
            raise UnavailableGameError(_("Couldn't load the download links for this game")) from err

    def get_patch_files(self, installer, installer_file_id):
        logger.debug("Getting patches for %s", installer.version)
        downloads = self.get_downloads(installer.service_appid)
        links = []
        for patch_file in downloads["patches"]:
            if "GOG " + patch_file["version"] == installer.version:
                links += self.query_download_links(patch_file)
        return self._format_links(installer, installer_file_id, links)

    def _format_links(self, installer, installer_file_id, links):
        _installer_files = defaultdict(dict)  # keyed by filename
        for link in links:
            try:
                filename = link["filename"]
            except KeyError:
                logger.error("Invalid link: %s", link)
                raise
            if filename.lower().endswith(".xml"):
                if filename != installer_file_id:
                    filename = filename[:-4]
                _installer_files[filename]["checksum_url"] = link["url"]
                continue
            _installer_files[filename]["id"] = link["id"]
            _installer_files[filename]["url"] = link["url"]
            _installer_files[filename]["filename"] = filename
            _installer_files[filename]["total_size"] = link["total_size"]
        files = []
        file_id_provided = False  # Only assign installer_file_id once
        for _file_id in _installer_files:
            installer_file = _installer_files[_file_id]
            if "url" not in installer_file:
                raise ValueError("Invalid installer file %s" % installer_file)
            filename = installer_file["filename"]
            if filename.lower().endswith((".exe", ".sh")) and not file_id_provided:
                file_id = installer_file_id
                file_id_provided = True
            else:
                file_id = _file_id
            files.append(
                InstallerFile(
                    installer.game_slug,
                    file_id,
                    {
                        "url": installer_file["url"],
                        "filename": installer_file["filename"],
                        "checksum_url": installer_file.get("checksum_url"),
                        "total_size": installer_file["total_size"],
                        "size": -1,
                    },
                )
            )
        if not file_id_provided:
            raise UnavailableGameError(_("Unable to determine correct file to launch installer"))
        return files

    def get_installer_files(self, installer, installer_file_id, selected_extras):
        try:
            downloads = self.get_downloads(installer.service_appid)
        except HTTPError as err:
            raise UnavailableGameError(_("Couldn't load the downloads for this game")) from err
        links = self._get_installer_links(installer, downloads)
        if links:
            files = [
                InstallerFileCollection(
                    installer.game_slug, installer_file_id, self._format_links(installer, installer_file_id, links)
                )
            ]
        else:
            files = []

        extra_files = []
        if selected_extras:
            for extra_file in self.get_extra_files(installer, selected_extras):
                extra_files.append(extra_file)

        return files, extra_files

    def read_file_checksum(self, file_path):
        """Return the MD5 checksum for a GOG file
        Requires a GOG XML file as input
        This has yet to be used.
        """
        if not file_path.endswith(".xml"):
            raise ValueError("Pass a XML file to return the checksum")
        with open(file_path, encoding="utf-8") as checksum_file:
            checksum_content = checksum_file.read()
        root_elem = etree.fromstring(checksum_content)
        return root_elem.attrib["name"], root_elem.attrib["md5"]

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        details = json.loads(db_game["details"])
        slug = details["slug"]
        platforms = [platform.casefold() for platform, is_supported in details["worksOn"].items() if is_supported]
        if "linux" in platforms:
            return self._generate_installer(slug, "linux", db_game)
        else:
            return self._generate_installer(slug, "wine", db_game)

    def generate_installers(self, db_game: Dict[str, Any]) -> List[dict]:
        details = json.loads(db_game["details"])
        slug = details["slug"]
        platforms = [platform.casefold() for platform, is_supported in details["worksOn"].items() if is_supported]

        installers = []

        if "linux" in platforms:
            installers.append(self._generate_installer(slug, "linux", db_game))

        if "windows" in platforms:
            installers.append(self._generate_installer(slug, "wine", db_game))

        if len(installers) > 1:
            for installer in installers:
                runner_human_name = get_runner_human_name(installer["runner"])
                installer["version"] += " " + (runner_human_name or installer["runner"])

        return installers

    def _generate_installer(self, slug: str, runner: str, db_game: Dict[str, Any]) -> Dict[str, Any]:
        system_config = {}
        if runner == "linux":
            game_config = {"exe": AUTO_ELF_EXE}
            script = [
                {"extract": {"file": "goginstaller", "format": "zip", "dst": "$CACHE"}},
                {"merge": {"src": "$CACHE/data/noarch", "dst": "$GAMEDIR"}},
            ]
        else:
            game_config = {"exe": AUTO_WIN32_EXE}
            script = [
                {"autosetup_gog_game": "goginstaller"},
            ]
        return {
            "name": db_game["name"],
            "version": "GOG",
            "slug": slug,
            "game_slug": self.get_installed_slug(db_game),
            "runner": runner,
            "gogid": db_game["appid"],
            "script": {
                "game": game_config,
                "system": system_config,
                "files": [{"goginstaller": "N/A:Select the installer from GOG"}],
                "installer": script,
            },
        }

    def get_installed_runner_name(self, db_game):
        platforms = [platform.casefold() for platform in self.get_game_platforms(db_game)]
        return "linux" if "linux" in platforms else "wine"

    def get_games_owned(self):
        """Return IDs of games owned by user"""
        url = "{}/user/data/games".format(self.embed_url)
        return self.make_api_request(url)

    def get_dlc_installers(self, db_game):
        """Return all available DLC installers for game"""
        appid = db_game["service_id"]
        runner_name = db_game.get("runner")

        filter_os = self.runner_to_os_dict.get(runner_name) if runner_name else None

        dlcs = self.get_game_dlcs(appid)

        installers = []

        for dlc in dlcs:
            dlc_id = "gogdlc-%s" % dlc["slug"]

            # remove mac installers for now
            installfiles = [
                installer for installer in dlc["downloads"].get("installers", []) if installer["os"] != "mac"
            ]

            for file in installfiles:
                file_os = file["os"].casefold()

                if filter_os and file_os and filter_os != file_os:
                    continue

                # supports linux
                if file_os == "linux":
                    runner = "linux"
                    script = [
                        {"extract": {"dst": "$CACHE/GOG", "file": dlc_id, "format": "zip"}},
                        {"merge": {"dst": "$GAMEDIR", "src": "$CACHE/GOG/data/noarch/"}},
                    ]
                else:
                    runner = "wine"
                    script = [{"task": {"name": "wineexec", "executable": dlc_id}}]

                installer = {
                    "name": db_game["name"],
                    # add runner in brackets - wrong installer can be run when this is not unique
                    "version": f"{dlc['title']} ({runner})",
                    "slug": dlc["slug"],
                    "description": "DLC for %s" % db_game["name"],
                    "game_slug": self.get_installed_slug(db_game),
                    "runner": runner,
                    "is_dlc": True,
                    "dlcid": dlc["id"],
                    "gogid": dlc["id"],
                    "script": {
                        "extends": db_game["installer_slug"],
                        "files": [{dlc_id: "N/A:Select the patch from GOG"}],
                        "installer": script,
                    },
                }
                installers.append(installer)

        return installers

    def get_dlc_installers_owned(self, db_game):
        """Return DLC installers for owned DLC"""

        owned = self.get_games_owned()
        installers = self.get_dlc_installers(db_game)

        installers = [installer for installer in installers if installer["dlcid"] in owned["owned"]]

        return installers

    def get_dlc_installers_runner(self, db_game, runner, only_owned=True):
        """Return DLC installers for requested runner
        only_owned=True only return installers for owned DLC (default)"""
        if only_owned:
            installers = self.get_dlc_installers_owned(db_game)
        else:
            installers = self.get_dlc_installers(db_game)

        # only handle linux & wine for now
        if runner != "linux":
            runner = "wine"

        installers = [installer for installer in installers if installer["runner"] == runner]

        return installers

    def get_update_installers(self, db_game):
        appid = db_game["service_id"]
        runner = db_game.get("runner")
        patch_versions = self.get_update_versions(appid, runner)
        patch_installers = []
        for version in patch_versions:
            patch = patch_versions[version]
            size = human_size(sum(part["total_size"] for part in patch))
            patch_id = "gogpatch-%s" % slugify(patch[0]["version"])
            installer = {
                "name": db_game["name"],
                "description": patch[0]["name"] + " " + size,
                "slug": db_game["installer_slug"],
                "game_slug": db_game["slug"],
                "version": "GOG " + patch[0]["version"],
                "runner": "wine",
                "script": {
                    "extends": db_game["installer_slug"],
                    "files": [{patch_id: "N/A:Select the patch from GOG"}],
                    "installer": [{"task": {"name": "wineexec", "executable": patch_id}}],
                },
            }
            patch_installers.append(installer)
        return patch_installers

    def get_game_platforms(self, db_game: dict) -> List[str]:
        details = db_game.get("details")
        if details:
            worksOn = json.loads(details).get("worksOn")
            if worksOn is not None:
                return [name for name, works in worksOn.items() if works]
        return []
