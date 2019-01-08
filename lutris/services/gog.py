"""Module for handling the GOG service"""
import os
import time
import json
from urllib.parse import urlencode, urlparse, parse_qsl
from lutris import settings
from lutris import pga
from lutris import api
from lutris.services import AuthenticationError
from lutris.util.http import Request
from lutris.util import system
from lutris.util.log import logger
from lutris.util.cookies import WebkitCookieJar
from lutris.util.resources import download_media
from lutris.gui.dialogs import WebConnectDialog
from lutris.services.service_game import ServiceGame


NAME = "GOG"
ICON = "gog"
ONLINE = True


class GogService:
    """Service class for GOG"""

    name = "GOG"
    embed_url = "https://embed.gog.com"
    api_url = "https://api.gog.com"

    client_id = "46899977096215655"
    client_secret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    redirect_uri = "https://embed.gog.com/on_login_success?origin=client"

    login_success_url = "https://www.gog.com/on_login_success"
    credentials_path = os.path.join(settings.CACHE_DIR, ".gog.auth")
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
        return [self.credentials_path, self.token_path]

    def disconnect(self):
        """Disconnect from GOG by removing all credentials"""
        for auth_file in self.credential_files + [self.cache_path]:
            try:
                os.remove(auth_file)
            except OSError:
                logger.warning("Unable to remove %s", auth_file)

    def is_authenticated(self):
        return all([os.path.exists(path) for path in self.credential_files])

    def is_available(self):
        """Return whether the user is authenticated and if the service is available"""
        if not self.is_authenticated():
            return False
        user_data = self.get_user_data()
        return user_data and "username" in user_data

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
        request.get()
        token = request.json
        with open(self.token_path, "w") as token_file:
            token_file.write(json.dumps(token))

    def load_cookies(self):
        """Load cookies from disk"""
        logger.debug("Loading cookies from %s", self.credentials_path)
        if not os.path.exists(self.credentials_path):
            logger.debug("No cookies found, please authenticate first")
            return
        cookiejar = WebkitCookieJar(self.credentials_path)
        cookiejar.load()
        return cookiejar

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
        cookies = self.load_cookies()
        request = Request(url, cookies=cookies)
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
        headers = {"Authorization": "Bearer " + token["access_token"]}
        request = Request(url, headers=headers)
        request.get()
        return request.json

    def get_user_data(self):
        """Return GOG profile information"""
        url = "https://embed.gog.com/userData.json"
        return self.make_api_request(url)

    def get_library(self, force_reload=False):
        """Return the user's library of GOG games"""

        if system.path_exists(self.cache_path) and not force_reload:
            logger.debug("Returning cached GOG library")
            with open(self.cache_path, 'r') as gog_cache:
                return json.load(gog_cache)

        total_pages = 1
        games = []
        page = 1
        while page <= total_pages:
            products_response = self.get_products_page(page=page)
            page += 1
            total_pages = products_response["totalPages"]
            games += products_response["products"]
        with open(self.cache_path, 'w') as gog_cache:
            json.dump(games, gog_cache)
        return games

    def get_products_page(self, page=1, search=None):
        if not self.is_authenticated():
            raise RuntimeError("User is not logged in")
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
        response = self.make_api_request(downlink)
        for field in ("checksum", "downlink"):
            field_url = response[field]
            parsed = urlparse(field_url)
            response[field + "_filename"] = os.path.basename(parsed.path)
        return response


class GOGGame(ServiceGame):
    store = "gog"

    @classmethod
    def new_from_gog_game(cls, gog_game):
        """Return a GOG game instance from the API info"""
        service_game = GOGGame()
        service_game.appid = str(gog_game['id'])
        service_game.icon = cls.get_banner(gog_game)
        service_game.name = gog_game['title']
        service_game.details = json.dumps(gog_game)
        return service_game

    @classmethod
    def get_banner(cls, gog_game):
        """Return the path to the game banner.
        Downloads the banner if not present.
        """
        image_url = "https:%s_prof_game_100x60.jpg" % gog_game['image']
        image_hash = gog_game['image'].split("/")[-1]
        cache_dir = os.path.join(settings.CACHE_DIR, "gog/banners/small/")
        if not system.path_exists(cache_dir):
            os.makedirs(cache_dir)
        cache_path = os.path.join(cache_dir, "%s.jpg" % image_hash)
        if not system.path_exists(cache_path):
            download_media(image_url, cache_path)
        return cache_path


GOG_SERVICE = GogService()


def is_connected():
    """Return True if user is connected to GOG"""
    return GOG_SERVICE.is_available()


def connect(parent=None):
    """Connect to GOG"""
    dialog = WebConnectDialog(GOG_SERVICE, parent)
    dialog.run()


def disconnect():
    """Disconnect from GOG"""
    GOG_SERVICE.disconnect()


class GOGSyncer:
    """Sync GOG games to Lutris"""

    @classmethod
    def load(cls, force_reload=False):
        """Load the user game library from the GOG API"""
        return [
            GOGGame.new_from_gog_game(game)
            for game in GOG_SERVICE.get_library(force_reload=force_reload)
        ]

    @classmethod
    def sync(cls, games, full=False):
        """Import GOG games to the Lutris library"""
        gog_ids = [game.appid for game in games]
        if not gog_ids:
            return ([], [])
        lutris_games = api.get_api_games(gog_ids, query_type="gogid")
        added_games = []
        for game in lutris_games:
            game_data = {
                "name": game["name"],
                "slug": game["slug"],
                "year": game["year"],
                "updated": game["updated"],
                "gogid": game.get("gogid"),  # GOG IDs will be added at a later stage in the API
            }
            added_games.append(pga.add_or_update(**game_data))
        if not full:
            return added_games
        return added_games, []


SYNCER = GOGSyncer
