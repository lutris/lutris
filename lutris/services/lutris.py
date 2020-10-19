import json
import os
import urllib.parse
from gettext import gettext as _

from gi.repository import Gio

from lutris import settings
from lutris.api import read_api_key
from lutris.database.games import get_games
from lutris.database.services import ServiceGameCollection
from lutris.gui import dialogs
from lutris.gui.views.media_loader import MediaLoader
from lutris.installer import fetch_script
from lutris.services.base import OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util import http
from lutris.util.log import logger


class LutrisBanner(ServiceMedia):
    service = 'lutris'
    size = (184, 69)
    small_size = (120, 45)
    dest_path = settings.BANNER_PATH
    file_pattern = "%s.jpg"
    api_field = 'banner_url'


class LutrisIcon(ServiceMedia):
    service = 'lutris'
    size = (32, 32)
    small_size = (20, 20)
    dest_path = settings.ICON_PATH
    file_pattern = "lutris_%s.png"
    api_field = 'icon_url'


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
    }
    default_format = "banner"

    api_url = settings.SITE_URL + "/api"
    login_url = settings.SITE_URL + "/api/accounts/token"
    cache_path = os.path.join(settings.CACHE_DIR, "lutris")
    token_path = os.path.join(settings.CACHE_DIR, "auth-token")

    is_loading = False

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
        if self.is_loading:
            logger.warning("Lutris games are already loading")
            return
        self.emit("service-games-load")
        self.is_loading = True
        for game in self.get_library():
            lutris_game = LutrisGame.new_from_api(game)
            lutris_game.save()
        logger.debug("Matching with already installed games")
        self.match_games()
        self.is_loading = False
        logger.debug("Lutris games loaded")
        self.emit("service-games-loaded")

    def install(self, db_game):
        if isinstance(db_game, dict):
            slug = db_game["slug"]
        else:
            slug = db_game
        installers = fetch_script(slug)
        if not installers:
            logger.warning("No installer for %s", slug)
            return
        application = Gio.Application.get_default()
        application.show_installer_window(installers)


def download_lutris_media(slug):
    """Downloads the banner and icon for a given lutris game"""
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
        icon_loader = MediaLoader()
        icon_loader.download_icons({slug: icon_url}, LutrisIcon())

    banner_url = response_data.get("banner_url")
    if banner_url:
        banner_loader = MediaLoader()
        banner_loader.download_icons({slug: banner_url}, LutrisBanner())
