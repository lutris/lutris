"""Runtime handling module"""
import concurrent.futures
import os
import time
from gettext import gettext as _
from typing import Any, Callable, Dict, List, Tuple

from gi.repository import GLib

from lutris import settings
from lutris.api import download_runtime_versions, format_runner_version, get_time_from_api_date
from lutris.gui.widgets.progress_box import ProgressInfo
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


class ComponentUpdater:
    (
        PENDING,
        DOWNLOADING,
        EXTRACTING,
        COMPLETED
    ) = list(range(4))

    status_formats = {
        PENDING: _("Updating %s"),
        DOWNLOADING: _("Updating %s"),
        EXTRACTING: _("Extracting %s"),
        COMPLETED: _("Updating %s"),
    }

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def should_update(self) -> bool:
        return True

    def install_update(self, updater: 'RuntimeUpdater') -> None:
        raise NotImplementedError

    def get_progress(self) -> ProgressInfo:
        return ProgressInfo(None)


class RuntimeUpdater:
    """Class handling the runtime updates"""

    UpdaterFactory = Callable[[], List[ComponentUpdater]]

    def __init__(self, pci_ids: List[str] = None, force: bool = False):
        self.force = force
        self.pci_ids: List[str] = pci_ids or []
        self.runtime_versions: Dict[str, Any] = {}
        self.update_functions: List[Tuple[str, RuntimeUpdater.UpdaterFactory]] = []

        if RUNTIME_DISABLED:
            logger.warning("Runtime disabled. Safety not guaranteed.")
        else:
            self.add_update("runtime", self._get_runtime_updaters, hours=12)
            self.add_update("runners", self._get_runner_updaters, hours=12)

    def add_update(self, key: str, updater_factory: UpdaterFactory, hours: int) -> None:
        """__init__ calls this to register each update. This function
        only registers the update if it hasn't been tried in the last
        'hours' hours. This is tracked in 'updates.json', and identified
        by 'key' in that file."""
        last_call = update_cache.get_last_call(key)
        if self.force or not last_call or last_call > 3600 * hours:
            self.update_functions.append((key, updater_factory))

    @property
    def has_updates(self) -> bool:
        """Returns True if there are any updates to perform."""
        return bool(self.update_functions)

    def create_component_updaters(self) -> List[ComponentUpdater]:
        """Creates the component updaters that need to be applied and
        returns them in a list."""
        if not self.runtime_versions:
            self.runtime_versions = download_runtime_versions(self.pci_ids)

        updaters = []
        for key, func in self.update_functions:
            updaters += func()
            # Not ideal - we are marking this off as updated just before
            # the updater, not after it completes.
            update_cache.write_date_to_cache(key)
        return updaters

    def _get_runtime_updaters(self) -> List[ComponentUpdater]:
        """Launch the update process"""
        updaters: List[ComponentUpdater] = []
        for name, remote_runtime in self.runtime_versions.get("runtimes", {}).items():
            if remote_runtime["architecture"] == "x86_64" and not LINUX_SYSTEM.is_64_bit:
                logger.debug("Skipping runtime %s for %s", name, remote_runtime["architecture"])
                continue

            try:
                if remote_runtime.get("url"):
                    updaters.append(RuntimeExtractedComponentUpdater(remote_runtime))
                else:
                    updaters.append(RuntimeFilesComponentUpdater(remote_runtime))
            except Exception as ex:
                logger.exception("Unable to download %s: %s", name, ex)

        return updaters

    def _get_runner_updaters(self) -> List[ComponentUpdater]:
        """Update installed runners (only works for Wine at the moment)"""
        updaters: List[ComponentUpdater] = []
        upstream_runners = self.runtime_versions.get("runners", {})
        for name, upstream_runners in upstream_runners.items():
            if name != "wine":
                continue
            upstream_runner = None
            for _runner in upstream_runners:
                if _runner["architecture"] == LINUX_SYSTEM.arch:
                    upstream_runner = _runner

            if upstream_runner:
                updaters.append(RunnerComponentUpdater(name, upstream_runner))

        return updaters


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


class RuntimeComponentUpdater(ComponentUpdater):
    """A base class for component updates that use the timestamp from a runtime-info dict
    to decide when an update is required."""

    def __init__(self, remote_runtime_info: Dict[str, Any]) -> None:
        self.remote_runtime_info = remote_runtime_info
        self.state = ComponentUpdater.PENDING
        # Versioned runtimes keep 1 version per folder
        self.versioned = bool(self.remote_runtime_info.get("versioned"))
        self.version = str(self.remote_runtime_info.get("version") or "") if self.versioned else ""

    @property
    def name(self) -> str:
        return self.remote_runtime_info["name"]

    def install_update(self, updater: 'RuntimeUpdater') -> None:
        raise NotImplementedError

    def get_progress(self) -> ProgressInfo:
        status_text = ComponentUpdater.status_formats[self.state] % self.name

        if self.state == ComponentUpdater.COMPLETED:
            return ProgressInfo(1.0, status_text)

        if self.state == ComponentUpdater.PENDING:
            return ProgressInfo(0.0, status_text)

        return ProgressInfo(None, status_text)

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

    @property
    def should_update(self) -> bool:
        """Determine if the current runtime should be updated"""
        if self.versioned:
            return not system.path_exists(os.path.join(settings.RUNTIME_DIR, self.name, self.version))

        try:
            local_updated_at = self.get_updated_at()
        except FileNotFoundError:
            return True

        remote_updated_at = get_time_from_api_date(self.remote_runtime_info["created_at"])

        if local_updated_at and local_updated_at >= remote_updated_at:
            return False

        logger.debug(
            "Runtime %s locally updated on %s, remote created on %s)",
            self.name,
            time.strftime("%c", local_updated_at),
            time.strftime("%c", remote_updated_at),
        )
        return True


class RuntimeExtractedComponentUpdater(RuntimeComponentUpdater):
    """Component updater that downloads and extracts an archive."""

    def __init__(self, remote_runtime_info: Dict[str, Any]) -> None:
        super().__init__(remote_runtime_info)
        self.url = remote_runtime_info["url"]
        self.downloader: Downloader = None
        self.download_progress = 0.0

    def install_update(self, updater: RuntimeUpdater) -> None:
        self.state = ComponentUpdater.DOWNLOADING
        self.downloader = self.download()
        self.downloader.join()
        self.downloader = None

    def get_progress(self) -> ProgressInfo:
        progress_info = super().get_progress()

        if self.downloader:
            return ProgressInfo(self.downloader.progress_fraction, progress_info.label_markup, self.downloader.cancel)

        return progress_info

    def get_downloader(self) -> Downloader:
        """Return Downloader for this runtime"""
        archive_path = os.path.join(settings.RUNTIME_DIR, os.path.basename(self.url))
        return Downloader(self.url, archive_path, overwrite=True)

    def download(self) -> Downloader:
        """Downloads a runtime locally"""
        downloader = self.get_downloader()
        downloader.start()
        GLib.timeout_add(100, self.check_download_progress, downloader)
        return downloader

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
        self.state = ComponentUpdater.EXTRACTING
        jobs.AsyncCall(extract_archive, self.on_extracted, path, dest_path, merge_single=True)
        return False

    def on_extracted(self, result: tuple, error: Exception) -> bool:
        """Callback method when a runtime has extracted"""
        self.state = ComponentUpdater.COMPLETED
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


class RuntimeFilesComponentUpdater(RuntimeComponentUpdater):
    """Component updaters that downloads a set of files described by the server
    individually."""

    def install_update(self, updater: RuntimeUpdater) -> None:
        """Download a runtime item by individual components. Used for icons only at the moment"""
        self.state = ComponentUpdater.DOWNLOADING
        components = self._get_runtime_components()
        downloads = []
        for component in components:
            modified_at = get_time_from_api_date(component["modified_at"])
            if not self._should_update_component(component["filename"], modified_at):
                continue
            downloads.append(component)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_downloads = {
                executor.submit(self._download_component, component): component["filename"]
                for component in downloads
            }
            for future in concurrent.futures.as_completed(future_downloads):
                if not future.cancelled() and future.exception():
                    expected_filename = future_downloads[future]
                    logger.warning("Failed to get '%s': %s", expected_filename, future.exception())
        self.state = ComponentUpdater.COMPLETED

    def _should_update_component(self, filename: str, remote_modified_at: time.struct_time) -> bool:
        """Should an individual component be updated?"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, filename)
        if not system.path_exists(file_path):
            return True
        locally_modified_at = time.gmtime(os.path.getmtime(file_path))
        if locally_modified_at >= remote_modified_at:
            return False
        return True

    def _get_runtime_components(self) -> List[Dict[str, Any]]:
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

    def _download_component(self, component: Dict[str, Any]) -> None:
        """Download an individual file from a runtime item"""
        file_path = os.path.join(settings.RUNTIME_DIR, self.name, component["filename"])
        http.download_file(component["url"], file_path)


class RunnerComponentUpdater(ComponentUpdater):
    """Component updaters that downloads new versions of runners. These are download
    as archives and extracted into place."""

    def __init__(self, name: str, upstream_runner: Dict[str, Any]):
        self._name = name
        self.upstream_runner = upstream_runner
        self.runner_version = format_runner_version(upstream_runner)
        self.version_path = os.path.join(settings.RUNNER_DIR, name, self.runner_version)
        self.downloader: Downloader = None
        self.state = ComponentUpdater.PENDING

    @property
    def name(self) -> str:
        return self._name

    @property
    def should_update(self):
        # This has the responsibility to update existing runners, not installing new ones
        runner_base_path = os.path.join(settings.RUNNER_DIR, self.name)
        if not system.path_exists(runner_base_path) or not os.listdir(runner_base_path):
            return False

        if system.path_exists(self.version_path):
            return False

        return True

    def install_update(self, updater: 'RuntimeUpdater') -> None:
        url = self.upstream_runner["url"]
        archive_download_path = os.path.join(settings.TMP_DIR, os.path.basename(url))
        self.state = ComponentUpdater.DOWNLOADING
        self.downloader = Downloader(self.upstream_runner["url"], archive_download_path)
        self.downloader.start()
        self.downloader.join()
        if self.downloader.state == self.downloader.COMPLETED:
            self.downloader = None
            self.state = ComponentUpdater.EXTRACTING
            extract_archive(archive_download_path, self.version_path)
            get_installed_wine_versions.cache_clear()

        os.remove(archive_download_path)
        self.state = ComponentUpdater.COMPLETED

    def get_progress(self) -> ProgressInfo:
        status_text = ComponentUpdater.status_formats[self.state] % self.name
        d = self.downloader
        if d:
            return ProgressInfo(d.progress_fraction, status_text, d.cancel)

        if self.state == ComponentUpdater.EXTRACTING:
            return ProgressInfo(None, status_text)

        if self.state == ComponentUpdater.COMPLETED:
            return ProgressInfo(1.0, status_text)

        return ProgressInfo(0.0, status_text)
