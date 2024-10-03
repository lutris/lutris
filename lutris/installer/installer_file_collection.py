"""Manipulates installer files"""

import os
from gettext import gettext as _
from urllib.parse import urlparse

from lutris.cache import get_cache_path, has_custom_cache_path
from lutris.gui.widgets.download_collection_progress_box import DownloadCollectionProgressBox
from lutris.util import system
from lutris.util.strings import gtk_safe_urls

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
        if len(self.files_list) > 0:
            if self.files_list[0].total_size:
                self.full_size = self.files_list[0].total_size
            else:
                self.full_size = sum(f.size or 0 for f in self.files_list)

    def _get_service(self):
        """Try to get the service using the url of an InstallerFile"""
        self.service = None
        if len(self.files_list) < 1:
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

    def override_dest_file(self, new_dest_file):
        """Called by the UI when the user selects a file path; this causes
        the collection to be ready if this one file is there, and
        we'll special case GOG here too."""
        self._dest_file = new_dest_file

        if len(self.files_list) == 1:
            self.files_list[0].override_dest_file(new_dest_file)
        else:
            # try to set main gog file to dest_file
            for installer_file in self.files_list:
                if installer_file.id == "goginstaller":
                    installer_file.dest_file = new_dest_file

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
        return gtk_safe_urls(self.game_slug)

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

    def uses_pga_cache(self):
        """Determines whether the installer files are stored in a PGA cache

        Returns:
            bool
        """
        return has_custom_cache_path()

    @property
    def is_user_pga_caching_allowed(self):
        return len(self.files_list) == 1 and self.files_list[0].is_user_pga_caching_allowed

    @property
    def cache_path(self):
        """Return the directory used as a cache for the duration of the installation"""
        _cache_path = get_cache_path()
        return os.path.join(_cache_path, self.game_slug)

    def prepare(self):
        """Prepare the file for download, if we've not been redirected to an existing file."""
        if not self._dest_file or len(self.files_list) == 1:
            for installer_file in self.files_list:
                installer_file.prepare()

    def create_download_progress_box(self):
        return DownloadCollectionProgressBox(self)

    def is_ready(self, provider):
        """Is the file already present at the destination (if applicable)?"""
        if provider not in ("user", "pga"):
            return True

        if self._dest_file:
            return system.path_exists(self._dest_file)

        for installer_file in self.files_list:
            if not installer_file.is_ready(provider):
                return False
        return True

    @property
    def is_cached(self):
        """Are the files available in the local PGA cache?"""
        if self.uses_pga_cache():
            # check if every file is in cache, without checking
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
        """Remove file already at destination, prior to starting the download."""
        for installer_file in self.files_list:
            installer_file.remove_previous()
