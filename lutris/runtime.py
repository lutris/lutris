"""Runtime handling module"""
import concurrent.futures
import os
import time

from gi.repository import GLib

from lutris import settings
from lutris.api import get_time_from_api_date
from lutris.util import http, jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.vkd3d import VKD3DManager

RUNTIME_DISABLED = os.environ.get("LUTRIS_RUNTIME", "").lower() in ("0", "off")
DEFAULT_RUNTIME = "Ubuntu-18.04"

DLL_MANAGERS = {
    "dxvk": DXVKManager,
    "vkd3d": VKD3DManager,
    "d3d_extras": D3DExtrasManager,
    "dgvoodoo2": dgvoodoo2Manager,
    "dxvk_nvapi": DXVKNVAPIManager,
}


class Runtime:

    """Class for manipulating runtime folders"""

    def __init__(self, name: str, updater) -> None:
        self.name: str = name
        self.updater = updater
        self.versioned: bool = False  # Versioned runtimes keep 1 version per folder
        self.version: str = ""
        self.download_progress: float = 0

    @property
    def local_runtime_path(self):
        """Return the local path for the runtime folder"""
        if not self.name:
            return None
        return os.path.join(settings.RUNTIME_DIR, self.name)

    def get_updated_at(self):
        """Return the modification date of the runtime folder"""
        if not system.path_exists(self.local_runtime_path):
            return None
        return time.gmtime(os.path.getmtime(self.local_runtime_path))

    def set_updated_at(self):
        """Set the creation and modification time to now"""
        if not system.path_exists(self.local_runtime_path):
            logger.error("No local runtime path in %s", self.local_runtime_path)
            return
        os.utime(self.local_runtime_path)

    def should_update(self, remote_updated_at):
        """Determine if the current runtime should be updated"""
        if self.versioned:
            return not system.path_exists(os.path.join(settings.RUNTIME_DIR, self.name, self.version))

        local_updated_at = self.get_updated_at()
        if not local_updated_at:
            logger.debug("Runtime %s is not available locally", self.name)
            return True

        if local_updated_at and local_updated_at >= remote_updated_at:
            return False

        logger.debug(
            "Runtime %s locally updated on %s, remote created on %s)",
            self.name,
            time.strftime("%c", local_updated_at),
            time.strftime("%c", remote_updated_at),
        )
        return True

    def should_update_component(self, filename, remote_modified_at):
        """Should an individual component be updated?"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, filename)
        if not system.path_exists(file_path):
            return True
        locally_modified_at = time.gmtime(os.path.getmtime(file_path))
        if locally_modified_at >= remote_modified_at:
            return False
        return True

    def get_downloader(self, remote_runtime_info: dict) -> Downloader:
        """Return Downloader for this runtime"""
        url = remote_runtime_info["url"]
        self.versioned = remote_runtime_info["versioned"]
        if self.versioned:
            self.version = remote_runtime_info["version"]
        archive_path = os.path.join(settings.RUNTIME_DIR, os.path.basename(url))
        return Downloader(url, archive_path, overwrite=True)

    def download(self, remote_runtime_info: dict):
        """Downloads a runtime locally"""
        remote_updated_at = get_time_from_api_date(remote_runtime_info["created_at"])
        if not self.should_update(remote_updated_at):
            return None
        downloader = self.get_downloader(remote_runtime_info)
        downloader.start()
        GLib.timeout_add(100, self.check_download_progress, downloader)
        return downloader

    def download_component(self, component):
        """Download an individual file from a runtime item"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, component["filename"])
        try:
            http.download_file(component["url"], file_path)
        except http.HTTPError as ex:
            logger.error("Failed to download runtime component %s: %s", component, ex)
            return
        return file_path

    def get_runtime_components(self) -> list:
        """Fetch individual runtime files for a component"""
        request = http.Request(settings.RUNTIME_URL + "/" + self.name)
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Failed to get components: %s", ex)
            return []
        if not response.json:
            return []
        return response.json.get("components", [])

    def download_components(self) -> None:
        """Download a runtime item by individual components. Used for icons only at the moment"""
        components = self.get_runtime_components()
        downloads = []
        for component in components:
            modified_at = get_time_from_api_date(component["modified_at"])
            if not self.should_update_component(component["filename"], modified_at):
                continue
            downloads.append(component)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_downloads = {
                executor.submit(self.download_component, component): component["filename"]
                for component in downloads
            }
            for future in concurrent.futures.as_completed(future_downloads):
                filename = future_downloads[future]
                if not filename:
                    logger.warning("Failed to get %s", future)

    def check_download_progress(self, downloader: Downloader):
        """Call download.check_progress(), return True if download finished."""
        if downloader.state == downloader.ERROR:
            logger.error("Runtime update failed")
            return False
        self.download_progress = downloader.check_progress()
        if downloader.state == downloader.COMPLETED:
            self.on_downloaded(downloader.dest)
            return False
        return True

    def on_downloaded(self, path: str) -> bool:
        """Actions taken once a runtime is downloaded

        Arguments:
            path: local path to the runtime archive, or None on download failure
        """
        if not path:
            return False

        stats = os.stat(path)
        if not stats.st_size:
            logger.error("Download failed: file %s is empty, Deleting file.", path)
            os.unlink(path)
            return False
        directory, _filename = os.path.split(path)

        dest_path = os.path.join(directory, self.name)
        if self.versioned:
            dest_path = os.path.join(dest_path, self.version)
        else:
            # Delete the existing runtime path
            system.remove_folder(dest_path)
        # Extract the runtime archive
        jobs.AsyncCall(extract_archive, self.on_extracted, path, dest_path, merge_single=True)
        return False

    def on_extracted(self, result: tuple, error: Exception) -> bool:
        """Callback method when a runtime has extracted"""
        if error:
            logger.error("Runtime update failed: %s", error)
            return False
        archive_path, _destination_path = result
        os.unlink(archive_path)
        self.set_updated_at()
        if self.name in DLL_MANAGERS:
            manager = DLL_MANAGERS[self.name]()
            manager.fetch_versions()
        return False


def get_env(version: str = None, prefer_system_libs: bool = False, wine_path: str = None) -> dict:
    """Return a dict containing LD_LIBRARY_PATH env var

    Params:
        version: Version of the runtime to use, such as "Ubuntu-18.04" or "legacy"
        prefer_system_libs: Whether to prioritize system libs over runtime libs
        wine_path: If you prioritize system libs, provide the path for a lutris wine build
                         if one is being used. This allows Lutris to prioritize the wine libs
                         over everything else.
    """
    library_path = ":".join(get_paths(version=version, prefer_system_libs=prefer_system_libs, wine_path=wine_path))
    env = {}
    if library_path:
        env["LD_LIBRARY_PATH"] = library_path
        network_tools_path = os.path.join(settings.RUNTIME_DIR, "network-tools")
        env["PATH"] = "%s:%s" % (network_tools_path, os.environ["PATH"])
    return env


def get_winelib_paths(wine_path):
    """Return wine libraries path for a Lutris wine build"""
    paths = []
    # Prioritize libwine.so.1 for lutris builds
    for winelib_path in ("lib", "lib64"):
        winelib_fullpath = os.path.join(wine_path or "", winelib_path)
        if system.path_exists(winelib_fullpath):
            paths.append(winelib_fullpath)
    return paths


def get_runtime_paths(version=None, prefer_system_libs=True, wine_path=None):
    """Return Lutris runtime paths"""
    version = version or DEFAULT_RUNTIME
    lutris_runtime_path = "%s-i686" % version
    runtime_paths = [
        lutris_runtime_path,
        "steam/i386/lib/i386-linux-gnu",
        "steam/i386/lib",
        "steam/i386/usr/lib/i386-linux-gnu",
        "steam/i386/usr/lib",
    ]

    if LINUX_SYSTEM.is_64_bit:
        lutris_runtime_path = "%s-x86_64" % version
        runtime_paths += [
            lutris_runtime_path,
            "steam/amd64/lib/x86_64-linux-gnu",
            "steam/amd64/lib",
            "steam/amd64/usr/lib/x86_64-linux-gnu",
            "steam/amd64/usr/lib",
        ]

    paths = []
    if prefer_system_libs:
        if wine_path:
            paths += get_winelib_paths(wine_path)
        paths += list(LINUX_SYSTEM.iter_lib_folders())
    # Then resolve absolute paths for the runtime
    paths += [os.path.join(settings.RUNTIME_DIR, path) for path in runtime_paths]
    return paths


def get_paths(version=None, prefer_system_libs=True, wine_path=None):
    """Return a list of paths containing the runtime libraries."""
    if not RUNTIME_DISABLED:
        paths = get_runtime_paths(version=version, prefer_system_libs=prefer_system_libs, wine_path=wine_path)
    else:
        paths = []
    # Put existing LD_LIBRARY_PATH at the end
    if os.environ.get("LD_LIBRARY_PATH"):
        paths.append(os.environ["LD_LIBRARY_PATH"])
    return paths
