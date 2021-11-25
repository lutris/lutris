"""Manipulates installer files"""
import os
from urllib.parse import urlparse

from lutris import cache, settings
from lutris.installer.errors import ScriptingError
from lutris.util import system
from lutris.util.log import logger


class InstallerFile:
    """Representation of a file in the `files` sections of an installer"""

    def __init__(self, game_slug, file_id, file_meta):
        self.game_slug = game_slug
        self.id = file_id.replace("-", "_")  # pylint: disable=invalid-name
        self._file_meta = file_meta
        self._dest_file = None  # Used to override the destination

    @property
    def url(self):
        _url = ""
        if isinstance(self._file_meta, dict):
            if "url" not in self._file_meta:
                raise ScriptingError("missing field `url` for file `%s`" % self.id)
            _url = self._file_meta["url"]
        else:
            _url = self._file_meta
        if _url.startswith("/"):
            return "file://" + _url
        return _url

    @property
    def filename(self):
        if isinstance(self._file_meta, dict):
            if "filename" not in self._file_meta:
                raise ScriptingError("missing field `filename` in file `%s`" % self.id)
            return self._file_meta["filename"]
        if self._file_meta.startswith("N/A"):
            if self.uses_pga_cache() and os.path.isdir(self.cache_path):
                return self.cached_filename
            return ""
        if self.url.startswith("$STEAM"):
            return self.url
        if self.url.startswith("$WINESTEAM"):
            raise ScriptingError("Usage of $WINESTEAM location is deprecated")
        return os.path.basename(self._file_meta)

    @property
    def referer(self):
        if isinstance(self._file_meta, dict):
            return self._file_meta.get("referer")

    @property
    def checksum(self):
        if isinstance(self._file_meta, dict):
            return self._file_meta.get("checksum")

    @property
    def dest_file(self):
        if self._dest_file:
            return self._dest_file
        return os.path.join(self.cache_path, self.filename)

    @dest_file.setter
    def dest_file(self, value):
        self._dest_file = value

    def __str__(self):
        return "%s/%s" % (self.game_slug, self.id)

    @property
    def human_url(self):
        """Return the url in human readable format"""
        if self.url.startswith("N/A"):
            # Ask the user where the file is located
            parts = self.url.split(":", 1)
            if len(parts) == 2:
                return parts[1]
            return "Please select file '%s'" % self.id
        return self.url

    @property
    def cached_filename(self):
        """Return the filename of the first file in the cache path"""
        cache_files = os.listdir(self.cache_path)
        if cache_files:
            return cache_files[0]
        return ""

    @property
    def provider(self):
        """Return file provider used"""
        if self.url.startswith("$STEAM"):
            return "steam"
        if self.is_cached:
            return "pga"
        if self.url.startswith("N/A"):
            return "user"
        if self.is_downloadable():
            return "download"
        raise ValueError("Unsupported provider for %s" % self.url)

    @property
    def providers(self):
        """Return all supported providers"""
        _providers = set()
        if self.url.startswith("$STEAM"):
            _providers.add("steam")
        if self.is_cached:
            _providers.add("pga")
        if self.url.startswith("N/A"):
            _providers.add("user")
        if self.is_downloadable():
            _providers.add("download")
        return _providers

    def is_downloadable(self):
        """Return True if the file can be downloaded (even from the local filesystem)"""
        return self.url.startswith(("http", "file"))

    def uses_pga_cache(self, create=False):
        """Determines whether the installer files are stored in a PGA cache

        Params:
            create (bool): If a cache is active, auto create directories if needed
        Returns:
            bool
        """
        cache_path = cache.get_cache_path()
        if not cache_path:
            return False
        if system.path_exists(cache_path):
            return True
        if create:
            try:
                logger.debug("Creating cache path %s", self.cache_path)
                os.makedirs(self.cache_path)
            except (OSError, PermissionError) as ex:
                logger.error("Failed to created cache path: %s", ex)
                return False
            return True
        logger.warning("Cache path %s does not exist", cache_path)
        return False

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        _cache_path = cache.get_cache_path()
        if not _cache_path:
            _cache_path = os.path.join(settings.CACHE_DIR, "installer")
        url_parts = urlparse(self.url)
        if url_parts.netloc.endswith("gog.com"):
            folder = "gog"
        else:
            folder = self.id
        return os.path.join(_cache_path, self.game_slug, folder)

    def prepare(self):
        """Prepare the file for download"""
        if not system.path_exists(self.cache_path):
            os.makedirs(self.cache_path)

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
        except ValueError as err:
            raise ScriptingError("Invalid checksum, expected format (type:hash) ", self.checksum) from err

        if system.get_file_checksum(self.dest_file, hash_type) != expected_hash:
            raise ScriptingError(hash_type.capitalize() + " checksum mismatch ", self.checksum)

    @property
    def is_cached(self):
        """Is the file available in the local PGA cache?"""
        return self.uses_pga_cache() and system.path_exists(self.dest_file)
