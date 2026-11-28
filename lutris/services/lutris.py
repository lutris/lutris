import json
import os
from collections.abc import Iterable
from gettext import gettext as _
from typing import Any

from gi.repository import Gio

from lutris import settings
from lutris.api import get_game_installers, read_api_key
from lutris.database.games import get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui import dialogs
from lutris.gui.views.media_loader import download_media
from lutris.services.base import (
    SERVICE_LOGIN,
    LutrisBanner,
    LutrisCoverart,
    LutrisCoverartMedium,
    LutrisIcon,
    OnlineService,
)
from lutris.services.service_game import ServiceGame
from lutris.util import http
from lutris.util.busy import BusyAsyncCall
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
    icon = "net.lutris.Lutris"
    online = True
    medias = {
        "icon": LutrisIcon,
        "banner": LutrisBanner,
        "coverart_med": LutrisCoverartMedium,
        "coverart_big": LutrisCoverart,
    }
    default_format = "coverart_med"

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
        SERVICE_LOGIN.fire(self)

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
        # Remote-only library entries retain their legacy service artwork.
        local_slugs = {game["slug"] for game in get_games()}
        for media_type in {**self.medias, **self.extra_medias}.values():
            media = media_type()
            urls = {slug: url for slug, url in media.get_media_urls().items() if slug not in local_slugs}
            download_media(urls, media)
            media.render()
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

        BusyAsyncCall(get_game_installers, on_installers_ready, appid)  # appid is the slug for Lutris games

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

    def get_game_platforms(self, db_game: dict) -> list[str]:
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
    """Refresh every local row sharing this slug using its selected provider."""
    rows = [game for game in get_games() if game["slug"] == slug]
    if rows:
        from lutris.artwork import refresh_artwork

        refresh_artwork([game["id"] for game in rows])
    else:
        from lutris.artwork import get_effective_source

        if get_effective_source({}) == "lutris":
            _download_lutris_media(slug)


def _download_lutris_media(slug):
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


def sync_media(slugs: Iterable[str] | None = None) -> dict[str, int]:
    """Refresh matching library rows and retain the legacy plural count contract."""
    from lutris.artwork import refresh_artwork

    selected = set(slugs) if slugs is not None else None
    game_ids = [game["id"] for game in get_games() if selected is None or game["slug"] in selected]
    if not game_ids:
        return {}
    counts = {"banners": 0, "icons": 0, "covers": 0}
    names = {"banner": "banners", "icon": "icons", "cover": "covers"}
    for result in refresh_artwork(game_ids).values():
        for kind in result.updated_kinds:
            counts[names[kind]] += 1
    return counts


def _get_response_game_coverart(api_game: dict[str, Any]) -> str | None:
    return api_game.get("coverart")


def _get_response_game_banner(api_game: dict[str, Any]) -> str | None:
    return api_game.get("banner_url") or api_game.get("banner")


def _get_response_game_icon(api_game: dict[str, Any]) -> str | None:
    return api_game.get("icon_url") or api_game.get("icon")
