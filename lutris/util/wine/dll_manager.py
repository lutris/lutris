"""Injects sets of DLLs into a prefix"""
import json
import os
import shutil
from gettext import gettext as _

from lutris.util import system
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger
from lutris.util.wine.prefix import WinePrefixManager


class DLLManager:
    """Utility class to install dlls to a Wine prefix"""
    component = NotImplemented
    base_dir = NotImplemented
    managed_dlls = NotImplemented
    managed_user_files = []  # most managers have none
    versions_path = NotImplemented
    releases_url = NotImplemented
    archs = {
        32: "x32",
        64: "x64"
    }

    def __init__(self, prefix=None, arch="win64", version=None):
        self.prefix = prefix
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)
        self._versions = []
        self._version = version
        self.wine_arch = arch

    @property
    def versions(self):
        """Return available versions"""
        self._versions = self.load_versions()
        if not self._versions:
            self._versions = os.listdir(self.base_dir)
        return self._versions

    @property
    def version(self):
        """Return version (latest known version if not provided)"""
        if self._version:
            return self._version
        if self.versions:
            return self.versions[0]

    @property
    def path(self):
        """Path to local folder containing DLLs"""
        version = self.version
        if not version:
            raise RuntimeError(
                "No path can be generated for %s because no version information is available." % self.component)
        return os.path.join(self.base_dir, version)

    @property
    def version_choices(self):
        _choices = [
            (_("Manual"), "manual"),
        ]
        for version in self.versions:
            _choices.append((version, version))
        return _choices

    def load_versions(self):
        if not system.path_exists(self.versions_path):
            return []
        with open(self.versions_path, "r", encoding='utf-8') as version_file:
            try:
                versions = [v["tag_name"] for v in json.load(version_file)]
            except (KeyError, json.decoder.JSONDecodeError):
                logger.warning(
                    "Invalid versions file %s, deleting so it is downloaded on next start.",
                    self.versions_path
                )
                os.remove(self.versions_path)
                return []
        return versions

    @staticmethod
    def is_managed_dll(dll_path):
        """Check if a given DLL path is provided by the component"""
        return False

    def is_available(self):
        """Return whether component is cached locally"""
        return self.version and system.path_exists(self.path)

    def dll_exists(self, dll_name):
        """Check if the dll is provided by the component
        The DLL might not be available for all architectures so
        only check if one exists for the supported ones
        """
        return any(
            system.path_exists(os.path.join(self.path, arch, dll_name + ".dll"))
            for arch in self.archs.values()
        )

    def get_download_url(self):
        """Fetch the download URL from the JSON version file"""
        with open(self.versions_path, "r", encoding='utf-8') as version_file:
            releases = json.load(version_file)
        for release in releases:
            if release["tag_name"] != self.version:
                continue
            return release["assets"][0]["browser_download_url"]

    def download(self):
        """Download component to the local cache; returns True if successful but False
        if the component could not be downloaded."""
        if self.is_available():
            logger.warning("%s already available at %s", self.component, self.path)

        url = self.get_download_url()
        if not url:
            logger.warning("Could not find a release for %s %s", self.component, self.version)
            return False
        archive_path = os.path.join(self.base_dir, os.path.basename(url))
        logger.info("Downloading %s to %s", url, archive_path)
        download_file(url, archive_path, overwrite=True)
        if not system.path_exists(archive_path) or not os.stat(archive_path).st_size:
            logger.error("Failed to download %s %s", self.component, self.version)
            return False
        logger.info("Extracting %s to %s", archive_path, self.path)
        extract_archive(archive_path, self.path, merge_single=True)
        os.remove(archive_path)
        return True

    def enable_dll(self, system_dir, arch, dll_path):
        """Copies dlls to the appropriate destination"""
        dll = os.path.basename(dll_path)
        if system.path_exists(dll_path):
            wine_dll_path = os.path.join(system_dir, dll)
            if system.path_exists(wine_dll_path):
                if not self.is_managed_dll(wine_dll_path) and not os.path.islink(wine_dll_path):
                    # Backing up original version (may not be needed)
                    shutil.move(wine_dll_path, wine_dll_path + ".orig")
                else:
                    os.remove(wine_dll_path)
            try:
                os.symlink(dll_path, wine_dll_path)
            except OSError:
                logger.error("Failed linking %s to %s", dll_path, wine_dll_path)
        else:
            self.disable_dll(system_dir, arch, dll)

    def disable_dll(self, system_dir, _arch, dll):  # pylint: disable=unused-argument
        """Remove DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
        if system.path_exists(wine_dll_path + ".orig"):
            if system.path_exists(wine_dll_path):
                os.remove(wine_dll_path)
            shutil.move(wine_dll_path + ".orig", wine_dll_path)

    def enable_user_file(self, user_dir, file_path, source_path):
        if system.path_exists(source_path):
            wine_file_path = os.path.join(user_dir, file_path)
            wine_file_dir = os.path.dirname(wine_file_path)
            if system.path_exists(wine_file_path):
                if not os.path.islink(wine_file_path):
                    # Backing up original version (may not be needed)
                    shutil.move(wine_file_path, wine_file_path + ".orig")
                else:
                    os.remove(wine_file_path)

            if not os.path.isdir(wine_file_dir):
                os.makedirs(wine_file_dir)

            try:
                os.symlink(source_path, wine_file_path)
            except OSError:
                logger.error("Failed linking %s to %s", source_path, wine_file_path)
        else:
            self.disable_user_file(user_dir, file_path)

    def disable_user_file(self, user_dir, file_path):
        wine_file_path = os.path.join(user_dir, file_path)
        # We only create a symlink; if it is a real file, it mus tbe user data.
        if system.path_exists(wine_file_path) and os.path.islink(wine_file_path):
            os.remove(wine_file_path)
            if system.path_exists(wine_file_path + ".orig"):
                shutil.move(wine_file_path + ".orig", wine_file_path)

    def _iter_dlls(self):
        windows_path = os.path.join(self.prefix, "drive_c/windows")
        if self.wine_arch == "win64":
            system_dirs = {
                self.archs[64]: os.path.join(windows_path, "system32"),
                self.archs[32]: os.path.join(windows_path, "syswow64"),
            }
        elif self.wine_arch == "win32":
            system_dirs = {self.archs[32]: os.path.join(windows_path, "system32")}

        for arch, system_dir in system_dirs.items():
            for dll in self.managed_dlls:
                yield system_dir, arch, dll

    def _iter_user_files(self):
        if self.managed_user_files:
            prefix_manager = WinePrefixManager(self.prefix)
            user_dir = prefix_manager.user_dir
            for file in self.managed_user_files:
                filename = os.path.basename(file)
                yield user_dir, file, filename

    def enable(self):
        """Enable Dlls for the current prefix"""
        if not self.is_available():
            if not self.download():
                logger.error("%s %s could not be enabled because it is not available locally",
                             self.component, self.version)
                return
        for system_dir, arch, dll in self._iter_dlls():
            dll_path = os.path.join(self.path, arch, "%s.dll" % dll)
            self.enable_dll(system_dir, arch, dll_path)
        for user_dir, file, filename in self._iter_user_files():
            source_path = os.path.join(self.path, filename)
            self.enable_user_file(user_dir, file, source_path)

    def disable(self):
        """Disable DLLs for the current prefix"""
        for system_dir, arch, dll in self._iter_dlls():
            self.disable_dll(system_dir, arch, dll)
        for user_dir, file, _filename in self._iter_user_files():
            self.disable_user_file(user_dir, file)

    def fetch_versions(self):
        """Get releases from GitHub"""
        if not os.path.isdir(self.base_dir):
            os.mkdir(self.base_dir)
        download_file(self.releases_url, self.versions_path, overwrite=True)

    def upgrade(self):
        self.fetch_versions()
        if not self.is_available():
            if self.version:
                logger.info("Downloading %s %s...", self.component, self.version)
                self.download()
            else:
                logger.warning("Unable to download %s because version information was not available.", self.component)
