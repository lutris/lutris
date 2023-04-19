import json
import os
import urllib.parse
from gettext import gettext as _

from gi.repository import Gio

from lutris import settings
from lutris.api import get_api_games, get_game_installers, read_api_key
from lutris.database.games import get_games
from lutris.database.services import ServiceGameCollection
from lutris.gui import dialogs
from lutris.gui.views.media_loader import download_media
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisCoverartMedium, LutrisIcon, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.util import http
from lutris.util.log import logger


class LutrisGame(ServiceGame):
    """Service game created from the Lutris API"""
    service = "lutris"

    @classmethod
    def new_from_api(cls, api_payload):
        """Create an instance of LutrisGame from the API response"""
        service_game = LutrisGame()
        service_game.appid = api_payload['slug']
        service_game.slug = api_payload['slug']
        service_game.name = api_payload['name']
        service_game.details = json.dumps(api_payload)
        return service_game


class LutrisService(OnlineService):
    """Service for Lutris games"""

    id = "lutris"
    name = _("Lutris")
    icon = "lutris"
    online = True
    medias = {
        "icon": LutrisIcon,
        "banner": LutrisBanner,
        "coverart_med": LutrisCoverartMedium,
        "coverart_big": LutrisCoverart,
    }
    default_format = "banner"

    api_url = settings.SITE_URL + "/api"
    login_url = settings.SITE_URL + "/api/accounts/token"
    cache_path = os.path.join(settings.CACHE_DIR, "lutris")
    token_path = os.path.join(settings.CACHE_DIR, "auth-token")

    @property
    def credential_files(self):
        """Return a list of all files used for authentication"""
        return [self.token_path]

    def match_games(self):
        """Matching lutris games is much simpler... No API call needed."""
        service_games = {
            str(game["appid"]): game for game in ServiceGameCollection.get_for_service(self.id)
        }
        for lutris_game in get_games():
            self.match_game(service_games.get(lutris_game["slug"]), lutris_game)

    def is_connected(self):
        """Is the service connected?"""
        return self.is_authenticated()

    def login(self, parent=None):
        """Connect to Lutris"""
        login_dialog = dialogs.ClientLoginDialog(parent=parent)
        login_dialog.connect("connected", self.on_connect_success)

    def on_connect_success(self, _widget, _username):
        """Handles connection success"""
        self.emit("service-login")

    def get_library(self):
        """Return the remote library as a list of dicts."""
        credentials = read_api_key()
        if not credentials:
            return []
        url = settings.SITE_URL + "/api/games/library/%s" % urllib.parse.quote(credentials["username"])
        request = http.Request(url, headers={"Authorization": "Token " + credentials["token"]})
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Unable to load library: %s", ex)
            return []
        response_data = response.json
        if response_data:
            return response_data["games"]
        return []

    def load(self):
        lutris_games = self.get_library()
        logger.debug("Loaded %s games from Lutris library", len(lutris_games))
        for game in lutris_games:
            lutris_game = LutrisGame.new_from_api(game)
            lutris_game.save()
        logger.debug("Matching with already installed games")
        self.match_games()
        logger.debug("Lutris games loaded")
        return lutris_games

    def install(self, db_game):
        if isinstance(db_game, dict):
            slug = db_game["slug"]
        else:
            slug = db_game
        installers = get_game_installers(slug)
        if not installers:
            raise RuntimeError(_("Lutris has no installers for %s. Try using a different service instead.") % slug)
        application = Gio.Application.get_default()
        application.show_installer_window(installers)

    def get_game_platforms(self, db_game):
        details = db_game.get("details")
        if details:
            platforms = json.loads(details).get("platforms")
            if platforms is not None:
                return [p.get("name") for p in platforms]
        return None


def download_lutris_media(slug):
    """Download all media types for a single lutris game"""
    url = settings.SITE_URL + "/api/games/%s" % slug
    request = http.Request(url)
    try:
        response = request.get()
    except http.HTTPError as ex:
        logger.debug("Unable to load %s: %s", slug, ex)
        return
    response_data = response.json
    icon_url = response_data.get("icon_url")
    if icon_url:
        download_media({slug: icon_url}, LutrisIcon())

    banner_url = response_data.get("banner_url")
    if banner_url:
        download_media({slug: banner_url}, LutrisBanner())

    cover_url = response_data.get("coverart")
    if cover_url:
        download_media({slug: cover_url}, LutrisCoverart())


def sync_media():
    """Downlad all missing media"""
    banners_available = {fn.split(".")[0] for fn in os.listdir(settings.BANNER_PATH)}
    icons_available = {
        fn.split(".")[0].replace("lutris_", "")
        for fn in os.listdir(settings.ICON_PATH)
        if fn.startswith("lutris_")
    }
    covers_available = {fn.split(".")[0] for fn in os.listdir(settings.COVERART_PATH)}
    complete_games = banners_available.intersection(icons_available).intersection(covers_available)
    all_slugs = {game["slug"] for game in get_games()}
    slugs = all_slugs - complete_games
    if not slugs:
        return
    games = get_api_games(list(slugs))

    alias_map = {}
    api_slugs = set()
    for game in games:
        api_slugs.add(game["slug"])
        for alias in game["aliases"]:
            if alias["slug"] in slugs:
                alias_map[game["slug"]] = alias["slug"]
    alias_slugs = set(alias_map.values())
    used_alias_slugs = alias_slugs - api_slugs
    for alias_slug in used_alias_slugs:
        for game in games:
            if alias_slug in [alias["slug"] for alias in game["aliases"]]:
                game["slug"] = alias_map[game["slug"]]
                continue
    banner_urls = {
        game["slug"]: game["banner_url"]
        for game in games
        if game["slug"] not in banners_available and game["banner_url"]
    }
    icon_urls = {
        game["slug"]: game["icon_url"]
        for game in games
        if game["slug"] not in icons_available and game["icon_url"]
    }
    cover_urls = {
        game["slug"]: game["coverart"]
        for game in games
        if game["slug"] not in covers_available and game["coverart"]
    }
    logger.debug(
        "Syncing %s banners, %s icons and %s covers",
        len(banner_urls), len(icon_urls), len(cover_urls)
    )
    download_media(banner_urls, LutrisBanner())
    download_media(icon_urls, LutrisIcon())
    download_media(cover_urls, LutrisCoverart())
