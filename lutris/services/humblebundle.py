"""Manage Humble Bundle libraries"""
import json
import os
from gettext import gettext as _

from lutris import settings
from lutris.exceptions import UnavailableGame
from lutris.gui.dialogs import WebConnectDialog
from lutris.installer import AUTO_ELF_EXE, AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.http import HTTPError, Request
from lutris.util.log import logger
from lutris.util.strings import slugify


class HumbleBundleIcon(ServiceMedia):
    """HumbleBundle icon"""
    service = "humblebundle"
    size = (70, 70)
    dest_path = os.path.join(settings.CACHE_DIR, "humblebundle/icons")
    file_pattern = "%s.png"
    api_field = "icon"


class HumbleSmallIcon(HumbleBundleIcon):
    size = (35, 35)


class HumbleBundleGame(ServiceGame):
    """Service game for DRM free Humble Bundle games"""
    service = "humblebundle"

    @classmethod
    def new_from_humble_game(cls, humble_game):
        """Converts a game from the API to a service game usable by Lutris"""
        service_game = HumbleBundleGame()
        service_game.appid = humble_game["machine_name"]
        service_game.slug = humble_game["machine_name"]
        service_game.name = humble_game["human_name"]
        service_game.details = json.dumps(humble_game)
        return service_game


class HumbleBundleService(OnlineService):

    """Service for Humble Bundle"""

    id = "humblebundle"
    _matcher = "humble"
    name = _("Humble Bundle")
    icon = "humblebundle"
    online = True
    medias = {
        "small_icon": HumbleSmallIcon,
        "icon": HumbleBundleIcon
    }
    default_format = "icon"

    api_url = "https://www.humblebundle.com/"
    login_url = "https://www.humblebundle.com/login?goto=/home/library"
    redirect_uri = "https://www.humblebundle.com/home/library"

    cookies_path = os.path.join(settings.CACHE_DIR, ".humblebundle.auth")
    token_path = os.path.join(settings.CACHE_DIR, ".humblebundle.token")
    cache_path = os.path.join(settings.CACHE_DIR, "humblebundle-library/")

    supported_platforms = ("linux", "windows")
    is_loading = False

    def request_token(self, url="", refresh_token=""):
        """Dummy function, should not be here. Fix in WebConnectDialog"""
        self.emit("service-login")

    def login(self, parent=None):
        """Connect to Humble Bundle"""
        dialog = WebConnectDialog(self, parent)
        dialog.set_modal(True)
        dialog.show()

    def is_connected(self):
        """Is the service connected?"""
        return self.is_authenticated()

    def load(self):
        """Load the user's Humble Bundle library"""
        if self.is_loading:
            logger.warning("Humble bundle games are already loading")
            return
        self.is_loading = True
        self.emit("service-games-load")
        humble_games = []
        seen = set()
        for game in self.get_library():
            if game["human_name"] in seen:
                continue
            humble_games.append(HumbleBundleGame.new_from_humble_game(game))
            seen.add(game["human_name"])
        for game in humble_games:
            game.save()
        self.is_loading = False
        self.emit("service-games-loaded")

    def make_api_request(self, url):
        """Make an authenticated request to the Humble API"""
        request = Request(url, cookies=self.load_cookies())
        try:
            request.get()
        except HTTPError:
            logger.error(
                "Failed to request %s, check your Humble Bundle credentials and internet connectivity",
                url,
            )
            return
        return request.json

    def order_path(self, gamekey):
        """Return the local path for an order"""
        return os.path.join(self.cache_path, "%s.json" % gamekey)

    def get_order(self, gamekey):
        """Retrieve an order identitied by its key"""
        # logger.debug("Getting Humble Bundle order %s", gamekey)
        cache_filename = self.order_path(gamekey)
        if os.path.exists(cache_filename):
            with open(cache_filename) as cache_file:
                return json.load(cache_file)
        response = self.make_api_request(self.api_url + "api/v1/order/%s?all_tpkds=true" % gamekey)
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)
        with open(cache_filename, "w") as cache_file:
            json.dump(response, cache_file)
        return response

    def get_library(self):
        """Return the games from the user's library"""
        games = []
        for order in self.get_orders():
            if not order:
                continue
            for product in order["subproducts"]:
                for download in product["downloads"]:
                    if download["platform"] in self.supported_platforms:
                        games.append(product)
        return games

    def get_gamekeys_from_local_orders(self):
        """Retrieve a list of orders from the cache."""
        game_keys = []
        if os.path.exists(self.cache_path):
            for order_file in os.listdir(self.cache_path):
                if not order_file.endswith(".json"):
                    continue
                game_keys.append({"gamekey": order_file[:-5]})
        return game_keys

    def get_orders(self):
        """Return all orders"""
        gamekeys = self.get_gamekeys_from_local_orders()
        if not gamekeys:
            gamekeys = self.make_api_request(self.api_url + "api/v1/user/order")
        return [self.get_order(gamekey["gamekey"]) for gamekey in gamekeys]

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

    def get_installer_files(self, installer, installer_file_id):
        """Replace the user provided file with download links from Humble Bundle"""
        try:
            link = get_humble_download_link(installer.service_appid, installer.runner)
        except Exception as ex:
            logger.exception("Failed to get Humble Bundle game: %s", ex)
            raise UnavailableGame
        if not link:
            raise UnavailableGame("No game found on Humble Bundle")
        filename = link.split("?")[0].split("/")[-1]
        return [
            InstallerFile(installer.game_slug, installer_file_id, {
                "url": link,
                "filename": filename
            })
        ]

    @staticmethod
    def get_filename_for_platform(downloads, platform):
        download = [d for d in downloads if d["platform"] == platform][0]
        url = pick_download_url_from_download_info(download)
        if not url:
            return
        return url.split("?")[0].split("/")[-1]

    @staticmethod
    def platform_has_downloads(downloads, platform):
        for download in downloads:
            if download["platform"] != platform:
                continue
            if len(download["download_struct"]) > 0:
                return True

    def generate_installer(self, db_game):
        details = json.loads(db_game["details"])
        platforms = [download["platform"] for download in details["downloads"]]
        system_config = {}
        if "linux" in platforms and self.platform_has_downloads(details["downloads"], "linux"):
            runner = "linux"
            game_config = {"exe": AUTO_ELF_EXE}
            filename = self.get_filename_for_platform(details["downloads"], "linux")
            if filename.lower().endswith(".sh"):
                script = [
                    {"extract": {"file": "humblegame", "format": "zip", "dst": "$CACHE"}},
                    {"merge": {"src": "$CACHE/data/noarch", "dst": "$GAMEDIR", "optional": True}},
                    {"move": {"src": "$CACHE/data/noarch", "dst": "$CACHE/noarch", "optional": True}},
                    {"merge": {"src": "$CACHE/data/x86_64", "dst": "$GAMEDIR", "optional": True}},
                    {"move": {"src": "$CACHE/data/x86_64", "dst": "$CACHE/x86_64", "optional": True}},
                    {"merge": {"src": "$CACHE/data/x86", "dst": "$GAMEDIR", "optional": True}},
                    {"move": {"src": "$CACHE/data/x86", "dst": "$CACHE/x86", "optional": True}},
                    {"merge": {"src": "$CACHE/data/", "dst": "$GAMEDIR", "optional": True}},
                ]
            elif filename.endswith("-bin") or filename.endswith("mojo.run"):
                script = [
                    {"extract": {"file": "humblegame", "format": "zip", "dst": "$CACHE"}},
                    {"merge": {"src": "$CACHE/data/", "dst": "$GAMEDIR"}},
                ]
            else:
                script = [{"extract": {"file": "humblegame"}}]
                system_config = {"gamemode": 'false'}  # Unity games crash with gamemode
        elif "windows" in platforms:
            runner = "wine"
            game_config = {"exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR"}
            filename = self.get_filename_for_platform(details["downloads"], "windows")
            if filename.lower().endswith(".zip"):
                script = [
                    {"task": {"name": "create_prefix", "prefix": "$GAMEDIR"}},
                    {"extract": {"file": "humblegame", "dst": "$GAMEDIR/drive_c/%s" % db_game["slug"]}}
                ]
            else:
                script = [
                    {"task": {"name": "wineexec", "executable": "humblegame"}}
                ]
        else:
            logger.warning("Unsupported platforms: %s", platforms)
            return {}
        return {
            "name": db_game["name"],
            "version": "Humble Bundle",
            "slug": details["machine_name"],
            "game_slug": slugify(db_game["name"]),
            "runner": runner,
            "humbleid": db_game["appid"],
            "script": {
                "game": game_config,
                "system": system_config,
                "files": [
                    {"humblegame": "N/A:Select the installer from Humble Bundle"}
                ],
                "installer": script
            }
        }


def pick_download_url_from_download_info(download_info):
    """From a list of downloads in Humble Bundle, pick the most appropriate one
    for the installer.
    This needs a way to be explicitely filtered.
    """
    if not download_info["download_struct"]:
        logger.warning("No downloads found")
        return
    if len(download_info["download_struct"]) > 1:
        logger.info("There are %s downloads available:", len(download_info["download_struct"]))
        sorted_downloads = []
        for _download in download_info["download_struct"]:
            if "deb" in _download["name"] or "rpm" in _download["name"] or "32" in _download["name"]:
                sorted_downloads.append(_download)
            else:
                sorted_downloads.insert(0, _download)
        return sorted_downloads[0]["url"]["web"]
    return download_info["download_struct"][0]["url"]["web"]


def get_humble_download_link(humbleid, runner):
    """Return a download link for a given humbleid and runner"""
    service = HumbleBundleService()
    platform = runner if runner != "wine" else "windows"
    downloads = service.get_downloads(humbleid, platform)
    if not downloads:
        logger.error("Game %s for %s not found in the Humble Bundle library", humbleid, platform)
        return
    logger.info("Found %s download for %s", len(downloads), humbleid)
    download = downloads[0]
    logger.info("Reloading order %s", download["product"]["human_name"])
    os.remove(service.order_path(download["gamekey"]))
    order = service.get_order(download["gamekey"])
    download_info = service.find_download_in_order(order, humbleid, platform)
    if download_info:
        return pick_download_url_from_download_info(download_info["download"])
    logger.warning("Couldn't retrieve any downloads for %s", humbleid)
