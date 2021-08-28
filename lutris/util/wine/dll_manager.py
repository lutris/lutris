"""Injects sets of DLLs into a prefix"""
import json
import os
import shutil
from gettext import gettext as _

from lutris.util import system
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger


class DLLManager:
    """Utility class to install dlls to a Wine prefix"""
    component = NotImplemented
    base_dir = NotImplemented
    managed_dlls = NotImplemented
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
            logger.warning("Loading of %s versions failed, defaulting to locally available versions", self.component)
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
        """Path to local folder containing DDLs"""
        return os.path.join(self.base_dir, self.version)

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
        with open(self.versions_path) as version_file:
            try:
                versions = [v["tag_name"] for v in json.load(version_file)]
            except KeyError:
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
        return system.path_exists(self.path)

    def dll_exists(self, dll_name):
        """Check if the dll is provided by the component
        The DLL might not be available for all archs so
        only check if one exists for the supported architectures
        """
        return any(
            [
                system.path_exists(os.path.join(self.path, arch, dll_name + ".dll"))
                for arch in self.archs.values()
            ]
        )

    def get_download_url(self):
        """Fetch the download URL from the JSON version file"""
        with open(self.versions_path) as version_file:
            releases = json.load(version_file)
        for release in releases:
            if release["tag_name"] != self.version:
                continue
            return release["assets"][0]["browser_download_url"]

    def download(self):
        """Download component to the local cache"""
        if self.is_available():
            logger.warning("%s already available at %s", self.component, self.path)

        url = self.get_download_url()
        if not url:
            logger.warning("Could not find a release for %s %s", self.component, self.version)
            return
        archive_path = os.path.join(self.base_dir, os.path.basename(url))
        download_file(url, archive_path, overwrite=True)
        if not system.path_exists(archive_path) or not os.stat(archive_path).st_size:
            logger.error("Failed to download %s %s", self.component, self.version)
            return
        extract_archive(archive_path, self.path, merge_single=True)
        os.remove(archive_path)

    def enable_dll(self, system_dir, arch, dll_path):
        """Copies dlls to the appropriate destination"""
        dll = os.path.basename(dll_path)
        if system.path_exists(dll_path):
            wine_dll_path = os.path.join(system_dir, dll)
            logger.debug("Replacing %s/%s with %s version", system_dir, dll, self.component)
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
                logger.debug("Removing %s dll %s/%s", self.component, system_dir, dll)
                os.remove(wine_dll_path)
            shutil.move(wine_dll_path + ".orig", wine_dll_path)

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

    def enable(self):
        """Enable Dlls for the current prefix"""
        if not system.path_exists(self.path):
            logger.error("%s %s is not available locally", self.component, self.version)
            return
        for system_dir, arch, dll in self._iter_dlls():
            dll_path = os.path.join(self.path, arch, "%s.dll" % dll)
            self.enable_dll(system_dir, arch, dll_path)

    def disable(self):
        """Disable DLLs for the current prefix"""
        for system_dir, arch, dll in self._iter_dlls():
            self.disable_dll(system_dir, arch, dll)

    def fetch_versions(self):
        """Get releases from GitHub"""
        if not os.path.isdir(self.base_dir):
            os.mkdir(self.base_dir)
        download_file(self.releases_url, self.versions_path, overwrite=True)

    def upgrade(self):
        self.fetch_versions()
        if not self.is_available():
            logger.info("Downloading %s %s...", self.component, self.version)
            self.download()
