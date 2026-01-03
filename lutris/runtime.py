"""Runtime handling module"""

import concurrent.futures
import os
import threading
import time
from gettext import gettext as _
from typing import Any, Dict, List, Optional

from lutris import settings
from lutris.api import (
    check_stale_runtime_versions,
    download_runtime_versions,
    get_runtime_versions,
    get_time_from_api_date,
)
from lutris.gui.widgets.progress_box import ProgressInfo
from lutris.util import http, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.jobs import AsyncCall
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.strings import parse_version
from lutris.util.wine.d3d_extras import D3DExtrasManager
from lutris.util.wine.dgvoodoo2 import dgvoodoo2Manager
from lutris.util.wine.dxvk import DXVKManager
from lutris.util.wine.dxvk_nvapi import DXVKNVAPIManager
from lutris.util.wine.vkd3d import VKD3DManager

RUNTIME_DISABLED = os.environ.get("LUTRIS_RUNTIME", "").casefold() in ("0", "off")
DEFAULT_RUNTIME = "Ubuntu-18.04"

DLL_MANAGERS = {
    "dxvk": DXVKManager,
    "vkd3d": VKD3DManager,
    "d3d_extras": D3DExtrasManager,
    "dgvoodoo2": dgvoodoo2Manager,
    "dxvk_nvapi": DXVKNVAPIManager,
}


def get_env(
    version: Optional[str] = None, prefer_system_libs: bool = False, wine_path: Optional[str] = None
) -> Dict[str, str]:
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


def get_runtime_paths(
    version: Optional[str] = None, prefer_system_libs: bool = True, wine_path: Optional[str] = None
) -> List[str]:
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


def get_paths(
    version: Optional[str] = None, prefer_system_libs: bool = True, wine_path: Optional[str] = None
) -> List[str]:
    """Return a list of paths containing the runtime libraries."""
    if not RUNTIME_DISABLED:
        paths = get_runtime_paths(version=version, prefer_system_libs=prefer_system_libs, wine_path=wine_path)
    else:
        paths = []
    # Put existing LD_LIBRARY_PATH at the end
    if os.environ.get("LD_LIBRARY_PATH"):
        paths.append(os.environ["LD_LIBRARY_PATH"])
    return paths


class ComponentUpdater:
    (PENDING, DOWNLOADING, EXTRACTING, COMPLETED) = list(range(4))

    status_formats = {
        PENDING: _("Updating %s"),
        DOWNLOADING: _("Downloading %s"),
        EXTRACTING: _("Extracting %s"),
        COMPLETED: _("Updated %s"),
    }

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def should_update(self) -> bool:
        """True if this update should be installed; false to discard it."""
        return True

    def install_update(self, updater: "RuntimeUpdater") -> None:
        """Performs the update; runs on a worker thread, and returns when complete.
        However, some updates spawn a further thread to extract in parallel with the
        next update even after this."""
        raise NotImplementedError

    def join(self):
        """Blocks until the update is entirely complete; used when install_update() spawns
        a thread to finish up. We call this on each update before closing the download queue."""

    def get_progress(self) -> ProgressInfo:
        """Returns the current progress for the updater as it runs; called from the main thread."""
        return ProgressInfo.ended()


class RuntimeUpdater:
    """Class handling the runtime updates"""

    def __init__(self, force: bool = False):
        if RUNTIME_DISABLED:
            logger.warning("Runtime disabled by environment variable. Re-enable runtime before submitting issues.")
            self.update_runtime = False
        elif force:
            self.update_runtime = True
        else:
            self.update_runtime = settings.read_bool_setting("auto_update_runtime", default=True)

            if not self.update_runtime:
                logger.warning("Runtime updates are disabled. This configuration is not supported.")

            if not check_stale_runtime_versions():
                self.update_runtime = False

        if self.has_updates:
            self.runtime_versions = download_runtime_versions()
        else:
            self.runtime_versions = get_runtime_versions()

    @property
    def has_updates(self):
        return self.update_runtime

    def create_component_updaters(self) -> List[ComponentUpdater]:
        """Creates the component updaters that need to be applied and returns them in a list.

        This tests each to see if it should be used and returns only those you should install.
        It returns an empty list if has_updates is false.

        This method also downloads fresh runner versions on each call, so we call this on a
        worker thread, instead of blocking the UI."""
        if not self.runtime_versions:
            return []

        updaters: List[ComponentUpdater] = []

        if self.update_runtime:
            updaters += self._get_runtime_updaters(self.runtime_versions)

        return [u for u in updaters if u.should_update]

    def check_client_versions(self) -> Optional[str]:
        """Checks if the client is of an old version and no longer supported; this can be blocked
        with an env-var, and can be temporarily ignored as well, but if we're out of date, then
        this method returns the version of Lutris that is required. If we're good, or we are ignoring
        the problem, this returns None.

        I expect that most users will not discover the env-var, so they will be prompted
        on each new Lutris release."""
        if self.runtime_versions and not os.environ.get("LUTRIS_NO_CLIENT_VERSION_CHECK"):
            client_version = self.runtime_versions.get("client_version")
            if client_version:
                if parse_version(client_version) > parse_version(settings.VERSION):
                    ignored = settings.read_setting("ignored_supported_lutris_verison")
                    if not ignored or ignored != client_version:
                        return client_version

        return None

    @staticmethod
    def _get_runtime_updaters(runtime_versions: Dict[str, Any]) -> List[ComponentUpdater]:
        """Launch the update process"""
        updaters: List[ComponentUpdater] = []
        for name, remote_runtime in runtime_versions.get("runtimes", {}).items():
            if remote_runtime["architecture"] == "x86_64" and not LINUX_SYSTEM.is_64_bit:
                logger.debug("Skipping runtime %s for %s", name, remote_runtime["architecture"])
                continue

            try:
                url = remote_runtime.get("url")
                if url:
                    if "-proton" not in os.path.basename(url).casefold():
                        updaters.append(RuntimeExtractedComponentUpdater(remote_runtime))
                else:
                    updaters.append(RuntimeFilesComponentUpdater(remote_runtime))
            except Exception as ex:
                logger.exception("Unable to download %s: %s", name, ex)

        return updaters


class RuntimeComponentUpdater(ComponentUpdater):
    """A base class for component updates that use the timestamp from a runtime-info dict
    to decide when an update is required.

    These dicts are part of the 'versions.json' file, sent down from the server. They describe
    what versions of components are available from the server. This dict includes the modification
    date-time of the component, and we compare it to the mtime of the relevant directory.
    """

    def __init__(self, remote_runtime_info: Dict[str, Any]) -> None:
        self.remote_runtime_info = remote_runtime_info
        self.state = ComponentUpdater.PENDING
        # Versioned runtimes keep 1 version per folder
        self.versioned = bool(self.remote_runtime_info.get("versioned"))
        self.version = str(self.remote_runtime_info.get("version") or "") if self.versioned else ""

    @property
    def name(self) -> str:
        return self.remote_runtime_info["name"]

    @property
    def local_runtime_path(self) -> str:
        """Return the local path for the runtime directory where the component
        is kept."""
        return os.path.join(settings.RUNTIME_DIR, self.name)

    def install_update(self, updater: "RuntimeUpdater") -> None:
        raise NotImplementedError

    def get_progress(self) -> ProgressInfo:
        status_text = ComponentUpdater.status_formats[self.state] % self.name

        if self.state == ComponentUpdater.COMPLETED:
            return ProgressInfo.ended(status_text)

        if self.state == ComponentUpdater.PENDING:
            return ProgressInfo(0.0, status_text)

        return ProgressInfo(0, status_text)

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
            return not system.path_exists(os.path.join(self.local_runtime_path, self.version))

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
        self.complete_event = threading.Event()

    def get_progress(self) -> ProgressInfo:
        progress_info = super().get_progress()

        if self.downloader and not progress_info.has_ended:
            return ProgressInfo(self.downloader.progress_fraction, progress_info.label_markup, self.downloader.cancel)

        return progress_info

    @property
    def archive_path(self):
        """This is the path where the archive is downloaded, before being extracted."""
        return os.path.join(settings.RUNTIME_DIR, os.path.basename(self.url))

    def install_update(self, updater: RuntimeUpdater) -> None:
        self.state = ComponentUpdater.DOWNLOADING
        self.complete_event.clear()

        archive_path = self.archive_path
        self.downloader = Downloader(self.url, archive_path, overwrite=True)
        self.downloader.start()
        self.downloader.join()
        self.downloader = None

        AsyncCall(self._install, self._install_cb, archive_path)

    def join(self):
        self.complete_event.wait()

    def _complete(self):
        self.state = ComponentUpdater.COMPLETED
        self.complete_event.set()

    def _install(self, path: str):
        """Finishes the installation after download, on a worker thread. This extracts
        the archive and downloads the versions file for it, the marks the update complete
        so join() above will be unblocked."""
        try:
            self._extract(path)

            self.set_updated_at()
            if self.name in DLL_MANAGERS:
                manager = DLL_MANAGERS[self.name]()
                manager.fetch_versions()
        finally:
            self._complete()

    def _install_cb(self, _completed: bool, error: Exception):
        if error:
            logger.error("Runtime update failed: %s", error)

    def _extract(self, path: str) -> None:
        """Actions taken once a runtime is downloaded

        Arguments:
            path: local path to the runtime archive, or None on download failure
        """
        if not path:
            return

        stats = os.stat(path)
        if not stats.st_size:
            logger.error("Download failed: file %s is empty, Deleting file.", path)
            os.unlink(path)
            return
        directory, _filename = os.path.split(path)

        # Determine the destination path
        dest_path = os.path.join(directory, self.name)

        if self.versioned:
            dest_path = os.path.join(dest_path, self.version)
        else:
            # Delete the existing runtime path
            system.delete_folder(dest_path)
        # Extract the runtime archive
        self.state = ComponentUpdater.EXTRACTING
        archive_path, _destination_path = extract_archive(path, dest_path, merge_single=True)
        os.unlink(archive_path)


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
                executor.submit(self._download_component, component): component["filename"] for component in downloads
            }
            for future in concurrent.futures.as_completed(future_downloads):
                if not future.cancelled() and future.exception():
                    expected_filename = future_downloads[future]
                    logger.warning("Failed to get '%s': %s", expected_filename, future.exception())
        self.state = ComponentUpdater.COMPLETED

    def _should_update_component(self, filename: str, remote_modified_at: time.struct_time) -> bool:
        """Should an individual component be updated?"""
        file_path = os.path.join(self.local_runtime_path, filename)
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
        file_path = os.path.join(self.local_runtime_path, component["filename"])
        http.download_file(component["url"], file_path)
