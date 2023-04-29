"""Generic service utilities"""
import os
import shutil
from gettext import gettext as _

from gi.repository import Gio, GObject

from lutris import api, settings
from lutris.api import get_game_installers
from lutris.config import write_game_config
from lutris.database import sql
from lutris.database.games import add_game, get_game_by_field, get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui.dialogs import NoticeDialog
from lutris.gui.dialogs.webconnect_dialog import DEFAULT_USER_AGENT, WebConnectDialog
from lutris.gui.views.media_loader import download_media
from lutris.gui.widgets.utils import BANNER_SIZE, ICON_SIZE
from lutris.installer import get_installers
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.cookies import WebkitCookieJar
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger

PGA_DB = settings.PGA_DB


class AuthTokenExpired(Exception):
    """Exception raised when a token is no longer valid"""


class LutrisBanner(ServiceMedia):
    service = 'lutris'
    size = BANNER_SIZE
    dest_path = settings.BANNER_PATH
    file_pattern = "%s.jpg"
    file_format = "jpeg"
    api_field = 'banner_url'


class LutrisIcon(LutrisBanner):
    size = ICON_SIZE
    dest_path = settings.ICON_PATH
    file_pattern = "lutris_%s.png"
    file_format = "png"
    api_field = 'icon_url'

    @property
    def custom_media_storage_size(self):
        return (128, 128)

    def update_desktop(self):
        system.update_desktop_icons()


class LutrisCoverart(ServiceMedia):
    service = 'lutris'
    size = (264, 352)
    file_pattern = "%s.jpg"
    file_format = "jpeg"
    dest_path = settings.COVERART_PATH
    api_field = 'coverart'

    @property
    def config_ui_size(self):
        return (66, 88)


class LutrisCoverartMedium(LutrisCoverart):
    size = (176, 234)


class BaseService(GObject.Object):
    """Base class for local services"""
    id = NotImplemented
    _matcher = None
    has_extras = False
    name = NotImplemented
    icon = NotImplemented
    online = False
    local = False
    drm_free = False  # DRM free games can be added to Lutris from an existing install
    client_installer = None  # ID of a script needed to install the client used by the service
    scripts = {}  # Mapping of Javascript snippets to handle redirections during auth
    medias = {}
    extra_medias = {}
    default_format = "icon"
    is_loading = False

    __gsignals__ = {
        "service-games-load": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "service-games-loaded": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "service-login": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "service-logout": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    @property
    def matcher(self):
        if self._matcher:
            return self._matcher
        return self.id

    def run(self):
        """Launch the game client"""
        launcher = self.get_launcher()
        if launcher:
            launcher.emit("game-launch")

    def is_launchable(self):
        if self.client_installer:
            return get_game_by_field(self.client_installer, "slug")
        return False

    def get_launcher(self):
        if not self.client_installer:
            return
        db_launcher = get_game_by_field(self.client_installer, "slug")
        if db_launcher:
            return Game(db_launcher["id"])

    def is_launcher_installed(self):
        launcher = self.get_launcher()
        if not launcher:
            return False
        return launcher.is_installed

    def start_reload(self, reloaded_callback):
        """Refresh the service's games, asynchronously. This raises signals, but
        does so on the main thread- and runs the reload on a worker thread. It calls
        reloaded_callback when done, passing any error (or None on success)"""
        def do_reload():
            if self.is_loading:
                logger.warning("'%s' games are already loading", self.name)
                return

            try:
                self.is_loading = True

                self.wipe_game_cache()
                self.load()
                self.load_icons()
                self.add_installed_games()
            finally:
                self.is_loading = False

        def reload_cb(_result, error):
            self.emit("service-games-loaded")
            reloaded_callback(error)

        self.emit("service-games-load")
        AsyncCall(do_reload, reload_cb)

    def load(self):
        logger.warning("Load method not implemented")

    def load_icons(self):
        """Download all game media from the service"""
        all_medias = self.medias.copy()
        all_medias.update(self.extra_medias)

        service_medias = [media_type() for media_type in all_medias.values()]

        # Download icons
        for service_media in service_medias:
            media_urls = service_media.get_media_urls()
            download_media(media_urls, service_media)

        # Process icons
        for service_media in service_medias:
            service_media.render()

    def wipe_game_cache(self):
        logger.debug("Deleting games from service-games for %s", self.id)
        sql.db_delete(PGA_DB, "service_games", "service", self.id)

    def get_update_installers(self, db_game):
        return []

    def generate_installer(self, db_game):
        """Used to generate an installer from the data returned from the services"""
        return {}

    def match_game(self, service_game, api_game):
        """Match a service game to a lutris game referenced by its slug"""
        if not service_game:
            return
        sql.db_update(
            PGA_DB,
            "service_games",
            {"lutris_slug": api_game["slug"]},
            conditions={"appid": service_game["appid"], "service": self.id}
        )
        unmatched_lutris_games = get_games(
            searches={"installer_slug": self.matcher},
            filters={"slug": api_game["slug"]},
            excludes={"service": self.id}
        )
        for game in unmatched_lutris_games:
            logger.debug("Updating unmatched game %s", game)
            sql.db_update(
                PGA_DB,
                "games",
                {"service": self.id, "service_id": service_game["appid"]},
                conditions={"id": game["id"]}
            )

    def match_games(self):
        """Matching of service games to lutris games"""
        service_games = {
            str(game["appid"]): game for game in ServiceGameCollection.get_for_service(self.id)
        }
        lutris_games = api.get_api_games(list(service_games.keys()), service=self.id)
        for lutris_game in lutris_games:
            for provider_game in lutris_game["provider_games"]:
                if provider_game["service"] != self.id:
                    continue
                self.match_game(service_games.get(provider_game["slug"]), lutris_game)
        unmatched_service_games = get_games(searches={"installer_slug": self.matcher}, excludes={"service": self.id})
        for lutris_game in api.get_api_games(game_slugs=[g["slug"] for g in unmatched_service_games]):
            for provider_game in lutris_game["provider_games"]:
                if provider_game["service"] != self.id:
                    continue
                self.match_game(service_games.get(provider_game["slug"]), lutris_game)

    def match_existing_game(self, db_games, appid):
        """Checks if a game is already installed and populates the service info"""
        for _game in db_games:
            logger.debug("Matching %s with existing install: %s", appid, _game)
            game = Game(_game["id"])
            game.appid = appid
            game.service = self.id
            game.save()
            service_game = ServiceGameCollection.get_game(self.id, appid)
            sql.db_update(PGA_DB, "service_games", {"lutris_slug": game.slug}, {"id": service_game["id"]})
            return game

    def get_installers_from_api(self, appid):
        """Query the lutris API for an appid and get existing installers for the service"""
        lutris_games = api.get_api_games([appid], service=self.id)
        service_installers = []
        if lutris_games:
            lutris_game = lutris_games[0]
            installers = get_game_installers(lutris_game["slug"])
            for installer in installers:
                if self.matcher in installer["version"].lower():
                    service_installers.append(installer)
        return service_installers

    def install(self, db_game, update=False):
        """Install a service game, or starts the installer of the game.

        Args:
            db_game (dict or str): Database fields of the game to add, or (for Lutris service only
                the slug of the game.)

        Returns:
            str: The slug of the game that was installed, to be run. None if the game should not be
                run now. Many installers start from here, but continue running after this returns;
                they return None.
        """
        appid = db_game["appid"]
        logger.debug("Installing %s from service %s", appid, self.id)

        # Local services (aka game libraries that don't require any type of online interaction) can
        # be added without going through an install dialog.
        if self.local:
            return self.simple_install(db_game)
        if update:
            service_installers = self.get_update_installers(db_game)
        else:
            service_installers = self.get_installers_from_api(appid)
        # Check if the game is not already installed
        for service_installer in service_installers:
            existing_game = self.match_existing_game(
                get_games(filters={"installer_slug": service_installer["slug"], "installed": "1"}),
                appid
            )
            if existing_game:
                logger.debug("Found existing game, aborting install")
                return
        if update:
            installer = None
        else:
            installer = self.generate_installer(db_game)
        if installer:
            if service_installers:
                installer["version"] = installer["version"] + " (auto-generated)"
            service_installers.append(installer)
        if not service_installers:
            logger.error("No installer found for %s", db_game)
            return

        application = Gio.Application.get_default()
        application.show_installer_window(service_installers, service=self, appid=appid)

    def simple_install(self, db_game):
        """A simplified version of the install method, used when a game doesn't need any setup"""
        installer = self.generate_installer(db_game)
        configpath = write_game_config(db_game["slug"], installer["script"])
        game_id = add_game(
            name=installer["name"],
            runner=installer["runner"],
            slug=installer["game_slug"],
            directory=self.get_game_directory(installer),
            installed=1,
            installer_slug=installer["slug"],
            configpath=configpath,
            service=self.id,
            service_id=db_game["appid"],
        )
        return game_id

    def add_installed_games(self):
        """Services can implement this method to scan for locally
        installed games and add them to lutris.

        This runs on a worker thread, and must trigger UI actions -
        so no emitting signals here.
        """

    def get_game_directory(self, _installer):
        """Specific services should implement this"""
        return ""

    def get_game_platforms(self, db_game):
        """Interprets the database record for this game from this service
        to extract its platform, or returns None if this is not available."""
        return None


class OnlineService(BaseService):
    """Base class for online gaming services"""

    online = True
    cookies_path = NotImplemented
    cache_path = NotImplemented
    requires_login_page = False

    login_window_width = 390
    login_window_height = 500
    login_user_agent = DEFAULT_USER_AGENT

    @property
    def credential_files(self):
        """Return a list of all files used for authentication"""
        return [self.cookies_path]

    def login(self, parent=None):
        if self.client_installer and not self.is_launcher_installed():
            NoticeDialog(
                _("This service requires a game launcher. The following steps will install it.\n"
                  "Once the client is installed, you can login to %s.") % self.name)
            application = Gio.Application.get_default()
            installers = get_installers(game_slug=self.client_installer)
            application.show_installer_window(installers)
            return
        logger.debug("Connecting to %s", self.name)
        dialog = WebConnectDialog(self, parent)
        dialog.run()

    def is_authenticated(self):
        """Return whether the service is authenticated"""
        return all(system.path_exists(path) for path in self.credential_files)

    def wipe_game_cache(self):
        """Wipe the game cache, allowing it to be reloaded"""
        if self.cache_path:
            logger.debug("Deleting %s cache %s", self.id, self.cache_path)
            if os.path.isdir(self.cache_path):
                shutil.rmtree(self.cache_path)
            elif system.path_exists(self.cache_path):
                os.remove(self.cache_path)
        super().wipe_game_cache()

    def logout(self):
        """Disconnect from the service by removing all credentials"""
        self.wipe_game_cache()
        for auth_file in self.credential_files:
            try:
                os.remove(auth_file)
            except OSError:
                logger.warning("Unable to remove %s", auth_file)
        logger.debug("logged out from %s", self.id)
        self.emit("service-logout")

    def load_cookies(self):
        """Load cookies from disk"""
        if not system.path_exists(self.cookies_path):
            logger.warning("No cookies found in %s, please authenticate first", self.cookies_path)
            return
        cookiejar = WebkitCookieJar(self.cookies_path)
        cookiejar.load()
        return cookiejar
