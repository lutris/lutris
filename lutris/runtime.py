import os
import time

from gi.repository import GLib
from lutris.settings import RUNTIME_DIR, RUNTIME_URL
from lutris.util import http, jobs, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.log import logger

RUNTIME_DISABLED = os.environ.get('LUTRIS_RUNTIME', '').lower() in ('0', 'off')


class RuntimeUpdater:
    current_updates = 0
    status_updater = None
    cancellables = []

    def is_updating(self):
        return self.current_updates > 0

    def get_created_at(self, name):
        path = os.path.join(RUNTIME_DIR, name)
        if not os.path.exists(path):
            return time.gmtime(0)
        return time.gmtime(os.path.getctime(path))

    def update(self, status_updater=None):
        if RUNTIME_DISABLED:
            logger.debug("Runtime disabled, not updating it.")
            return []

        if self.is_updating():
            logger.debug("Runtime already updating")
            return []

        if status_updater:
            self.status_updater = status_updater

        for runtime in self._iter_runtimes():
            self.download_runtime(runtime)

    def _iter_runtimes(self):
        request = http.Request(RUNTIME_URL)
        response = request.get()
        runtimes = response.json or []
        for runtime in runtimes:

            # Skip 32bit runtimes on 64 bit systems except the lib32 one
            if(runtime['architecture'] == 'i386' and
               system.IS_64BIT and
               runtime['name'] != 'lib32'):
                logger.debug('Skipping runtime %s for %s',
                             runtime['name'], runtime['architecture'])
                continue

            # Skip 64bit runtimes on 32 bit systems
            if(runtime['architecture'] == 'x86_64' and
               not system.IS_64BIT):
                logger.debug('Skipping runtime %s for %s',
                             runtime['name'], runtime['architecture'])
                continue

            yield runtime

    def download_runtime(self, runtime):
        name = runtime['name']
        created_at = runtime['created_at']
        created_at = time.strptime(created_at[:created_at.find('.')],
                                   "%Y-%m-%dT%H:%M:%S")
        if self.get_created_at(name) >= created_at:
            return
        if self.status_updater:
            self.status_updater("Updating Runtime")
        logger.debug('Updating runtime %s', name)
        url = runtime['url']
        archive_path = os.path.join(RUNTIME_DIR, os.path.basename(url))
        self.current_updates += 1
        downloader = Downloader(url, archive_path, overwrite=True)
        self.cancellables.append(downloader.cancel)
        downloader.start()
        GLib.timeout_add(100, self.check_download_progress, downloader)

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


def get_env(prefer_system_libs=True, wine_path=None):
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars."""
    # Adding the STEAM_RUNTIME here is probably unneeded and unwanted
    return {
        key: value for key, value in {
            'STEAM_RUNTIME': os.path.join(RUNTIME_DIR, 'steam') if not RUNTIME_DISABLED else None,
            'LD_LIBRARY_PATH': ':'.join(get_paths(
                prefer_system_libs=prefer_system_libs,
                wine_path=wine_path
            ))
        }.items() if value
    }


def get_paths(prefer_system_libs=True, wine_path=None):
    """Return a list of paths containing the runtime libraries."""
    paths = []

    if not RUNTIME_DISABLED:
        runtime_paths = [
            "lib32",
            "steam/i386/lib/i386-linux-gnu",
            "steam/i386/lib",
            "steam/i386/usr/lib/i386-linux-gnu",
            "steam/i386/usr/lib"
        ]

        if system.IS_64BIT:
            runtime_paths += [
                "lib64",
                "steam/amd64/lib/x86_64-linux-gnu",
                "steam/amd64/lib",
                "steam/amd64/usr/lib/x86_64-linux-gnu",
                "steam/amd64/usr/lib"
            ]

        if prefer_system_libs:
            paths = []
            # Prioritize libwine.so.1 for lutris builds
            if system.path_exists(wine_path):
                paths.append(os.path.join(wine_path, 'lib'))
                lib64_path = os.path.join(wine_path, 'lib64')
                if system.path_exists(lib64_path):
                    paths.append(lib64_path)

            # This prioritizes system libraries over
            # the Lutris and Steam runtimes.
            paths.append("/usr/lib")
            if os.path.exists("/usr/lib32"):
                paths.append("/usr/lib32")
            if os.path.exists("/lib/x86_64-linux-gnu"):
                paths.append("/lib/x86_64-linux-gnu")
            if os.path.exists("/lib/i386-linux-gnu"):
                paths.append("/lib/i386-linux-gnu")
            if os.path.exists("/usr/lib/x86_64-linux-gnu"):
                paths.append("/usr/lib/x86_64-linux-gnu")
            if os.path.exists("/usr/lib/i386-linux-gnu"):
                paths.append("/usr/lib/i386-linux-gnu")

        # Then resolve absolute paths for the runtime
        paths += [os.path.join(RUNTIME_DIR, path) for path in runtime_paths]

    if os.environ.get('LD_LIBRARY_PATH'):
        paths.append(os.environ['LD_LIBRARY_PATH'])

    return paths
