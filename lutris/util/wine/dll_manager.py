"""Injects sets of DLLs into a prefix"""

import json
import os
import shutil
from gettext import gettext as _
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lutris import settings
from lutris.exceptions import MissingRuntimeComponentError
from lutris.util import system
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger
from lutris.util.strings import parse_version
from lutris.util.upstream import ReleaseSource
from lutris.util.wine.prefix import WinePrefixManager


class DLLManager:
    """Utility class to install dlls to a Wine prefix"""

    name = NotImplemented
    human_name = NotImplemented
    managed_dlls = NotImplemented
    managed_appdata_files = []  # most managers have none
    release_source: ReleaseSource
    archs = {32: "x32", 64: "x64"}
    proton_compatible = False  # Proton manages its own DLLs

    def __init__(self, prefix=None, arch="win64", version=None):
        self.prefix = prefix
        self._versions = []
        self._version = None if version is None else str(version)
        self.wine_arch = arch

    @property
    def base_dir(self):
        return os.path.join(settings.RUNTIME_DIR, self.name)

    @property
    def versions_path(self):
        return os.path.join(self.base_dir, f"{self.name}_versions.json")

    @property
    def versions(self):
        """Return available versions"""
        self._versions = self.load_versions()
        if system.path_exists(self.base_dir):
            for local_version in os.listdir(self.base_dir):
                if os.path.isdir(os.path.join(self.base_dir, local_version)) and local_version not in self._versions:
                    self._versions.append(local_version)
        return self._versions

    @property
    def version(self):
        """Return version (latest known version if not provided)"""
        if self._version:
            return self._version
        versions = self.versions
        if versions:

            def get_preference_key(v):
                return not self.is_compatible_version(v), not self.is_recommended_version(v)

            # Put the compatible versions first, and the recommended ones before unrecommended ones.
            sorted_versions = sorted(versions, key=get_preference_key)
            return sorted_versions[0]

    def is_recommended_version(self, version):
        """True if the version given should be usable as the default; false if it
        should not be the default, but may be selected by the user. If only
        non-recommended versions exist, we'll still default to one of them, however."""
        return True

    def is_compatible_version(self, version):
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
    def path(self):
        """Path to local folder containing DLLs"""
        version = self.version
        if not version:
            raise MissingRuntimeComponentError(
                _(
                    "The '%s' runtime component is not installed; "
                    "visit the Updates tab in the Preferences dialog to install it."
                )
                % self.human_name,
                component_name=self.name,
            )
        return os.path.join(self.base_dir, version)

    @property
    def version_choices(self):
        _choices = [
            (_("Manual"), "manual"),
        ]
        for version in self.versions:
            _choices.append((version, version))
        return _choices

    def _load_releases(self) -> list[dict[str, Any]]:
        try:
            with open(self.versions_path, encoding="utf-8") as version_file:
                data = json.load(version_file)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as ex:
            logger.warning("Invalid release information in %s: %s", self.versions_path, ex)
            return []
        return [release for release in data if not (release.get("draft") or release.get("prerelease"))]

    def load_versions(self) -> list[str]:
        return [
            build.version
            for release in self._load_releases()
            if (build := self.release_source.build_for_release(release))
        ]

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
        return any(system.path_exists(os.path.join(self.path, arch, dll_name + ".dll")) for arch in self.archs.values())

    def get_download_url(self) -> str | None:
        version = self.version
        for release in self._load_releases():
            if release.get("tag_name") == version and (build := self.release_source.build_for_release(release)):
                return build.url
        return None

    def prepare_download(self, staged: Path) -> None:
        """Prepare the DLL layout before publishing the extracted release."""

    def download(self):
        """Download component to the local cache; returns True if successful but False
        if the component could not be downloaded."""
        if self.is_available():
            logger.warning("%s already available at %s", self.human_name, self.path)

        if not self._load_releases():
            self.fetch_versions()

        url = self.get_download_url()
        if not url:
            logger.warning("Could not find a release for %s %s", self.human_name, self.version)
            return False
        with TemporaryDirectory(dir=self.base_dir) as temp:
            archive_path = os.path.join(temp, os.path.basename(url))
            logger.info("Downloading %s %s from %s", self.human_name, self.version, url)
            download_file(url, archive_path)
            if not system.path_exists(archive_path, exclude_empty=True):
                logger.error("Failed to download %s %s", self.human_name, self.version)
                return False
            staged = Path(temp) / "release"
            extract_archive(archive_path, str(staged))
            self.prepare_download(staged)
            shutil.copytree(staged, self.path, dirs_exist_ok=True)
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
            system.create_symlink(dll_path, wine_dll_path)
        else:
            self.disable_dll(system_dir, arch, dll)

    def disable_dll(self, system_dir, _arch, dll):  # pylint: disable=unused-argument
        """Remove DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
        if system.path_exists(wine_dll_path + ".orig"):
            if system.path_exists(wine_dll_path):
                os.remove(wine_dll_path)
            shutil.move(wine_dll_path + ".orig", wine_dll_path)

    def enable_user_file(self, appdata_dir, file_path, source_path):
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

    def disable_user_file(self, appdata_dir, file_path):
        wine_file_path = os.path.join(appdata_dir, file_path)
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

    def _iter_appdata_files(self):
        if self.managed_appdata_files:
            prefix_manager = WinePrefixManager(self.prefix)
            appdata_dir = prefix_manager.appdata_dir
            for file in self.managed_appdata_files:
                filename = os.path.basename(file)
                yield appdata_dir, file, filename

    def setup(self, enable):
        """Enable or disable DLLs"""

        # manual version only sets the dlls to native (in get_enabling_dll_overrides())
        manager_version = self.version
        if not manager_version or manager_version.lower() != "manual":
            if enable:
                self.enable()
            else:
                self.disable()

    def get_enabling_dll_overrides(self):
        """Returns aa dll-override dict for the dlls in this manager; these options will
        enable the manager's dll, so call this only for enabled managers."""
        overrides = {}

        for dll in self.managed_dlls:
            # We have to make sure that the dll exists before setting it to native
            if self.dll_exists(dll):
                overrides[dll] = "n"

        return overrides

    def can_enable(self):
        return True

    def enable(self):
        """Enable Dlls for the current prefix"""
        if not self.is_available():
            if not self.download():
                logger.error(
                    "%s %s could not be enabled because it is not available locally", self.human_name, self.version
                )
                return
        for system_dir, arch, dll in self._iter_dlls():
            dll_path = os.path.join(self.path, arch, "%s.dll" % dll)
            self.enable_dll(system_dir, arch, dll_path)
        for appdata_dir, file, filename in self._iter_appdata_files():
            source_path = os.path.join(self.path, filename)
            self.enable_user_file(appdata_dir, file, source_path)

    def disable(self):
        """Disable DLLs for the current prefix"""
        for system_dir, arch, dll in self._iter_dlls():
            self.disable_dll(system_dir, arch, dll)
        for appdata_dir, file, _filename in self._iter_appdata_files():
            self.disable_user_file(appdata_dir, file)

    def fetch_versions(self):
        """Get releases from GitHub"""
        os.makedirs(self.base_dir, exist_ok=True)
        with TemporaryDirectory(dir=self.base_dir) as temp:
            metadata = Path(temp) / "releases.json"
            if download_file(self.release_source.api_url, str(metadata)) and metadata.is_file():
                metadata.replace(self.versions_path)

    def upgrade(self):
        if not self.is_available():
            versions = self.load_versions()

            if not versions:
                logger.warning("Unable to download %s because version information was not available.", self.human_name)

            # We prefer recommended versions, so download those first.
            versions.sort(key=self.is_recommended_version, reverse=True)

            for version in versions:
                logger.info("Downloading %s %s...", self.human_name, version)
                self.download()

                if self.is_compatible_version(version):
                    return  # got a compatible version, that'll do.

                logger.warning(
                    "Version %s of %s is not compatible with this version of Lutris.", version, self.human_name
                )

            # We found nothing compatible, and downloaded everything, we just give up.
