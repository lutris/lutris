"""DXVK helper module"""
import os
import json
import time
import shutil
import urllib.request

from lutris.settings import RUNTIME_DIR, DATA_DIR
from lutris.util.log import logger
from lutris.util.extract import extract_archive
from lutris.util.downloader import Downloader
from lutris.util.system import path_exists


CACHE_MAX_AGE = 86400  # Re-download DXVK versions every day
DXVK_TAGS_URL = "https://api.github.com/repos/doitsujin/dxvk/tags"
DXVK_VERSIONS = [
    "0.90", "0.81", "0.80",
    "0.72", "0.71", "0.65",
    "0.64", "0.63", "0.62",
    "0.54", "0.53", "0.52",
    "0.42", "0.31", "0.21"
]
DXVK_LATEST, DXVK_PAST_RELEASES = DXVK_VERSIONS[0], DXVK_VERSIONS[1:]

def get_dxvk_versions():
    """Get DXVK versions from GitHub"""
    dxvk_path = os.path.join(RUNTIME_DIR, 'dxvk')
    if not os.path.isdir(dxvk_path):
        os.mkdir(dxvk_path)
    versions_path = os.path.join(dxvk_path, 'dxvk_versions.json')

    # Download tags if the versions_path does not exist or is more than a day old
    if (
            not os.path.exists(versions_path) or
            os.path.getmtime(versions_path) + CACHE_MAX_AGE < time.time()
    ):
        urllib.request.urlretrieve(DXVK_TAGS_URL, versions_path)

    with open(versions_path, "r") as dxvk_tags:
        dxvk_json = json.load(dxvk_tags)
        dxvk_versions = [x['name'].replace('v', '') for x in dxvk_json]

    return dxvk_versions

def init_dxvk_versions():
    try:
        DXVK_VERSIONS = get_dxvk_versions()
    except Exception as ex:  # pylint: disable= broad-except
        logger.error(ex)
    DXVK_LATEST, DXVK_PAST_RELEASES = DXVK_VERSIONS[0], DXVK_VERSIONS[1:]


class DXVKManager:
    """Utility class to install DXVK dlls to a Wine prefix"""
    base_url = "https://github.com/doitsujin/dxvk/releases/download/v{}/dxvk-{}.tar.gz"
    base_dir = os.path.join(RUNTIME_DIR, 'dxvk')
    dxvk_dlls = ('dxgi', 'd3d11', 'd3d10core', 'd3d10_1', 'd3d10')
    latest_version = DXVK_LATEST

    def __init__(self, prefix, arch='win64', version=None):
        self.prefix = prefix
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)
        self._version = version
        self.wine_arch = arch

    @property
    def version(self):
        """Return version of DXVK (latest known version if not provided)"""
        if self._version:
            return self._version
        return self.latest_version

    @property
    def dxvk_path(self):
        """Return path to DXVK local cache"""
        return os.path.join(self.base_dir, self.version)

    @staticmethod
    def is_dxvk_dll(dll_path):
        """Check if a given DLL path is provided by DXVK

        Very basic check to see if a dll exists and is over 256K. If this is the
        case, then consider the DLL to be from DXVK
        """
        if os.path.exists(dll_path):
            dll_stats = os.stat(dll_path)
            dll_size = dll_stats.st_size
        else:
            dll_size = 0
        return dll_size > 1024 * 256

    def is_available(self):
        """Return whether DXVK is cached locally"""
        return os.path.exists(self.dxvk_path)

    def download(self):
        """Download DXVK to the local cache"""
        # There's a glitch in one of the archive's names
        fixed_version = 'v0.40' if self.version == '0.40' else self.version
        dxvk_url = self.base_url.format(self.version, fixed_version)
        if self.is_available():
            logger.warning("DXVK already available at %s", self.dxvk_path)

        dxvk_archive_path = os.path.join(self.base_dir, os.path.basename(dxvk_url))
        downloader = Downloader(dxvk_url, dxvk_archive_path)
        downloader.start()
        while downloader.check_progress() < 1:
            time.sleep(1)
        if not os.path.exists(dxvk_archive_path):
            logger.error("DXVK %s not downloaded")
            return
        if os.stat(dxvk_archive_path).st_size:
            extract_archive(dxvk_archive_path, self.dxvk_path, merge_single=True)
        else:
            logger.error("%s is an empty file", self.dxvk_path)
        os.remove(dxvk_archive_path)

    def enable_dxvk_dll(self, system_dir, dxvk_arch, dll):
        """Copies DXVK dlls to the appropriate destination"""
        wine_dll_path = os.path.join(system_dir, '%s.dll' % dll)
        logger.info("Replacing %s/%s with DXVK version", system_dir, dll)
        if not self.is_dxvk_dll(wine_dll_path):
            # Backing up original version (may not be needed)
            if os.path.exists(wine_dll_path):
                shutil.move(wine_dll_path, wine_dll_path + ".orig")
        # Copying DXVK's version
        dxvk_dll_path = os.path.join(self.dxvk_path, dxvk_arch, "%s.dll" % dll)
        if os.path.exists(dxvk_dll_path):
            if path_exists(wine_dll_path):
                os.remove(wine_dll_path)
            os.symlink(dxvk_dll_path, wine_dll_path)

    def disable_dxvk_dll(self, system_dir, dxvk_arch, dll):
        """Remove DXVK DLL from Wine prefix"""
        wine_dll_path = os.path.join(system_dir, '%s.dll' % dll)
        if self.is_dxvk_dll(wine_dll_path):
            logger.info("Removing DXVK dll %s/%s", system_dir, dll)
            os.remove(wine_dll_path)
        # Restoring original version (may not be needed)
        if os.path.exists(wine_dll_path + '.orig'):
            shutil.move(wine_dll_path + '.orig', wine_dll_path)

    def _iter_dxvk_dlls(self):
        windows_path = os.path.join(self.prefix, 'drive_c/windows')
        if self.wine_arch == 'win64':
            system_dirs = {
                'x64': os.path.join(windows_path, 'system32'),
                'x32': os.path.join(windows_path, 'syswow64')
            }
        elif self.wine_arch == 'win32':
            system_dirs = {
                'x32': os.path.join(windows_path, 'system32'),
            }

        for dxvk_arch, system_dir in system_dirs.items():
            for dll in self.dxvk_dlls:
                yield system_dir, dxvk_arch, dll

    def enable(self):
        """Enable DXVK for the current prefix"""
        if not os.path.exists(self.dxvk_path):
            logger.error("DXVK %s is not available locally", self.version)
            return
        for system_dir, dxvk_arch, dll in self._iter_dxvk_dlls():
            self.enable_dxvk_dll(system_dir, dxvk_arch, dll)

    def disable(self):
        """Disable DXVK for the current prefix"""
        for system_dir, dxvk_arch, dll in self._iter_dxvk_dlls():
            self.disable_dxvk_dll(system_dir, dxvk_arch, dll)
