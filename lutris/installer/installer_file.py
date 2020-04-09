"""Manipulates installer files"""
import os
from urllib.parse import urlparse
from lutris import pga
from lutris import settings
from lutris.installer.errors import ScriptingError, FileNotAvailable
from lutris.util.log import logger
from lutris.util import system
from lutris.cache import get_cache_path


class InstallerFile:
    """Representation of a file in the `files` sections of an installer"""
    def __init__(self, game_slug, file_id, file_meta):
        self.game_slug = game_slug
        self.id = file_id  # pylint: disable=invalid-name
        self.dest_file = None
        if isinstance(file_meta, dict):
            for field in ("url", "filename"):
                if field not in file_meta:
                    raise ScriptingError(
                        "missing field `%s` for file `%s`" % (field, file_id)
                    )
            self.url = file_meta["url"]
            self.filename = file_meta["filename"]
            self.referer = file_meta.get("referer")
            self.checksum = file_meta.get("checksum")
        else:
            self.url = file_meta
            self.filename = os.path.basename(file_meta)
            self.referer = None
            self.checksum = None

        if self.url.startswith(("$STEAM", "$WINESTEAM")):
            self.filename = self.url

        if self.url.startswith("/"):
            self.url = "file://" + self.url

        if not self.filename:
            logger.error("Couldn't find a filename for file %s in %s", file_id, file_meta)
            raise ScriptingError(
                "No filename provided for %s, please provide 'url' "
                "and 'filename' parameters in the script" % file_id
            )
        if self.uses_pga_cache(create=True):
            logger.debug("Using cache path %s", self.cache_path)

    def __str__(self):
        return "%s/%s" % (self.game_slug, self.id)

    def uses_pga_cache(self, create=False):
        """Determines whether the installer files are stored in a PGA cache

        Params:
            create (bool): If a cache is active, auto create directories if needed
        Returns:
            bool
        """
        cache_path = get_cache_path()
        if not cache_path:
            return False
        if system.path_exists(cache_path):
            return True
        if create:
            try:
                os.makedirs(self.cache_path)
            except OSError as ex:
                logger.error("Failed to created cache path: %s", ex)
                return False
            return True
        logger.warning("Cache path %s does not exist", cache_path)
        return False

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        _cache_path = get_cache_path()
        if not _cache_path:
            _cache_path = os.path.join(settings.CACHE_DIR, "installer")
        url_parts = urlparse(self.url)
        if url_parts.netloc.endswith("gog.com"):
            folder = "gog"
        else:
            folder = self.id
        return os.path.join(_cache_path, self.game_slug, folder)

    def get_download_info(self):
        """Retrieve the file locally"""
        if self.url.startswith(("$WINESTEAM", "$STEAM", "N/A")):
            raise FileNotAvailable()
        # Check for file availability in PGA
        pga_uri = pga.check_for_file(self.game_slug, self.id)
        if pga_uri:
            self.url = pga_uri

        dest_file = os.path.join(self.cache_path, self.filename)
        logger.debug("Downloading [%s]: %s to %s", self.id, self.url, dest_file)

        if not self.uses_pga_cache() and os.path.exists(dest_file):
            os.remove(dest_file)
        self.dest_file = dest_file
        return self.dest_file

    def check_hash(self):
        """Checks the checksum of `file` and compare it to `value`

        Args:
            checksum (str): The checksum to look for (type:hash)
            dest_file (str): The path to the destination file
            dest_file_uri (str): The uri for the destination file
        """
        if not self.checksum or not self.dest_file:
            return
        try:
            hash_type, expected_hash = self.checksum.split(':', 1)
        except ValueError:
            raise ScriptingError("Invalid checksum, expected format (type:hash) ", self.checksum)

        if system.get_file_checksum(self.dest_file, hash_type) != expected_hash:
            raise ScriptingError(hash_type.capitalize() + " checksum mismatch ", self.checksum)

    def download(self, downloader):
        """Download a file with a given downloader"""
        if self.uses_pga_cache() and system.path_exists(self.dest_file):
            logger.info("File %s already cached", self)
            return False

        if not system.path_exists(self.cache_path):
            os.makedirs(self.cache_path)
        downloader(
            self.url,
            self.dest_file,
            callback=self.check_hash,
            referer=self.referer
        )
        return True
