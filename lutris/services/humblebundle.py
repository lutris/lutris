"""Manage Humble Bundle libraries"""
import os
import json
from urllib.parse import urlparse
from lutris import api
from lutris import pga
from lutris import settings
from lutris.gui.dialogs import WebConnectDialog
from lutris.util.http import Request, HTTPError
from lutris.util.log import logger
from lutris.util import system
from lutris.util.resources import download_media
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame

NAME = "Humble Bundle"
ICON = "humblebundle"
ONLINE = True


class HumbleBundleGame(ServiceGame):
    """Service game for DRM free Humble Bundle games"""
    store = "humblebundle"

    @classmethod
    def new_from_humble_game(cls, humble_game):
        """Converts a game from the API to a service game usable by Lutris"""
        service_game = HumbleBundleGame()
        service_game.appid = humble_game["machine_name"]
        service_game.name = humble_game["human_name"]
        service_game.icon = cls.get_icon(humble_game)
        service_game.details = json.dumps(humble_game)
        return service_game

    @classmethod
    def get_icon(cls, gog_game):
        """Download the icon for the game and return the local path"""
        icon_url = gog_game["icon"]
        cache_dir = os.path.join(settings.CACHE_DIR, "humblebundle/icons/")
        if not system.path_exists(cache_dir):
            os.makedirs(cache_dir)
        icon_filename = os.path.basename(urlparse(icon_url).path)
        if not icon_filename:
            return ""
        cache_path = os.path.join(cache_dir, icon_filename)
        if not system.path_exists(cache_path):
            download_media(icon_url, cache_path)
        return cache_path


class HumbleBundleService(OnlineService):
    """Service for Humble Bundle"""

    name = NAME
    api_url = "https://www.humblebundle.com/"
    login_url = "https://www.humblebundle.com/login?goto=/home/library"
    redirect_uri = "https://www.humblebundle.com/home/library"

    cookies_path = os.path.join(settings.CACHE_DIR, ".humblebundle.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".humblebundle.token")
    cache_path = os.path.join(settings.CACHE_DIR, "humblebundle-library/")

    supported_platforms = ("linux", "windows")

    def request_token(self, url="", refresh_token=""):
        """Dummy function, should not be here. Fix in WebConnectDialog"""

    def make_api_request(self, url):
        """Make an authenticated request to the Humble API"""
        request = Request(url, cookies=self.load_cookies())
        try:
            request.get()
        except HTTPError:
            logger.error(
                "Failed to request %s, check your GOG credentials and internet connectivity",
                url,
            )
            return
        return request.json

    def order_path(self, gamekey):
        """Return the local path for an order"""
        return os.path.join(self.cache_path, "%s.json" % gamekey)

    def get_order(self, gamekey):
        """Retrieve an order identitied by its key"""
        logger.debug("Getting Humble Bundle order %s", gamekey)
        cache_filename = self.order_path(gamekey)
        if os.path.exists(cache_filename):
            with open(cache_filename) as cache_file:
                return json.load(cache_file)
        response = self.make_api_request(
            self.api_url + "api/v1/order/%s?all_tpkds=true" % gamekey
        )
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
        with open(cache_filename, "w") as cache_file:
            json.dump(response, cache_file)
        return response

    def get_library(self):
        """Return the games from the user's library"""
        games = []
        for order in self.get_orders():
            for product in order["subproducts"]:
                for download in product["downloads"]:
                    if download["platform"] in self.supported_platforms:
                        games.append(product)
        return games

    def get_orders(self):
        """Return all orders"""
        gamekeys = self.make_api_request(self.api_url + "api/v1/user/order")
        return [
            self.get_order(gamekey["gamekey"])
            for gamekey in gamekeys
        ]

    @staticmethod
    def find_download_in_order(order, humbleid, platform):
        """Return the download information in an order for a give game"""
        for product in order["subproducts"]:
            if product["machine_name"] != humbleid:
                continue
            for download in product["downloads"]:
                if download["platform"] != platform:
                    continue
                return {
                    "product": order["product"],
                    "gamekey": order["gamekey"],
                    "created": order["created"],
                    "download": download
                }

    def get_downloads(self, humbleid, platform):
        """Return the download information for a given game"""
        download_links = []
        for order in self.get_orders():
            download = self.find_download_in_order(order, humbleid, platform)
            if download:
                download_links.append(download)
        return download_links


SERVICE = HumbleBundleService()


def is_connected():
    """Is the service connected?"""
    return SERVICE.is_authenticated()


def connect(parent=None):
    """Connect to Humble Bundle"""
    dialog = WebConnectDialog(SERVICE, parent)
    dialog.run()


def disconnect():
    """Disconnect from Humble Bundle"""
    return SERVICE.disconnect()


def get_humble_download_link(humbleid, runner):
    """Return a download link for a given humbleid and runner"""
    platform = runner if runner != "wine" else "windows"
    downloads = SERVICE.get_downloads(humbleid, platform)
    if not downloads:
        logger.error("Game %s for %s not found in the Humble Bundle library", humbleid, platform)
        return
    logger.info("Found %s download for %s", len(downloads), humbleid)
    download = downloads[0]
    logger.info("Reloading order %s", download["product"]["human_name"])
    os.remove(SERVICE.order_path(download["gamekey"]))
    order = SERVICE.get_order(download["gamekey"])
    download_info = SERVICE.find_download_in_order(order, humbleid, platform)
    if download_info:
        if len(download_info["download"]["download_struct"]) > 1:
            logger.warning("Multiple downloads for %s. This is unhandled", humbleid)
        return download_info["download"]["download_struct"][0]["url"]["web"]
    logger.warning("Couldn't retrieve any downloads for %s", humbleid)


class HumbleBundleSyncer:
    """Sync DRM-Free Humble Bundle games to the local library"""

    @classmethod
    def load(cls):
        """Load the user's Humble Bundle library"""
        humble_games = []
        seen = set()
        for game in SERVICE.get_library():
            if game["human_name"] in seen:
                continue
            humble_games.append(HumbleBundleGame.new_from_humble_game(game))
            seen.add(game["human_name"])
        return humble_games

    @classmethod
    def sync(cls, games, full=True):
        """Import Humble Bundle games to the library"""
        humbleids = [game.appid for game in games]
        if not humbleids:
            return ([], [])
        lutris_games = api.get_api_games(humbleids, query_type="humblestoreid")
        added_games = []
        for game in lutris_games:
            game_data = {
                "name": game["name"],
                "slug": game["slug"],
                "year": game["year"],
                "updated": game["updated"],
                "humblestoreid": game["humblestoreid"],
            }
            added_games.append(pga.add_or_update(**game_data))
        if not full:
            return added_games, games
        return added_games, []


SYNCER = HumbleBundleSyncer
