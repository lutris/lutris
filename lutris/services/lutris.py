import json
import os
from gettext import gettext as _
from typing import Any, Dict, Iterable, List, Optional

from gi.repository import Gio

from lutris import settings
from lutris.api import get_api_games, get_game_installers, read_api_key
from lutris.database.games import get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.views.media_loader import download_media
from lutris.services.base import LutrisBanner, LutrisCoverart, LutrisCoverartMedium, LutrisIcon, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.util import http
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger


class LutrisGame(ServiceGame):
    """Service game created from the Lutris API"""

    service = "lutris"

    @classmethod
    def new_from_api(cls, api_payload):
        """Create an instance of LutrisGame from the API response"""
        service_game = LutrisGame()
        service_game.appid = api_payload["slug"]
        service_game.slug = api_payload["slug"]
        service_game.name = api_payload["name"]
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
        service_games = {str(game["appid"]): game for game in ServiceGameCollection.get_for_service(self.id)}
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
        url = settings.SITE_URL + "/api/users/library"
        request = http.Request(url, headers={"Authorization": "Token " + credentials["token"]})
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Unable to load library: %s", ex)
            return []
        return response.json

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

    def load_icons(self):
        super().load_icons()
        # Also load any media for games that use Lutris media,
        # but are not in the Lutris library.
        sync_media()

    def get_installed_slug(self, db_game):
        return db_game["slug"]

    def install(self, db_game):
        slug = db_game["slug"]
        return self.install_by_id(slug)

    def install_by_id(self, appid):
        def on_installers_ready(installers, error):
            if error:
                raise error  # bounce any error off the backstop
            if not installers:
                raise RuntimeError(_("Lutris has no installers for %s. Try using a different service instead.") % appid)
            application = Gio.Application.get_default()
            application.show_installer_window(installers)

        AsyncCall(get_game_installers, on_installers_ready, appid)  # appid is the slug for Lutris games

    def get_installed_runner_name(self, db_game):
        platforms = self.get_game_platforms(db_game)

        if platforms and len(platforms) == 1:
            platform = platforms[0].casefold()

            if platform == "windows":
                return "wine"

            if platform == "linux":
                return "linux"

            if platform == "ms-dos":
                return "dosbox"

        return ""

    def get_game_platforms(self, db_game: dict) -> List[str]:
        details = db_game.get("details")
        if details:
            platforms = json.loads(details).get("platforms")
            if platforms is not None:
                return [p.get("name") for p in platforms]
        return []

    def get_service_db_game(self, game: Game):
        if game.service == self.id and game.slug:
            return ServiceGameCollection.get_game(self.id, game.slug)
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
    icon_url = _get_response_game_icon(response_data)
    if icon_url:
        download_media({slug: icon_url}, LutrisIcon())

    banner_url = _get_response_game_banner(response_data)
    if banner_url:
        download_media({slug: banner_url}, LutrisBanner())

    coverart_url = _get_response_game_coverart(response_data)
    if coverart_url:
        download_media({slug: coverart_url}, LutrisCoverart())


def sync_media(slugs: Iterable[str] = None) -> Dict[str, int]:
    """Download missing media for Lutris games; if a set of slugs
    is not provided, downloads them for all games in the PGA."""
    if slugs is None:
        slugs = {game["slug"] for game in get_games()}
    else:
        slugs = set(s for s in slugs if s)

    if not slugs:
        return {}

    banners_available = {fn.split(".")[0] for fn in os.listdir(settings.BANNER_PATH)}
    icons_available = {
        fn.split(".")[0].replace("lutris_", "") for fn in os.listdir(settings.ICON_PATH) if fn.startswith("lutris_")
    }
    covers_available = {fn.split(".")[0] for fn in os.listdir(settings.COVERART_PATH)}
    complete_games = banners_available.intersection(icons_available).intersection(covers_available)

    slugs_to_download = slugs - complete_games
    if not slugs_to_download:
        return {}
    games = get_api_games(list(slugs_to_download))

    alias_map = {}
    api_slugs = set()
    for game in games:
        api_slugs.add(game["slug"])
        for alias in game["aliases"]:
            if alias["slug"] in slugs_to_download:
                alias_map[game["slug"]] = alias["slug"]
    alias_slugs = set(alias_map.values())
    used_alias_slugs = alias_slugs - api_slugs
    for alias_slug in used_alias_slugs:
        for game in games:
            if alias_slug in [alias["slug"] for alias in game["aliases"]]:
                game["slug"] = alias_map[game["slug"]]
                continue
    banner_urls = {
        game["slug"]: _get_response_game_banner(game)
        for game in games
        if game["slug"] not in banners_available and _get_response_game_banner(game)
    }
    icon_urls = {
        game["slug"]: _get_response_game_icon(game)
        for game in games
        if game["slug"] not in icons_available and _get_response_game_icon(game)
    }
    coverart_urls = {
        game["slug"]: _get_response_game_coverart(game)
        for game in games
        if game["slug"] not in covers_available and _get_response_game_coverart(game)
    }
    logger.debug("Syncing %s banners, %s icons and %s covers", len(banner_urls), len(icon_urls), len(coverart_urls))
    download_media(banner_urls, LutrisBanner())
    download_media(icon_urls, LutrisIcon())
    download_media(coverart_urls, LutrisCoverart())
    return {
        "banners": len(banner_urls),
        "icons": len(icon_urls),
        "covers": len(coverart_urls),
    }


def _get_response_game_coverart(api_game: Dict[str, Any]) -> Optional[str]:
    return api_game.get("coverart")


def _get_response_game_banner(api_game: Dict[str, Any]) -> Optional[str]:
    return api_game.get("banner_url") or api_game.get("banner")


def _get_response_game_icon(api_game: Dict[str, Any]) -> Optional[str]:
    return api_game.get("icon_url") or api_game.get("icon")
