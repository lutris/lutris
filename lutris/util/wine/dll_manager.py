"""Injects sets of DLLs into a prefix"""
import json
import os
import shutil
from gettext import gettext as _
from typing import Generator, List, Optional, Tuple

from lutris import settings
from lutris.util import system
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger
from lutris.util.strings import parse_version
from lutris.util.wine.prefix import WinePrefixManager


class DLLManager:
    """Utility class to install dlls to a Wine prefix"""

    component = NotImplemented
    base_dir = NotImplemented
    managed_dlls = NotImplemented
    managed_appdata_files = []  # most managers have none
    versions_path = NotImplemented
    releases_url = NotImplemented
    archs = {32: "x32", 64: "x64"}

    # TODO MYPY - prefix is Optional[str] but it is used as a str
    def __init__(self, prefix=None, arch: str = "win64", version: Optional[str] = None):
        self.prefix = prefix
        self._versions = []
        self._version = version
        self.wine_arch = arch

    @property
    def versions(self) -> List[str]:
        """Return available versions"""
        self._versions = self.load_versions()
        if system.path_exists(self.base_dir):
            for local_version in os.listdir(self.base_dir):
                if os.path.isdir(os.path.join(self.base_dir, local_version)) and local_version not in self._versions:
                    self._versions.append(local_version)
        return self._versions

    # TODO MYPY - version returns Optional[str] but it is used as a str
    @property
    def version(self):
        """Return version (latest known version if not provided)"""
        if self._version:
            return self._version
        versions = self.versions
        if versions:

            def get_preference_key(v: str) -> Tuple[bool, bool]:
                return not self.is_compatible_version(v), not self.is_recommended_version(v)

            # Put the compatible versions first, and the recommended ones before unrecommended ones.
            sorted_versions = sorted(versions, key=get_preference_key)
            return sorted_versions[0]

    def is_recommended_version(self, version: str) -> bool:
        """True if the version given should be usable as the default; false if it
        should not be the default, but may be selected by the user. If only
        non-recommended versions exist, we'll still default to one of them, however."""
        return True

    def is_compatible_version(self, version: str) -> bool:
        """True if the version of the component is compatible with this Lutris. We can tell only
        once it is downloaded; if not this is always True.

        This checks the file 'lutris.json', which may contain the lowest version of Lutris
        the component version will work with. If this setting is absent, it is assumed compatible."""
        dir_settings = settings.get_lutris_directory_settings(self.base_dir)

        try:
            if "min_lutris_version" in dir_settings:
                min_lutris_version = parse_version(dir_settings["min_lutris_version"])
                current_lutris_version = parse_version(settings.VERSION)
                if current_lutris_version < min_lutris_version:
                    return False
        except TypeError as ex:
            logger.exception("Invalid lutris.json: %s", ex)
            return False

        return True

    @property
    def path(self) -> str:
        """Path to local folder containing DLLs"""
        version = self.version
        if not version:
            raise RuntimeError(
                "No path can be generated for %s because no version information is available." % self.component
            )
        return os.path.join(self.base_dir, version)

    @property
    def version_choices(self) -> List[Tuple[str, str]]:
        _choices = [
            (_("Manual"), "manual"),
        ]
        for version in self.versions:
            _choices.append((version, version))
        return _choices

    def load_versions(self) -> list:
        if not system.path_exists(self.versions_path):
            return []
        with open(self.versions_path, "r", encoding="utf-8") as version_file:
            try:
                versions = [v["tag_name"] for v in json.load(version_file)]
            except (KeyError, json.decoder.JSONDecodeError):
                logger.warning(
                    "Invalid versions file %s, deleting so it is downloaded on next start.", self.versions_path
                )
                os.remove(self.versions_path)
                return []
        return versions

    @staticmethod
    def is_managed_dll(dll_path: str) -> bool:
        """Check if a given DLL path is provided by the component"""
        return False

    def is_available(self) -> bool:
        """Return whether component is cached locally"""
        return self.version and system.path_exists(self.path)

    def dll_exists(self, dll_name: str) -> bool:
        """Check if the dll is provided by the component
        The DLL might not be available for all architectures so
        only check if one exists for the supported ones
        """
        return any(system.path_exists(os.path.join(self.path, arch, dll_name + ".dll")) for arch in self.archs.values())

    def get_download_url(self) -> Optional[str]:
        """Fetch the download URL from the JSON version file"""
        with open(self.versions_path, "r", encoding="utf-8") as version_file:
            releases = json.load(version_file)
        for release in releases:
            if release["tag_name"] != self.version:
                continue
            return release["assets"][0]["browser_download_url"]
        return None

    def download(self) -> bool:
        """Download component to the local cache; returns True if successful but False
        if the component could not be downloaded."""
        if self.is_available():
            logger.warning("%s already available at %s", self.component, self.path)

        if not system.path_exists(self.versions_path):
            self.fetch_versions()

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

    def enable_dll(self, system_dir: str, arch: str, dll_path: str) -> None:
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
            system.create_symlink(dll_path, wine_dll_path)
        else:
            self.disable_dll(system_dir, arch, dll)

    def disable_dll(self, system_dir: str, _arch: str, dll: str) -> None:  # pylint: disable=unused-argument
        """Remove DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
        if system.path_exists(wine_dll_path + ".orig"):
            if system.path_exists(wine_dll_path):
                os.remove(wine_dll_path)
            shutil.move(wine_dll_path + ".orig", wine_dll_path)

    def enable_user_file(self, appdata_dir: str, file_path: str, source_path: str) -> None:
        if system.path_exists(source_path):
            wine_file_path = os.path.join(appdata_dir, file_path)
            wine_file_dir = os.path.dirname(wine_file_path)
            if system.path_exists(wine_file_path):
                if not os.path.islink(wine_file_path):
                    # Backing up original version (may not be needed)
                    shutil.move(wine_file_path, wine_file_path + ".orig")
                else:
                    os.remove(wine_file_path)

            if not os.path.isdir(wine_file_dir):
                os.makedirs(wine_file_dir)
            system.create_symlink(source_path, wine_file_path)
        else:
            self.disable_user_file(appdata_dir, file_path)

    def disable_user_file(self, appdata_dir: str, file_path: str) -> None:
        wine_file_path = os.path.join(appdata_dir, file_path)
        # We only create a symlink; if it is a real file, it mus tbe user data.
        if system.path_exists(wine_file_path) and os.path.islink(wine_file_path):
            os.remove(wine_file_path)
            if system.path_exists(wine_file_path + ".orig"):
                shutil.move(wine_file_path + ".orig", wine_file_path)

    def _iter_dlls(self) -> Generator[Tuple[str, str, str], None, None]:
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

    def _iter_appdata_files(self) -> Generator[Tuple[str, str, str], None, None]:
        if self.managed_appdata_files:
            prefix_manager = WinePrefixManager(self.prefix)
            appdata_dir = prefix_manager.appdata_dir
            for file in self.managed_appdata_files:
                filename = os.path.basename(file)
                yield appdata_dir, file, filename

    def setup(self, enable: bool) -> None:
        """Enable or disable DLLs"""

        # manual version only sets the dlls to native (in get_enabling_dll_overrides())
        manager_version = self.version
        if not manager_version or manager_version.lower() != "manual":
            if enable:
                self.enable()
            else:
                self.disable()

    def get_enabling_dll_overrides(self) -> dict:
        """Returns aa dll-override dict for the dlls in this manager; these options will
        enable the manager's dll, so call this only for enabled managers."""
        overrides = {}

        for dll in self.managed_dlls:
            # We have to make sure that the dll exists before setting it to native
            if self.dll_exists(dll):
                overrides[dll] = "n"

        return overrides

    def can_enable(self) -> bool:
        return True

    def enable(self) -> None:
        """Enable Dlls for the current prefix"""
        if not self.is_available():
            if not self.download():
                logger.error(
                    "%s %s could not be enabled because it is not available locally", self.component, self.version
                )
                return
        for system_dir, arch, dll in self._iter_dlls():
            dll_path = os.path.join(self.path, arch, "%s.dll" % dll)
            self.enable_dll(system_dir, arch, dll_path)
        for appdata_dir, file, filename in self._iter_appdata_files():
            source_path = os.path.join(self.path, filename)
            self.enable_user_file(appdata_dir, file, source_path)

    def disable(self) -> None:
        """Disable DLLs for the current prefix"""
        for system_dir, arch, dll in self._iter_dlls():
            self.disable_dll(system_dir, arch, dll)
        for appdata_dir, file, _filename in self._iter_appdata_files():
            self.disable_user_file(appdata_dir, file)

    def fetch_versions(self) -> None:
        """Get releases from GitHub"""
        if not os.path.isdir(self.base_dir):
            os.mkdir(self.base_dir)
        download_file(self.releases_url, self.versions_path, overwrite=True)

    def upgrade(self) -> None:
        if not self.is_available():
            versions = self.load_versions()

            if not versions:
                logger.warning("Unable to download %s because version information was not available.", self.component)

            # We prefer recommended versions, so download those first.
            versions.sort(key=self.is_recommended_version, reverse=True)

            for version in versions:
                logger.info("Downloading %s %s...", self.component, version)
                self.download()

                if self.is_compatible_version(version):
                    return  # got a compatible version, that'll do.

                logger.warning(
                    "Version %s of %s is not compatible with this version of Lutris.", version, self.component
                )

            # We found nothing compatible, and downloaded everything, we just give up.
