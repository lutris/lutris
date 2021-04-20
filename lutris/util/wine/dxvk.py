"""DXVK helper module"""
import datetime
import json
import os
import shutil

from lutris.settings import RUNTIME_DIR
from lutris.util import system
from lutris.util.extract import extract_archive
from lutris.util.http import download_file
from lutris.util.log import logger

DXVK_RELEASES_URL = "https://api.github.com/repos/lutris/dxvk/releases"


def fetch_dxvk_versions():
    """Get DXVK versions from GitHub"""
    dxvk_path = os.path.join(RUNTIME_DIR, "dxvk")
    if not os.path.isdir(dxvk_path):
        os.mkdir(dxvk_path)
    versions_path = os.path.join(dxvk_path, "dxvk_versions.json")
    logger.info("Downloading DXVK releases to %s", versions_path)
    return download_file(DXVK_RELEASES_URL, versions_path, overwrite=True, max_age=datetime.timedelta(days=1))


class UnavailableDXVKVersion(RuntimeError):
    """Exception raised when a version of DXVK is not found"""


class DXVKManager:
    """Utility class to install DXVK dlls to a Wine prefix"""
    base_dir = os.path.join(RUNTIME_DIR, "dxvk")
    dxvk_dlls = ("dxgi", "d3d11", "d3d10core", "d3d9", "d3d12")

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
        self._versions = self.load_dxvk_versions()
        if not self._versions:
            logger.warning("Loading of DXVK versions failed, defaulting to locally available versions")
            self._versions = os.listdir(self.base_dir)
        return self._versions

    @property
    def version(self):
        """Return version of DXVK (latest known version if not provided)"""
        if self._version:
            return self._version
        if self.versions:
            return self.versions[0]

    @property
    def dxvk_path(self):
        """Return path to DXVK local cache"""
        return os.path.join(self.base_dir, self.version)

    def load_dxvk_versions(self):
        versions_path = os.path.join(self.base_dir, "dxvk_versions.json")
        if not system.path_exists(versions_path):
            return []
        with open(versions_path, "r") as dxvk_version_file:
            try:
                dxvk_versions = [v["tag_name"] for v in json.load(dxvk_version_file)]
            except KeyError:
                logger.warning(
                    "Invalid versions file %s, deleting so it is downloaded on next start.",
                    versions_path
                )
                os.remove(versions_path)
                return []
        return dxvk_versions

    @staticmethod
    def is_dxvk_dll(dll_path):
        """Check if a given DLL path is provided by DXVK

        Very basic check to see if a dll contains the string "dxvk".
        """
        try:
            with open(dll_path, 'rb') as file:
                prev_block_end = b''
                while True:
                    block = file.read(2 * 1024 * 1024)  # 2 MiB
                    if not block:
                        break
                    if b'dxvk' in prev_block_end + block[:4]:
                        return True
                    if b'dxvk' in block:
                        return True

                    prev_block_end = block[-4:]
        except OSError:
            pass
        return False

    def is_available(self):
        """Return whether DXVK is cached locally"""
        return system.path_exists(self.dxvk_path)

    def dxvk_dll_exists(self, dll_name):
        """Check if the dll exists as a DXVK variant"""
        return system.path_exists(os.path.join(self.dxvk_path, "x64", dll_name + ".dll")
                                  ) and system.path_exists(os.path.join(self.dxvk_path, "x32", dll_name + ".dll"))

    def get_dxvk_download_url(self):
        """Fetch the download URL for DXVK from the JSON version file"""
        versions_path = os.path.join(self.base_dir, "dxvk_versions.json")
        with open(versions_path, "r") as dxvk_version_file:
            dxvk_releases = json.load(dxvk_version_file)
        for release in dxvk_releases:
            if release["tag_name"] != self.version:
                continue
            return release["assets"][0]["browser_download_url"]

    def download(self):
        """Download DXVK to the local cache"""
        if self.is_available():
            logger.warning("DXVK already available at %s", self.dxvk_path)

        dxvk_url = self.get_dxvk_download_url()
        if not dxvk_url:
            logger.warning("Could not find a release for DXVK %s", self.version)
            return
        dxvk_archive_path = os.path.join(self.base_dir, os.path.basename(dxvk_url))
        download_file(dxvk_url, dxvk_archive_path, overwrite=True)
        if not system.path_exists(dxvk_archive_path) or not os.stat(dxvk_archive_path).st_size:
            logger.error("Failed to download DXVK %s", self.version)
            return
        extract_archive(dxvk_archive_path, self.dxvk_path, merge_single=True)
        os.remove(dxvk_archive_path)

    def enable_dxvk_dll(self, system_dir, dxvk_arch, dll):
        """Copies DXVK dlls to the appropriate destination"""
        # Copying DXVK's version
        dxvk_dll_path = os.path.join(self.dxvk_path, dxvk_arch, "%s.dll" % dll)
        if system.path_exists(dxvk_dll_path):
            wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
            logger.debug("Replacing %s/%s with DXVK version", system_dir, dll)
            if system.path_exists(wine_dll_path):
                if not self.is_dxvk_dll(wine_dll_path) and not os.path.islink(wine_dll_path):
                    # Backing up original version (may not be needed)
                    shutil.move(wine_dll_path, wine_dll_path + ".orig")
                else:
                    os.remove(wine_dll_path)
            try:
                os.symlink(dxvk_dll_path, wine_dll_path)
            except OSError:
                logger.error("Failed linking %s to %s", dxvk_dll_path, wine_dll_path)
        else:
            self.disable_dxvk_dll(system_dir, dxvk_arch, dll)

    def disable_dxvk_dll(self, system_dir, dxvk_arch, dll):  # pylint: disable=unused-argument
        """Remove DXVK DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, "%s.dll" % dll)
        if system.path_exists(wine_dll_path + ".orig"):
            if system.path_exists(wine_dll_path):
                logger.debug("Removing DXVK dll %s/%s", system_dir, dll)
                os.remove(wine_dll_path)
            shutil.move(wine_dll_path + ".orig", wine_dll_path)

    def _iter_dxvk_dlls(self):
        windows_path = os.path.join(self.prefix, "drive_c/windows")
        if self.wine_arch == "win64":
            system_dirs = {
                "x64": os.path.join(windows_path, "system32"),
                "x32": os.path.join(windows_path, "syswow64"),
            }
        elif self.wine_arch == "win32":
            system_dirs = {"x32": os.path.join(windows_path, "system32")}

        for dxvk_arch, system_dir in system_dirs.items():
            for dll in self.dxvk_dlls:
                yield system_dir, dxvk_arch, dll

    def enable(self):
        """Enable DXVK for the current prefix"""
        if not system.path_exists(self.dxvk_path):
            logger.error("DXVK %s is not available locally", self.version)
            return
        for system_dir, dxvk_arch, dll in self._iter_dxvk_dlls():
            self.enable_dxvk_dll(system_dir, dxvk_arch, dll)

    def disable(self):
        """Disable DXVK for the current prefix"""
        for system_dir, dxvk_arch, dll in self._iter_dxvk_dlls():
            self.disable_dxvk_dll(system_dir, dxvk_arch, dll)
