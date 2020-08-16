"""Module for handling the GOG service"""
import json
import os
import time
from gettext import gettext as _
from urllib.parse import parse_qsl, urlencode, urlparse

from lutris import settings
from lutris.exceptions import AuthenticationError, MultipleInstallerError, UnavailableGame
from lutris.gui.dialogs import WebConnectDialog
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.util import system
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.resources import download_media


class GOGService(OnlineService):

    """Service class for GOG"""

    id = "gog"
    name = _("GOG")
    icon = "gog"
    lutris_db_field = "gogid"

    embed_url = "https://embed.gog.com"
    api_url = "https://api.gog.com"

    client_id = "46899977096215655"
    client_secret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    redirect_uri = "https://embed.gog.com/on_login_success?origin=client"

    login_success_url = "https://www.gog.com/on_login_success"
    cookies_path = os.path.join(settings.CACHE_DIR, ".gog.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".gog.token")
    cache_path = os.path.join(settings.CACHE_DIR, "gog-library.json")

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

    def login(self, parent=None):
        """Connect to GOG"""
        logger.debug("Connecting to GOG")
        dialog = WebConnectDialog(self, parent)
        dialog.set_modal(True)
        dialog.show()

    def is_connected(self):
        """Return whether the user is authenticated and if the service is available"""
        if not self.is_authenticated():
            return False
        user_data = self.get_user_data()
        return user_data and "username" in user_data

    def load(self):
        """Load the user game library from the GOG API"""
        games = [GOGGame.new_from_gog_game(game) for game in self.get_library()]
        lutris_games = self.get_lutris_games(games)
        for game in games:
            game.lutris_slug = lutris_games[game.appid]["slug"] if lutris_games.get(game.appid) else None
            game.save()
        self.emit("service-games-loaded", self.id)

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
        except HTTPError:
            logger.error("Failed to get token, check your GOG credentials.")
            logger.warning("Clearing existing credentials")
            self.logout()
            return

        token = request.json
        with open(self.token_path, "w") as token_file:
            token_file.write(json.dumps(token))
        self.emit("service-login", self.id)

    def load_token(self):
        """Load token from disk"""
        if not os.path.exists(self.token_path):
            raise AuthenticationError("No GOG token available")
        with open(self.token_path) as token_file:
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
            logger.error(
                "Failed to request %s, check your GOG credentials and internet connectivity",
                url,
            )
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
            with open(self.cache_path, "r") as gog_cache:
                return json.load(gog_cache)

        total_pages = 1
        games = []
        page = 1
        while page <= total_pages:
            products_response = self.get_products_page(page=page)
            page += 1
            total_pages = products_response["totalPages"]
            games += products_response["products"]
        with open(self.cache_path, "w") as gog_cache:
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

    def get_game_details(self, product_id):
        """Return game information for a given game"""
        logger.info("Getting game details for %s", product_id)
        url = "{}/products/{}?expand=downloads".format(self.api_url, product_id)
        return self.make_api_request(url)

    def get_download_info(self, downlink):
        """Return file download information"""
        logger.info("Getting download info for %s", downlink)
        try:
            response = self.make_api_request(downlink)
        except HTTPError:
            raise UnavailableGame()
        if not response:
            raise UnavailableGame()
        for field in ("checksum", "downlink"):
            field_url = response[field]
            parsed = urlparse(field_url)
            query = dict(parse_qsl(parsed.query))
            response[field + "_filename"] = os.path.basename(query.get("path") or parsed.path)
        return response

    def get_installers(self, gogid, runner, language="en"):
        """Return available installers for a GOG game"""

        gog_data = self.get_game_details(gogid)
        if not gog_data:
            logger.warning("Unable to get GOG data for game %s", gogid)
            return []

        # Filter out Mac installers
        gog_installers = [installer for installer in gog_data["downloads"]["installers"] if installer["os"] != "mac"]
        available_platforms = {installer["os"] for installer in gog_installers}
        # If it's a Linux game, also filter out Windows games
        if "linux" in available_platforms:
            if runner == "linux":
                filter_os = "windows"
            else:
                filter_os = "linux"
            gog_installers = [installer for installer in gog_installers if installer["os"] != filter_os]

        # Keep only the english installer until we have locale detection
        # and / or language selection implemented
        gog_installers = [installer for installer in gog_installers if installer["language"] == language]
        return gog_installers


class GOGGame(ServiceGame):

    """Representation of a GOG game"""
    service = "gog"

    @classmethod
    def new_from_gog_game(cls, gog_game):
        """Return a GOG game instance from the API info"""
        service_game = GOGGame()
        service_game.appid = str(gog_game["id"])
        service_game.icon = cls.get_banner(gog_game)
        service_game.slug = gog_game["slug"]
        service_game.name = gog_game["title"]
        service_game.details = json.dumps(gog_game)
        return service_game

    @classmethod
    def get_banner(cls, gog_game):
        """Return the path to the game banner.
        Downloads the banner if not present.
        """
        # Are there other formats?
        image_url = "https:%s_prof_game_100x60.jpg" % gog_game["image"]
        image_hash = gog_game["image"].split("/")[-1]
        cache_dir = os.path.join(settings.CACHE_DIR, "gog/banners/small/")
        if not system.path_exists(cache_dir):
            os.makedirs(cache_dir)
        cache_path = os.path.join(cache_dir, "%s.jpg" % image_hash)
        if not system.path_exists(cache_path):
            download_media(image_url, cache_path)
        return cache_path


def get_gog_download_links(gogid, runner):
    """Return a list of downloadable links for a GOG game"""
    gog_service = GOGService()
    if not gog_service.is_connected():
        logger.info("You are not connected to GOG")
        gog_service.login()
    if not gog_service.is_connected():
        raise UnavailableGame
    gog_installers = gog_service.get_installers(gogid, runner)
    if len(gog_installers) > 1:
        raise MultipleInstallerError()
    try:
        installer = gog_installers[0]
    except IndexError:
        raise UnavailableGame
    download_links = []
    for game_file in installer.get('files', []):
        downlink = game_file.get("downlink")
        if not downlink:
            logger.error("No download information for %s", installer)
            continue
        download_info = gog_service.get_download_info(downlink)
        for field in ('checksum', 'downlink'):
            url = download_info[field]
            logger.info("Adding %s to download links", url)
            download_links.append({"url": download_info[field], "filename": download_info[field + "_filename"]})
    return download_links
