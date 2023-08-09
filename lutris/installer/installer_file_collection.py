"""Manipulates installer files"""
import os
from gettext import gettext as _

from lutris import cache, settings
from lutris.util import system
from lutris.util.log import logger
from lutris.util.strings import add_url_tags, gtk_safe


class InstallerFileCollection:
    """Representation of a collection of files in the `files` sections of an installer.
       Store files in a folder"""

    def __init__(self, game_slug, file_id, files_list, dest_folder=None):
        self.game_slug = game_slug
        self.id = file_id.replace("-", "_")  # pylint: disable=invalid-name
        self.num_files = len(files_list)
        self.files_list = files_list
        self._dest_folder = dest_folder  # Used to override the destination

    def copy(self):
        """Copy InstallerFileCollection"""
        # copy all InstallerFile inside file list
        new_file_list = []
        for file in self.files_list:
            new_file_list.append(file.copy())
        return InstallerFileCollection(self.game_slug, self.id, new_file_list, self.dest_file)

    @property
    def dest_file(self):
        """dest_file represents destination folder to all file collection"""
        if self._dest_folder:
            return self._dest_folder
        return self.cache_path

    @dest_file.setter
    def dest_file(self, value):
        self._dest_folder = value
        # try to set main gog file to dest_file
        for installer_file in self.files_list:
            if installer_file.id == "gogintaller":
                installer_file.dest_file = value

    def __str__(self):
        return "%s/%s" % (self.game_slug, self.id)

    @property
    def human_url(self):
        """Return game_slug"""
        return self.game_slug

    def get_label(self):
        """Return a human readable label for installer files"""
        return add_url_tags(gtk_safe(self.game_slug))

    @property
    def provider(self):
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
        for file in self.files_list:
            file.prepare()

    @property
    def is_cached(self):
        """Are the files available in the local PGA cache?"""
        if self.uses_pga_cache():
            # check if every file is on cache
            for installer_file in self.files_list:
                if not system.path_exists(installer_file.dest_file):
                    return False
            return True
        return False
