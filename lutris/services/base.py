"""Generic service utilities"""
import os
import shutil

from gi.repository import GObject

from lutris import api, settings
from lutris.database import sql
from lutris.database.services import ServiceGameCollection
from lutris.util.cookies import WebkitCookieJar
from lutris.util.log import logger

PGA_DB = settings.PGA_DB


class BaseService(GObject.Object):
    """Base class for local services"""
    id = NotImplemented
    name = NotImplemented
    icon = NotImplemented
    online = False
    medias = {}
    default_format = "icon"

    __gsignals__ = {
        "service-games-loaded": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def wipe_game_cache(self):
        logger.debug("Deleting games from service-games for %s", self.id)
        sql.db_delete(PGA_DB, "service_games", "service", self.id)

    def match_games(self):
        """Matching of service games to lutris games"""
        service_games = {
            str(game["appid"]): game for game in ServiceGameCollection.get_for_service(self.id)
        }
        lutris_games = api.get_api_games(list(service_games.keys()), service=self.id)
        for lutris_game in lutris_games:
            for provider_game in lutris_game["provider_games"]:
                if provider_game["service"] != self.id:
                    print("Not the same")
                    continue
                service_game = service_games.get(provider_game["slug"])
                if not service_game:
                    print("No game for %s" % provider_game)
                    continue
                conditions = {"appid": service_game["appid"], "service": self.id}
                print(conditions)
                sql.db_update(
                    PGA_DB,
                    "service_games",
                    {"lutris_slug": lutris_game["slug"]},
                    conditions=conditions
                )


class OnlineService(BaseService):
    """Base class for online gaming services"""

    __gsignals__ = {
        "service-login": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "service-logout": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    online = True
    cookies_path = NotImplemented
    cache_path = NotImplemented

    @property
    def credential_files(self):
        """Return a list of all files used for authentication
        """
        return [self.cookies_path]

    def is_authenticated(self):
        """Return whether the service is authenticated"""
        return all([os.path.exists(path) for path in self.credential_files])

    def wipe_game_cache(self):
        """Wipe the game cache, allowing it to be reloaded"""
        logger.debug("Wiping %s cache", self.id)
        if os.path.isdir(self.cache_path):
            shutil.rmtree(self.cache_path)
        elif os.path.exists(self.cache_path):
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
        # logger.debug("Loading cookies from %s", self.cookies_path)
        if not os.path.exists(self.cookies_path):
            logger.warning("No cookies found in %s, please authenticate first", self.cookies_path)
            return
        cookiejar = WebkitCookieJar(self.cookies_path)
        cookiejar.load()
        return cookiejar
