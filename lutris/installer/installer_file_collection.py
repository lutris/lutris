"""Manipulates installer files"""
import os
from functools import reduce
from urllib.parse import urlparse
from gettext import gettext as _

from lutris import cache, settings
from lutris.gui.widgets.download_collection_progress_box import DownloadCollectionProgressBox
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import add_url_tags, gtk_safe

AMAZON_DOMAIN = "a2z.com"


class InstallerFileCollection:
    """Representation of a collection of files in the `files` sections of an installer.
       Store files in a folder"""

    def __init__(self, game_slug, file_id, files_list, dest_file=None):
        self.game_slug = game_slug
        self.id = file_id.replace("-", "_")  # pylint: disable=invalid-name
        self.num_files = len(files_list)
        self.files_list = files_list
        self._dest_file = dest_file  # Used to override the destination
        self.full_size = 0
        self._get_files_size()
        self._get_service()

    def _get_files_size(self):
        if self.num_files > 0:
            self.full_size = reduce(lambda x, y: x + y, map(lambda a: a.size, self.files_list))

    def _get_service(self):
        """Try to get the service using the url of an InstallerFile"""
        self.service = None
        if self.num_files < 1:
            return
        url = self.files_list[0].url
        url_parts = urlparse(url)
        if url_parts.netloc.endswith(AMAZON_DOMAIN):
            self.service = "amazon"

    def copy(self):
        """Copy InstallerFileCollection"""
        # copy all InstallerFile inside file list
        new_file_list = []
        for file in self.files_list:
            new_file_list.append(file.copy())
        return InstallerFileCollection(self.game_slug, self.id, new_file_list, self._dest_file)

    @property
    def dest_file(self):
        """dest_file represents destination folder to all file collection"""
        if self._dest_file:
            return self._dest_file
        return self.cache_path

    @dest_file.setter
    def dest_file(self, value):
        self._dest_file = value
        # try to set main gog file to dest_file
        for installer_file in self.files_list:
            if installer_file.id == "goginstaller":
                installer_file.dest_file = value

    def get_dest_files_by_id(self):
        files = {}
        for file in self.files_list:
            files.update({file.id: file.dest_file})
        return files

    def __str__(self):
        return "%s/%s" % (self.game_slug, self.id)

    @property
    def auxiliary_info(self):
        """Provides a small bit of additional descriptive texts to show in the UI."""
        if self.num_files == 1:
            return f"{self.num_files} {_('File')}"

        return f"{self.num_files} {_('Files')}"

    @property
    def human_url(self):
        """Return game_slug"""
        return self.game_slug

    def get_label(self):
        """Return a human readable label for installer files"""
        return add_url_tags(gtk_safe(self.game_slug))

    @property
    def default_provider(self):
        """Return file provider used. File Collection only supports 'pga' and 'download'"""
        if self.is_cached:
            return "pga"
        return "download"

    @property
    def providers(self):
        """Return all supported providers. File Collection only supports 'pga' and 'download'"""
        _providers = set()
        if self.is_cached:
            _providers.add("pga")
        _providers.add("download")
        return _providers

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
                # make dirs to all files
                for installer_file in self.files_list:
                    os.makedirs(installer_file.cache_path)
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
        return os.path.join(_cache_path, self.game_slug)

    def prepare(self):
        """Prepare all files for download"""
        # File Collection do not need to prepare, only the files_list
        for installer_file in self.files_list:
            installer_file.prepare()

    def create_download_progress_box(self):
        return DownloadCollectionProgressBox(self)

    def is_ready(self, provider):
        """Are all the files already present at the destination?"""
        for installer_file in self.files_list:
            if not installer_file.is_ready(provider):
                return False
        return True

    @property
    def is_cached(self):
        """Are the files available in the local PGA cache?"""
        if self.uses_pga_cache():
            # check if every file is on cache, without checking
            # uses_pga_cache() on each.
            for installer_file in self.files_list:
                if not system.path_exists(installer_file.dest_file):
                    return False
            return True
        return False

    def save_to_cache(self):
        """Copy the files into the PGA cache."""
        for installer_file in self.files_list:
            installer_file.save_to_cache()

    def remove_previous(self):
        """Remove file at already at destination, prior to starting the download."""
        for installer_file in self.files_list:
            installer_file.remove_previous()
