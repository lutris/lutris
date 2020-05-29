"""Generic service utilities"""
# Standard Library
import os
import shutil

# Lutris Modules
from lutris.util.cookies import WebkitCookieJar
from lutris.util.log import logger


class OnlineService:

    """Base class for online gaming services"""

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
        if os.path.isdir(self.cache_path):
            shutil.rmtree(self.cache_path)
        elif os.path.exists(self.cache_path):
            os.remove(self.cache_path)

    def disconnect(self):
        """Disconnect from the service by removing all credentials"""
        self.wipe_game_cache()
        for auth_file in self.credential_files:
            try:
                os.remove(auth_file)
            except OSError:
                logger.warning("Unable to remove %s", auth_file)

    def load_cookies(self):
        """Load cookies from disk"""
        # logger.debug("Loading cookies from %s", self.cookies_path)
        if not os.path.exists(self.cookies_path):
            logger.warning("No cookies found in %s, please authenticate first", self.cookies_path)
            return
        cookiejar = WebkitCookieJar(self.cookies_path)
        cookiejar.load()
        return cookiejar
