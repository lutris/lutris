"""Generic service utilities"""
import os
import shutil

from gi.repository import Gio, GObject

from lutris import api, settings
from lutris.config import write_game_config
from lutris.database import sql
from lutris.database.games import add_game, get_games
from lutris.database.services import ServiceGameCollection
from lutris.game import Game
from lutris.gui.dialogs.webconnect_dialog import WebConnectDialog
from lutris.gui.views.media_loader import download_icons
from lutris.installer import fetch_script
from lutris.util import system
from lutris.util.cookies import WebkitCookieJar
from lutris.util.log import logger

PGA_DB = settings.PGA_DB


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
    medias = {}
    default_format = "icon"

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

    def reload(self):
        """Refresh the service's games"""
        self.emit("service-games-load")
        self.wipe_game_cache()
        self.load()
        self.load_icons()
        self.add_installed_games()
        self.emit("service-games-loaded")

    def load(self):
        logger.warning("Load method not implemented")

    def load_icons(self):
        """Download all game media from the service"""
        for icon_type in self.medias:
            service_media = self.medias[icon_type]()
            media_urls = service_media.get_media_urls()
            download_icons(media_urls, service_media)

    def wipe_game_cache(self):
        logger.debug("Deleting games from service-games for %s", self.id)
        sql.db_delete(PGA_DB, "service_games", "service", self.id)

    def generate_installer(self, db_game):
        """Used to generate an installer from the data returned from the services"""
        return {}

    def match_game(self, service_game, api_game):
        """Match a service game to a lutris game referenced by its slug"""
        if not service_game:
            return
        logger.debug("Matching service game %s with API game %s", service_game, api_game)
        conditions = {"appid": service_game["appid"], "service": self.id}
        sql.db_update(
            PGA_DB,
            "service_games",
            {"lutris_slug": api_game["slug"]},
            conditions=conditions
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
        logger.debug("Matching games %s", service_games)
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
            installers = fetch_script(lutris_game["slug"])
            for installer in installers:
                if self.matcher in installer["version"].lower():
                    service_installers.append(installer)
        return service_installers

    def install(self, db_game):
        """Install a service game"""
        appid = db_game["appid"]
        logger.debug("Installing %s from service %s", appid, self.id)
        if self.local:
            return self.simple_install(db_game)
        service_installers = self.get_installers_from_api(appid)
        # Check if the game is not already installed
        for service_installer in service_installers:
            existing_game = self.match_existing_game(
                get_games(filters={"installer_slug": service_installer["slug"], "installed": "1"}),
                appid
            )
            if existing_game:
                return
        if not service_installers:
            installer = self.generate_installer(db_game)
            if installer:
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
        """

    def get_game_directory(self, _installer):
        """Specific services should implement this"""
        return ""


class OnlineService(BaseService):
    """Base class for online gaming services"""

    online = True
    cookies_path = NotImplemented
    cache_path = NotImplemented
    requires_login_page = False

    @property
    def credential_files(self):
        """Return a list of all files used for authentication"""
        return [self.cookies_path]

    def login(self, parent=None):
        logger.debug("Connecting to %s", self.name)
        dialog = WebConnectDialog(self, parent)
        dialog.set_modal(True)
        dialog.show()

    def is_authenticated(self):
        """Return whether the service is authenticated"""
        return all([system.path_exists(path) for path in self.credential_files])

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
