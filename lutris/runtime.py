import os
import time
from gi.repository import GLib

from lutris.downloader import Downloader
from lutris.settings import RUNTIME_DIR, RUNTIME_URL
from lutris.util import http, jobs, system
from lutris.util.extract import extract_archive
from lutris.util.log import logger


def is_disabled():
    """Checks if runtime is disabled from an environment variable.
    Returns True if LUTRIS_RUNTIME is set to a negative value,
    False if any other value and None if LUTRIS_RUNTIME is not set.
    """
    env_runtime = os.getenv('LUTRIS_RUNTIME')
    if env_runtime:
        if env_runtime.lower() in ('0', 'off'):
            return True
        else:
            return False


class RuntimeUpdater:
    current_updates = 0
    status_updater = None

    def is_updating(self):
        return self.current_updates > 0

    def get_created_at(self, name):
        path = os.path.join(RUNTIME_DIR, name)
        if not os.path.exists(path):
            return time.gmtime(0)
        return time.gmtime(os.path.getctime(path))

    def update(self, status_updater=None):
        if is_disabled():
            logger.debug("Runtime disabled, not updating it.")
            return []

        if self.is_updating():
            logger.debug("Runtime already updating")
            return []

        if status_updater:
            self.status_updater = status_updater

        return self.get_runtimes()

    def get_runtimes(self):
        request = http.Request(RUNTIME_URL)
        response = request.get()
        cancellables = []
        runtimes = response.json or []
        for runtime in runtimes:
            name = runtime['name']
            if '64' in name and not system.is_64bit:
                continue
            created_at = runtime['created_at']
            created_at = time.strptime(created_at[:created_at.find('.')],
                                       "%Y-%m-%dT%H:%M:%S")
            if self.get_created_at(name) < created_at:
                if self.status_updater:
                    self.status_updater("Updating Runtime")
                logger.debug('Updating runtime %s', name)
                url = runtime['url']
                archive_path = os.path.join(RUNTIME_DIR, os.path.basename(url))
                self.current_updates += 1
                downloader = Downloader(url, archive_path, overwrite=True)
                cancellables.append(downloader.cancel)
                downloader.start()
                GLib.timeout_add(100, self.check_download_progress, downloader)
        return cancellables

    def check_download_progress(self, downloader):
        """Call download.check_progress(), return True if download finished."""
        if (not downloader or downloader.state in [downloader.CANCELLED,
                                                   downloader.ERROR]):
            logger.debug("Runtime update interrupted")
            return False

        downloader.check_progress()
        if downloader.state == downloader.COMPLETED:
            self.on_downloaded(downloader.dest)
            return False
        return True

    def on_downloaded(self, path):
        dir, filename = os.path.split(path)
        folder = os.path.join(dir, filename[:filename.find('.')])
        system.remove_folder(folder)
        jobs.AsyncCall(extract_archive, self.on_extracted, path, RUNTIME_DIR,
                       merge_single=False)

    def on_extracted(self, result, error):
        self.current_updates -= 1
        if error:
            logger.debug("Runtime update failed")
            return
        archive_path = result[0]
        os.unlink(archive_path)

        if self.status_updater and self.current_updates == 0:
            self.status_updater("Runtime updated")
        logger.debug("Runtime updated")


def get_env():
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars."""
    if is_disabled():
        return {}

    steam_runtime_dir = os.path.join(RUNTIME_DIR, 'steam')
    ld_library_path = ':'.join(get_paths()) + ':$LD_LIBRARY_PATH'
    return {
        'STEAM_RUNTIME': steam_runtime_dir,
        'LD_LIBRARY_PATH': ld_library_path
    }


def get_paths():
    """Return a list of paths containing the runtime libraries."""
    paths = [
        "lib32",
        "steam/i386/lib/i386-linux-gnu",
        "steam/i386/lib",
        "steam/i386/usr/lib/i386-linux-gnu",
        "steam/i386/usr/lib"
    ]
    if system.is_64bit:
        paths += [
            "lib64",
            "steam/amd64/lib/x86_64-linux-gnu",
            "steam/amd64/lib",
            "steam/amd64/usr/lib/x86_64-linux-gnu",
            "steam/amd64/usr/lib"
        ]
    return [os.path.join(RUNTIME_DIR, path) for path in paths]
