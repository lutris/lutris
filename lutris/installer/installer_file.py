"""Manipulates installer files"""
import os
from gettext import gettext as _
from urllib.parse import urlparse

from lutris import cache
from lutris.cache import has_custom_cache_path, save_to_cache
from lutris.gui.widgets.download_progress_box import DownloadProgressBox
from lutris.installer.errors import ScriptingError
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import gtk_safe_urls


class InstallerFile:
    """Representation of a file in the `files` sections of an installer"""

    def __init__(self, game_slug, file_id, file_meta, dest_file=None):
        self.game_slug = game_slug
        self.id = file_id.replace("-", "_")  # pylint: disable=invalid-name
        self._file_meta = file_meta
        self._dest_file = dest_file  # Used to override the destination

    def copy(self):
        """Copies this file object, so the copy can be modified safely."""
        if isinstance(self._file_meta, dict):
            return InstallerFile(self.game_slug, self.id, self._file_meta.copy(), self._dest_file)

        return InstallerFile(self.game_slug, self.id, self._file_meta, self._dest_file)

    @property
    def url(self):
        _url = ""
        if isinstance(self._file_meta, dict):
            if "url" not in self._file_meta:
                raise ScriptingError(_("missing field `url` for file `%s`") % self.id)
            _url = self._file_meta["url"]
        else:
            _url = self._file_meta
        if _url.startswith("/"):
            return "file://" + _url
        return _url

    def set_url(self, url):
        """Change the internal value of the URL"""
        if isinstance(self._file_meta, dict):
            self._file_meta["url"] = url
        else:
            self._file_meta = url

    @property
    def filename(self):
        if isinstance(self._file_meta, dict):
            if "filename" not in self._file_meta:
                raise ScriptingError(_("missing field `filename` in file `%s`") % self.id)
            return self._file_meta["filename"]
        if self._file_meta.startswith("N/A"):
            if self.uses_pga_cache() and os.path.isdir(self.cache_path):
                return self.cached_filename
            return ""
        if self.url.startswith("$STEAM"):
            return self.url
        return os.path.basename(self._file_meta)

    @property
    def referer(self):
        if isinstance(self._file_meta, dict):
            return self._file_meta.get("referer")

    @property
    def downloader(self):
        if isinstance(self._file_meta, dict):
            dl = self._file_meta.get("downloader")
            if dl and not dl.dest:
                dl.dest = self.dest_file
            return dl

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

    def override_dest_file(self, new_dest_file):
        """Called by the UI when the user selects a file path."""
        self.dest_file = new_dest_file

    def get_dest_files_by_id(self):
        return {self.id: self.dest_file}

    def __str__(self):
        return "%s/%s" % (self.game_slug, self.id)

    @property
    def auxiliary_info(self):
        """Provides a small bit of additional descriptive texts to show in the UI."""
        return None

    @property
    def human_url(self):
        """Return the url in human-readable format"""
        if self.url.startswith("N/A"):
            # Ask the user where the file is located
            parts = self.url.split(":", 1)
            if len(parts) == 2:
                return parts[1]
            return "Please select file '%s'" % self.id
        return self.url

    def get_label(self):
        """Return a human readable label for installer files"""
        url = self.url
        if url.startswith("http"):
            parsed = urlparse(url)
            label = _("{file} on {host}").format(file=self.filename, host=parsed.netloc)
        elif url.startswith("N/A"):
            label = url[3:].lstrip(":")
        else:
            label = url
        return gtk_safe_urls(label)

    @property
    def cached_filename(self):
        """Return the filename of the first file in the cache path"""
        cache_files = os.listdir(self.cache_path)
        if cache_files:
            return cache_files[0]
        return ""

    @property
    def default_provider(self):
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

    def uses_pga_cache(self):
        """Determines whether the installer files are stored in a PGA cache

        Returns:
            bool
        """
        if self.url.startswith("N/A"):
            return False
        return has_custom_cache_path()

    @property
    def is_user_pga_caching_allowed(self):
        """Returns true if this file can be transferred to the cache, if
        the user provides it."""
        return self.uses_pga_cache()

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        _cache_path = cache.get_cache_path()
        url_parts = urlparse(self.url)
        if url_parts.netloc.endswith("gog.com"):
            folder = "gog"
        else:
            folder = self.id
        return os.path.join(_cache_path, self.game_slug, folder)

    def prepare(self):
        """Prepare the file for download, if we've not been redirected to an existing file."""
        if not self._dest_file and not system.path_exists(self.cache_path):
            os.makedirs(self.cache_path)

    def create_download_progress_box(self):
        return DownloadProgressBox({
            "url": self.url,
            "dest": self.dest_file,
            "referer": self.referer
        }, downloader=self.downloader)

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
            raise ScriptingError(_("Invalid checksum, expected format (type:hash) "), self.checksum) from err

        if system.get_file_checksum(self.dest_file, hash_type) != expected_hash:
            raise ScriptingError(hash_type.capitalize() + _(" checksum mismatch "), self.checksum)

    @property
    def size(self):
        if isinstance(self._file_meta, dict) and "size" in self._file_meta and isinstance(self._file_meta["size"], int):
            return self._file_meta["size"]
        return 0

    @property
    def total_size(self):
        if isinstance(self._file_meta, dict) and "total_size" in self._file_meta:
            return self._file_meta["total_size"]
        return 0

    def is_ready(self, provider):
        """Is the file already present at the destination (if applicable)?"""
        return provider not in ("user", "pga") or system.path_exists(self.dest_file)

    @property
    def is_cached(self):
        """Is the file available in the local PGA cache?"""
        return self.uses_pga_cache() and system.path_exists(self.dest_file)

    def save_to_cache(self):
        """Copy the file into the PGA cache."""

        cache_path = self.cache_path
        try:
            if not os.path.isdir(cache_path):
                logger.debug("Creating cache path %s", self.cache_path)
                os.makedirs(cache_path)
        except (OSError, PermissionError) as ex:
            logger.error("Failed to created cache path: %s", ex)
            return

        save_to_cache(self.dest_file, cache_path)

    def remove_previous(self):
        """Remove file at already at destination, prior to starting the download."""
        if (
            not self.uses_pga_cache()
            and system.path_exists(self.dest_file)
        ):
            # If we've previously downloaded a directory, we'll need to get rid of it
            # to download a file now. Since we are not using the cache, we don't keep
            # these files anyway - so it should be safe to just nuke and pave all this.
            if os.path.isdir(self.dest_file):
                system.delete_folder(self.dest_file)
            else:
                os.remove(self.dest_file)
