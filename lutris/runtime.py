"""Runtime handling module"""
import os
import time

from gi.repository import GLib
from lutris.settings import RUNTIME_DIR, RUNTIME_URL
from lutris.util import http, jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.log import logger
from lutris.util.system import LINUX_SYSTEM

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
        return os.path.join(RUNTIME_DIR, self.name)

    def get_updated_at(self):
        """Return the modification date of the runtime folder"""
        if not system.path_exists(self.local_runtime_path):
            return None
        return time.gmtime(os.path.getmtime(self.local_runtime_path))

    def set_updated_at(self):
        """Set the creation and modification time to now"""
        if not system.path_exists(self.local_runtime_path):
            logger.error("No local runtime path in %s", self.local_runtime_path)
            return None
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

    def download(self, remote_runtime_info):
        """Downloads a runtime locally"""
        remote_updated_at = remote_runtime_info["created_at"]
        remote_updated_at = time.strptime(
            remote_updated_at[: remote_updated_at.find(".")], "%Y-%m-%dT%H:%M:%S"
        )
        if not self.should_update(remote_updated_at):
            return None

        url = remote_runtime_info["url"]
        archive_path = os.path.join(RUNTIME_DIR, os.path.basename(url))
        downloader = Downloader(url, archive_path, overwrite=True)
        downloader.start()
        GLib.timeout_add(100, self.check_download_progress, downloader)
        return downloader

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
        directory, _filename = os.path.split(path)

        # Delete the existing runtime path
        initial_path = os.path.join(directory, self.name)
        system.remove_folder(initial_path)

        # Extract the runtime archive
        jobs.AsyncCall(
            extract_archive, self.on_extracted, path, RUNTIME_DIR, merge_single=False
        )

    def on_extracted(self, result, error):
        """Callback method when a runtime has extracted"""
        if error:
            logger.error("Runtime update failed")
            logger.error(error)
            return
        archive_path, _destination_path = result
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
            logger.debug("Runtime disabled, not updating it.")
            return []

        if self.is_updating():
            logger.debug("Runtime already updating")
            return []

        for remote_runtime in self._iter_remote_runtimes():
            runtime = Runtime(remote_runtime["name"], self)
            downloader = runtime.download(remote_runtime)
            if downloader:
                self.current_updates += 1
        return None

    @staticmethod
    def _iter_remote_runtimes():
        request = http.Request(RUNTIME_URL)
        try:
            response = request.get()
        except http.HTTPError as ex:
            logger.error("Failed to get runtimes: %s", ex)
            return
        runtimes = response.json or []
        for runtime in runtimes:

            # Skip 32bit runtimes on 64 bit systems except the main runtime
            if (
                    runtime["architecture"] == "i386"
                    and system.LINUX_SYSTEM.is_64_bit
                    and not runtime["name"].startswith(("Ubuntu", "lib32"))
            ):
                logger.debug(
                    "Skipping runtime %s for %s",
                    runtime["name"],
                    runtime["architecture"],
                )
                continue

            # Skip 64bit runtimes on 32 bit systems
            if runtime["architecture"] == "x86_64" and not system.LINUX_SYSTEM.is_64_bit:
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
            logger.info("Runtime updated")


def get_env(version=None, prefer_system_libs=False, wine_path=None):
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars

    Params:
        version (str): Version of the runtime to use, such as "Ubuntu-18.04" or "legacy"
        prefer_system_libs (bool): Whether to prioritize system libs over runtime libs
        wine_path (str): If you prioritize system libs, provide the path for a lutris wine build
                         if one is being used. This allows Lutris to prioritize the wine libs
                         over everything else.
    Returns:
        dict
    """
    # Adding the STEAM_RUNTIME here is probably unneeded and unwanted
    return {
        key: value
        for key, value in {
            "STEAM_RUNTIME": os.path.join(RUNTIME_DIR, "steam") if not RUNTIME_DISABLED else None,
            "LD_LIBRARY_PATH": ":".join(
                get_paths(
                    version=version,
                    prefer_system_libs=prefer_system_libs,
                    wine_path=wine_path
                )
            ),
        }.items()
        if value
    }


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
    if version.startswith("Ubuntu"):
        lutris_runtime_path = "%s-i686" % version
    elif version == "legacy":
        lutris_runtime_path = "lib32"
    else:
        raise ValueError("Invalid runtime version %s" % version)

    runtime_paths = [
        lutris_runtime_path,
        "steam/i386/lib/i386-linux-gnu",
        "steam/i386/lib",
        "steam/i386/usr/lib/i386-linux-gnu",
        "steam/i386/usr/lib",
    ]

    if system.LINUX_SYSTEM.is_64_bit:
        if version == "legacy":
            lutris_runtime_path = "lib64"
        else:
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
    paths += [os.path.join(RUNTIME_DIR, path) for path in runtime_paths]
    return paths


def get_paths(version=None, prefer_system_libs=True, wine_path=None):
    """Return a list of paths containing the runtime libraries."""
    if not RUNTIME_DISABLED:
        paths = get_runtime_paths(
            version=version,
            prefer_system_libs=prefer_system_libs,
            wine_path=wine_path
        )
    else:
        paths = []
    if os.environ.get("LD_LIBRARY_PATH"):
        paths.append(os.environ["LD_LIBRARY_PATH"])
    return paths
