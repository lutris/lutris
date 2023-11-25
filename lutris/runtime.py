"""Runtime handling module"""
import concurrent.futures
import os
import time
from gettext import gettext as _
from typing import Any, Callable, Dict, List, Tuple

from gi.repository import GLib

from lutris import settings
from lutris.api import download_runtime_versions, get_time_from_api_date
from lutris.util import http, jobs, system, update_cache
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.vkd3d import VKD3DManager
from lutris.util.wine.wine import get_installed_wine_versions

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

    def __init__(self, name: str, updater: 'RuntimeUpdater') -> None:
        if not name:
            raise ValueError("Runtimes cannot be anonymous.")
        self.name = name
        self.updater = updater
        self.versioned = False  # Versioned runtimes keep 1 version per folder
        self.version = ""
        self.download_progress = 0.0

    @property
    def local_runtime_path(self) -> str:
        """Return the local path for the runtime folder"""
        return os.path.join(settings.RUNTIME_DIR, self.name)

    def get_updated_at(self) -> time.struct_time:
        """Return the modification date of the runtime folder"""
        return time.gmtime(os.path.getmtime(self.local_runtime_path))

    def set_updated_at(self) -> None:
        """Set the creation and modification time to now"""
        if not system.path_exists(self.local_runtime_path):
            logger.error("No local runtime path in %s", self.local_runtime_path)
            return
        os.utime(self.local_runtime_path)

    def should_update(self, remote_runtime_info: Dict[str, Any]) -> bool:
        """Determine if the current runtime should be updated"""
        if self.versioned:
            return not system.path_exists(os.path.join(settings.RUNTIME_DIR, self.name, self.version))

        try:
            local_updated_at = self.get_updated_at()
        except FileNotFoundError:
            return True

        remote_updated_at = get_time_from_api_date(remote_runtime_info["created_at"])

        if local_updated_at and local_updated_at >= remote_updated_at:
            return False

        logger.debug(
            "Runtime %s locally updated on %s, remote created on %s)",
            self.name,
            time.strftime("%c", local_updated_at),
            time.strftime("%c", remote_updated_at),
        )
        return True

    def should_update_component(self, filename: str, remote_modified_at: time.struct_time) -> bool:
        """Should an individual component be updated?"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, filename)
        if not system.path_exists(file_path):
            return True
        locally_modified_at = time.gmtime(os.path.getmtime(file_path))
        if locally_modified_at >= remote_modified_at:
            return False
        return True

    def get_downloader(self, remote_runtime_info: Dict[str, Any]) -> Downloader:
        """Return Downloader for this runtime"""
        url = remote_runtime_info["url"]
        self.versioned = remote_runtime_info["versioned"]
        if self.versioned:
            self.version = remote_runtime_info["version"]
        archive_path = os.path.join(settings.RUNTIME_DIR, os.path.basename(url))
        return Downloader(url, archive_path, overwrite=True)

    def download(self, remote_runtime_info: Dict[str, Any]) -> Downloader:
        """Downloads a runtime locally"""
        downloader = self.get_downloader(remote_runtime_info)
        downloader.start()
        GLib.timeout_add(100, self.check_download_progress, downloader)
        return downloader

    def download_component(self, component: Dict[str, Any]) -> None:
        """Download an individual file from a runtime item"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, component["filename"])
        http.download_file(component["url"], file_path)

    def get_runtime_components(self) -> List[Dict[str, Any]]:
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
                if not future.cancelled() and future.exception():
                    expected_filename = future_downloads[future]
                    logger.warning("Failed to get '%s': %s", expected_filename, future.exception())

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


class RuntimeUpdater:
    """Class handling the runtime updates"""

    UpdateFunction = Callable[[], None]

    def __init__(self, pci_ids: List[str] = None,
                 force: bool = False):
        self.force = force
        self.startup = True
        self.pci_ids: List[str] = pci_ids or []
        self.runtime_versions: Dict[str, Any] = {}
        self.update_functions: List[Tuple[str, RuntimeUpdater.UpdateFunction]] = []
        self.downloaders: Dict[Runtime, Downloader] = {}
        self.status_text = ""
        self.deferred_updates = 0

        if RUNTIME_DISABLED:
            logger.warning("Runtime disabled. Safety not guaranteed.")
        else:
            self.add_update("runtime", self._update_runtime, hours=12)
            self.add_update("runners", self._update_runners, hours=12)

    def add_update(self, key: str, update_function: UpdateFunction, hours: int) -> None:
        """__init__ calls this to register each update. This function
        only registers the update if it hasn't been tried in the last
        'hours' hours. This is tracked in 'updates.json', and identified
        by 'key' in that file."""
        last_call = update_cache.get_last_call(key)
        if self.force or not last_call or last_call > 3600 * hours:
            self.update_functions.append((key, update_function))

    @property
    def has_updates(self) -> bool:
        """Returns True if there are any updates to perform."""
        return len(self.update_functions) > 0

    def update_runtimes(self) -> None:
        """Performs all the registered updates."""
        self.runtime_versions = download_runtime_versions(self.pci_ids)
        for key, func in self.update_functions:
            func()
            update_cache.write_date_to_cache(key)

    def _update_runners(self) -> None:
        """Update installed runners (only works for Wine at the moment)"""
        upstream_runners = self.runtime_versions.get("runners", {})
        for name, upstream_runners in upstream_runners.items():
            if name != "wine":
                continue
            upstream_runner = None
            for _runner in upstream_runners:
                if _runner["architecture"] == LINUX_SYSTEM.arch:
                    upstream_runner = _runner

            if not upstream_runner:
                continue

            # This has the responsibility to update existing runners, not installing new ones
            runner_base_path = os.path.join(settings.RUNNER_DIR, name)
            if not system.path_exists(runner_base_path) or not os.listdir(runner_base_path):
                continue

            runner_version = "-".join([upstream_runner["version"], upstream_runner["architecture"]])

            archive_download_path = os.path.join(settings.TMP_DIR, os.path.basename(upstream_runner["url"]))
            version_path = os.path.join(settings.RUNNER_DIR, name, runner_version)
            staged_path = os.path.join(settings.STAGING_DIR, "runners", name, runner_version)

            if system.path_exists(version_path):
                if system.path_exists(staged_path):
                    system.remove_folder(staged_path)
                continue
            elif system.path_exists(staged_path):
                os.rename(staged_path, version_path)
                get_installed_wine_versions.cache_clear()
                continue

            if self.startup:
                self.deferred_updates += 1
                continue

            self.status_text = _("Updating %s") % name
            downloader = Downloader(upstream_runner["url"], archive_download_path)
            downloader.start()
            self.downloaders = {"wine": downloader}
            downloader.join()
            self.status_text = _("Extracting %s") % name
            extract_archive(archive_download_path, staged_path)
            os.remove(archive_download_path)

            get_installed_wine_versions.cache_clear()

    def percentage_completed(self) -> float:
        if not self.downloaders:
            return 0
        return sum(downloader.progress_fraction for downloader in self.downloaders.values()) / len(self.downloaders)

    def _update_runtime(self) -> None:
        """Launch the update process"""
        for name, remote_runtime in self.runtime_versions.get("runtimes", {}).items():
            if remote_runtime["architecture"] == "x86_64" and not LINUX_SYSTEM.is_64_bit:
                logger.debug("Skipping runtime %s for %s", name, remote_runtime["architecture"])
                continue

            try:
                runtime = Runtime(remote_runtime["name"], self)
                if runtime.should_update(remote_runtime):
                    self.status_text = _("Updating %s") % remote_runtime['name']
                    if remote_runtime["url"]:
                        downloader = runtime.download(remote_runtime)
                        self.downloaders[runtime] = downloader
                        downloader.join()
                    else:
                        runtime.download_components()
            except Exception as ex:
                logger.exception("Unable to download %s: %s", name, ex)


def get_env(version: str = None, prefer_system_libs: bool = False, wine_path: str = None) -> Dict[str, str]:
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


def get_winelib_paths(wine_path: str) -> List[str]:
    """Return wine libraries path for a Lutris wine build"""
    paths = []
    # Prioritize libwine.so.1 for lutris builds
    for winelib_path in ("lib", "lib64"):
        winelib_fullpath = os.path.join(wine_path or "", winelib_path)
        if system.path_exists(winelib_fullpath):
            paths.append(winelib_fullpath)
    return paths


def get_runtime_paths(version: str = None, prefer_system_libs: bool = True, wine_path: str = None) -> List[str]:
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


def get_paths(version: str = None, prefer_system_libs: bool = True, wine_path: str = None) -> List[str]:
    """Return a list of paths containing the runtime libraries."""
    if not RUNTIME_DISABLED:
        paths = get_runtime_paths(version=version, prefer_system_libs=prefer_system_libs, wine_path=wine_path)
    else:
        paths = []
    # Put existing LD_LIBRARY_PATH at the end
    if os.environ.get("LD_LIBRARY_PATH"):
        paths.append(os.environ["LD_LIBRARY_PATH"])
    return paths
