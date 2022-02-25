"""Runtime handling module"""
import concurrent.futures
import os
import time

from gi.repository import GLib

from lutris import settings
from lutris.util import http, jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger

RUNTIME_DISABLED = os.environ.get("LUTRIS_RUNTIME", "").lower() in ("0", "off")
DEFAULT_RUNTIME = "Ubuntu-18.04"


class Runtime:

    """Class for manipulating runtime folders"""

    def __init__(self, name, updater):
        self.name = name
        self.updater = updater

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
        local_updated_at = self.get_updated_at()
        if not local_updated_at:
            logger.warning("Runtime %s is not available locally", self.name)
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

    def download(self, remote_runtime_info):
        """Downloads a runtime locally"""
        url = remote_runtime_info["url"]
        if not url:
            return self.download_components()
        remote_updated_at = remote_runtime_info["created_at"]
        remote_updated_at = time.strptime(remote_updated_at[:remote_updated_at.find(".")], "%Y-%m-%dT%H:%M:%S")
        if not self.should_update(remote_updated_at):
            return None

        archive_path = os.path.join(settings.RUNTIME_DIR, os.path.basename(url))
        downloader = Downloader(url, archive_path, overwrite=True)
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

    def get_runtime_components(self):
        """Fetch runtime components from the API"""
        request = http.Request(settings.RUNTIME_URL + "/" + self.name)
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Failed to get components: %s", ex)
            return []
        if not response.json:
            return []
        return response.json.get("components", [])

    def download_components(self):
        """Download a runtime item by individual components."""
        components = self.get_runtime_components()
        downloads = []
        for component in components:
            modified_at = time.strptime(
                component["modified_at"][:component["modified_at"].find(".")], "%Y-%m-%dT%H:%M:%S"
            )
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

    def check_download_progress(self, downloader):
        """Call download.check_progress(), return True if download finished."""
        if not downloader or downloader.state in [
            downloader.CANCELLED,
            downloader.ERROR,
        ]:
            logger.debug("Runtime update interrupted")
            return False

        downloader.check_progress()
        if downloader.state == downloader.COMPLETED:
            self.on_downloaded(downloader.dest)
            return False
        return True

    def on_downloaded(self, path):
        """Actions taken once a runtime is downloaded

        Arguments:
            path (str): local path to the runtime archive
        """
        stats = os.stat(path)
        if not stats.st_size:
            logger.error("Download failed: file %s is empty, Deleting file.", path)
            os.unlink(path)
            self.updater.notify_finish(self)
            return False
        directory, _filename = os.path.split(path)

        # Delete the existing runtime path
        initial_path = os.path.join(directory, self.name)
        system.remove_folder(initial_path)

        # Extract the runtime archive
        jobs.AsyncCall(extract_archive, self.on_extracted, path, settings.RUNTIME_DIR, merge_single=False)
        return False

    def on_extracted(self, result, error):
        """Callback method when a runtime has extracted"""
        if error:
            logger.error("Runtime update failed")
            logger.error(error)
            self.updater.notify_finish(self)
            return False
        archive_path, _destination_path = result
        logger.debug("Deleting runtime archive %s", archive_path)
        os.unlink(archive_path)
        self.set_updated_at()
        self.updater.notify_finish(self)
        return False


class RuntimeUpdater:
    """Class handling the runtime updates"""

    current_updates = 0
    status_updater = None

    def is_updating(self):
        """Return True if the update process is running"""
        return self.current_updates > 0

    def update(self):
        """Launch the update process"""
        if RUNTIME_DISABLED:
            logger.warning("Runtime disabled, not updating it.")
            return 0

        for remote_runtime in self._iter_remote_runtimes():
            runtime = Runtime(remote_runtime["name"], self)
            downloader = runtime.download(remote_runtime)
            if downloader:
                self.current_updates += 1
        return self.current_updates

    @staticmethod
    def _iter_remote_runtimes():
        request = http.Request(settings.RUNTIME_URL + "?enabled=1")
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Failed to get runtimes: %s", ex)
            return
        runtimes = response.json or []
        for runtime in runtimes:

            # Skip 32bit runtimes on 64 bit systems except the main runtime
            if (
                runtime["architecture"] == "i386" and LINUX_SYSTEM.is_64_bit
                and not runtime["name"].startswith(("Ubuntu", "lib32"))
            ):
                logger.debug(
                    "Skipping runtime %s for %s",
                    runtime["name"],
                    runtime["architecture"],
                )
                continue

            # Skip 64bit runtimes on 32 bit systems
            if runtime["architecture"] == "x86_64" and not LINUX_SYSTEM.is_64_bit:
                logger.debug(
                    "Skipping runtime %s for %s",
                    runtime["name"],
                    runtime["architecture"],
                )
                continue

            yield runtime

    def notify_finish(self, runtime):
        """A runtime has finished downloading"""
        logger.debug("Runtime %s is now updated and available", runtime.name)
        self.current_updates -= 1
        if self.current_updates == 0:
            logger.info("Runtime is fully updated.")


def get_env(version=None, prefer_system_libs=False, wine_path=None):
    """Return a dict containing LD_LIBRARY_PATH env var

    Params:
        version (str): Version of the runtime to use, such as "Ubuntu-18.04" or "legacy"
        prefer_system_libs (bool): Whether to prioritize system libs over runtime libs
        wine_path (str): If you prioritize system libs, provide the path for a lutris wine build
                         if one is being used. This allows Lutris to prioritize the wine libs
                         over everything else.
    Returns:
        dict
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
