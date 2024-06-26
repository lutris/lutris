"""Generic service utilities"""

import os
import shutil
from gettext import gettext as _
from pathlib import Path
from typing import Any, Dict, List

from gi.repository import Gio

from lutris import api, settings
from lutris.api import get_game_installers
from lutris.config import write_game_config
from lutris.database import sql
from lutris.database.games import add_game, get_game_by_field, get_game_for_service, get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import GAME_UPDATED, Game
from lutris.gui.dialogs import NoticeDialog
from lutris.gui.dialogs.webconnect_dialog import DEFAULT_USER_AGENT, WebConnectDialog
from lutris.gui.views.media_loader import download_media
from lutris.gui.widgets import NotificationSource
from lutris.gui.widgets.utils import BANNER_SIZE, ICON_SIZE
from lutris.services.service_media import ServiceMedia
from lutris.util import system
from lutris.util.cookies import WebkitCookieJar
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.strings import slugify


class AuthTokenExpiredError(Exception):
    """Exception raised when a token is no longer valid; the sidebar will
    log-out and log-in again in response to this rather than reporting it."""


class LutrisBanner(ServiceMedia):
    service = "lutris"
    size = BANNER_SIZE
    dest_path = settings.BANNER_PATH
    file_patterns = ["%s.jpg", "%s.png"]
    api_field = "banner"


class LutrisIcon(LutrisBanner):
    size = ICON_SIZE
    dest_path = settings.ICON_PATH
    file_patterns = ["lutris_%s.png"]
    api_field = "icon"

    @property
    def custom_media_storage_size(self):
        return (128, 128)

    def run_system_update_desktop_icons(self):
        system.update_desktop_icons()


class LutrisCoverart(ServiceMedia):
    service = "lutris"
    size = (264, 352)
    file_patterns = ["%s.jpg", "%s.png"]
    dest_path = settings.COVERART_PATH
    api_field = "coverart"

    @property
    def config_ui_size(self):
        return (66, 88)


class LutrisCoverartMedium(LutrisCoverart):
    size = (176, 234)


SERVICE_GAMES_LOADING = NotificationSource()
SERVICE_GAMES_LOADED = NotificationSource()
SERVICE_LOGIN = NotificationSource()
SERVICE_LOGOUT = NotificationSource()


class BaseService:
    """Base class for local services"""

    id = NotImplemented
    _matcher = None
    has_extras = False
    name = NotImplemented
    description = ""
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

    @property
    def matcher(self):
        if self._matcher:
            return self._matcher
        return self.id

    def run(self, launch_ui_delegate):
        """Launch the game client"""
        launcher = self.get_launcher()
        if launcher:
            launcher.launch(launch_ui_delegate)

    def is_launchable(self):
        if self.client_installer:
            return bool(get_game_by_field(self.client_installer, "slug"))
        return False

    def get_launcher(self):
        if not self.client_installer:
            return None
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
            SERVICE_GAMES_LOADED.fire(self)
            reloaded_callback(error)

        SERVICE_GAMES_LOADING.fire(self)
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
        sql.db_delete(settings.DB_PATH, "service_games", "service", self.id)

    def get_update_installers(self, db_game):
        return []

    def generate_installer(self, db_game: Dict[str, Any]) -> Dict[str, Any]:
        """Used to generate an installer from the data returned from the services"""
        return {}

    def generate_installers(self, db_game: Dict[str, Any]) -> List[dict]:
        """Used to generate a list of installers to choose from, from the data returned from the services
        By default this is just the installer from generate_installer(), and if overridden to return
        more than one, then generate_installer must be overridden ti pick a default installer."""
        installer = self.generate_installer(db_game)
        return [installer] if installer else []

    def install_from_api(self, db_game, appid=None):
        """Install a game, using the API or generate_installer() to obtain the installer."""
        if not appid:
            appid = db_game["appid"]

        def on_installers_ready(service_installers, error):
            if error:
                raise error  # bounce any error off the backstop

            if not service_installers:
                service_installers = self.generate_installers(db_game)
            application = Gio.Application.get_default()
            application.show_installer_window(service_installers, service=self, appid=appid)

        AsyncCall(self.get_installers_from_api, on_installers_ready, appid)

    def get_installer_files(self, installer, installer_file_id, selected_extras):
        """Used to obtains the content files from the service, when an 'N/A' file is left in
        the installer. This handles 'extras', and must return a tuple; first a list of
        InstallerFile or InstallerFileCollection objects that are for the files themselves,
        and then a list of such objects for the extras. This separation allows us to generate
        extra installer script steps to move the extras in."""
        return [], []

    def match_game(self, service_game, lutris_game):
        """Match a service game to a lutris game referenced by its slug"""
        if not service_game:
            return
        sql.db_update(
            settings.DB_PATH,
            "service_games",
            {"lutris_slug": lutris_game["slug"]},
            conditions={"appid": service_game["appid"], "service": self.id},
        )
        unmatched_lutris_games = get_games(
            searches={"installer_slug": self.matcher},
            filters={"slug": lutris_game["slug"]},
            excludes={"service": self.id},
        )
        for game in unmatched_lutris_games:
            logger.debug("Updating unmatched game %s", game)
            sql.db_update(
                settings.DB_PATH,
                "games",
                {"service": self.id, "service_id": service_game["appid"]},
                conditions={"id": game["id"]},
            )

    def match_games(self):
        """Matching of service games to lutris games"""
        service_games = {str(game["appid"]): game for game in ServiceGameCollection.get_for_service(self.id)}
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

    def match_existing_game(self, db_games, appid, no_signal=False):
        """Checks if a game is already installed and populates the service info"""
        for _game in db_games:
            logger.debug("Matching %s with existing install: %s", appid, _game)
            game = Game(_game["id"])
            game.appid = appid
            game.service = self.id
            game.save(no_signal=no_signal)
            service_game = ServiceGameCollection.get_game(self.id, appid)
            sql.db_update(settings.DB_PATH, "service_games", {"lutris_slug": game.slug}, {"id": service_game["id"]})
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

    def get_installed_slug(self, db_game):
        """Returns the slug the game will have after installation, by default. This
        is Lutris's slug, not the one for the service. By default, we derive it from
        the Game's name."""
        return slugify(db_game["name"])

    def get_installed_runner_name(self, db_game):
        """Returns the name of the runner this game will have after installation, or
        blank if this is not known."""
        return ""

    def get_service_installers(self, db_game, update):
        appid = db_game["appid"]
        if update:
            service_installers = self.get_update_installers(db_game)
        else:
            service_installers = self.get_installers_from_api(appid)
        # Check if the game is not already installed
        for service_installer in service_installers:
            existing_game = self.match_existing_game(
                get_games(filters={"installer_slug": service_installer["slug"], "installed": "1"}),
                appid,
                no_signal=True,  # we're on a thread here, signals can crash us!
            )
            if existing_game:
                logger.debug("Found existing game, aborting install")
                return None, None, existing_game
        installers = self.generate_installers(db_game) if not update else []
        if installers:
            if service_installers:
                for installer in installers:
                    installer["version"] = installer["version"] + " (auto-generated)"
            service_installers.extend(installers)
        if not service_installers:
            logger.error("No installer found for %s", db_game)
            return
        return service_installers, db_game, None

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
        logger.debug("Installing %s from service %s", db_game["appid"], self.id)
        # Local services (aka game libraries that don't require any type of online interaction) can
        # be added without going through an install dialog.
        if self.local:
            return self.simple_install(db_game)
        AsyncCall(self.get_service_installers, self.on_service_installers_loaded, db_game, update)

    def install_by_id(self, appid):
        """Installs a game given the appid for the game on this service."""
        db_game = ServiceGameCollection.get_game(self.id, appid)
        if not db_game:
            logger.error("No game %s found for %s", appid, self.id)
            return None
        return self.install(db_game)

    def on_service_installers_loaded(self, result, error):
        if error:
            raise error  # bounce this error off the backstop for default handling

        service_installers, db_game, existing_game = result

        # If an existing game was found, it may have been updated,
        # and it's not safe to fire this until we get here.
        if existing_game:
            GAME_UPDATED.fire(existing_game)

        if service_installers and db_game:
            application = Gio.Application.get_default()
            application.show_installer_window(service_installers, service=self, appid=db_game["appid"])

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

    def get_game_platforms(self, db_game: dict) -> List[str]:
        """Interprets the database record for this game from this service
        to extract its platform, or returns an empty list if this is not available."""
        return []

    def resolve_game_id(self, appid):
        db_game = get_game_for_service(self.id, appid)

        if db_game and db_game.get("id"):
            return str(db_game.get("id"))

        return None

    def get_service_db_game(self, game: Game):
        """Returns the row dictionary for the service-game corresponding to the game given, if any, or None."""
        if game.service == self.id and game.appid:
            return ServiceGameCollection.get_game(self.id, game.appid)
        return None


class OnlineService(BaseService):
    """Base class for online gaming services"""

    online = True
    cookies_path = NotImplemented
    cache_path = NotImplemented
    requires_login_page = False

    login_url = NotImplemented
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
                _(
                    "This service requires a game launcher. The following steps will install it.\n"
                    "Once the client is installed, you can login to %s."
                )
                % self.name
            )
            application = Gio.Application.get_default()
            application.show_lutris_installer_window(game_slug=self.client_installer)
            return
        logger.debug("Connecting to %s", self.name)
        dialog = WebConnectDialog(self, parent)
        dialog.run()

    @property
    def is_login_in_progress(self) -> bool:
        """Set to true if the login process is underway; the credential files make be created at this
        time, but that does not count as 'authenticated' until the login process is over. This is used
        by WebConnectDialog since it creates its cookies before the login is actually complete.

        This is recorded with a file in ~/.cache/lutris so it will persist across Lutris
        restarted, just as the credentials themselves do. For this reason, we need to allow
        the user to login again even when a login is in progress."""
        return self._get_login_in_progress_path().exists()

    @is_login_in_progress.setter
    def is_login_in_progress(self, in_progress: bool) -> None:
        path = self._get_login_in_progress_path()
        if in_progress:
            path.touch()
        else:
            path.unlink(missing_ok=True)

    def _get_login_in_progress_path(self) -> Path:
        return Path(os.path.join(settings.CACHE_DIR, f"{self.name}-login-in-progress"))

    def is_authenticated(self):
        """Return whether the service is authenticated"""
        return not self.is_login_in_progress and all(system.path_exists(path) for path in self.credential_files)

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
        SERVICE_LOGOUT.fire(self)

    def load_cookies(self):
        """Load cookies from disk"""
        if not system.path_exists(self.cookies_path):
            logger.warning("No cookies found in %s, please authenticate first", self.cookies_path)
            return
        cookiejar = WebkitCookieJar(self.cookies_path)
        cookiejar.load()
        return cookiejar
