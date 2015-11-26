import os
import time
from gi.repository import GLib

from lutris.downloader import Downloader
from lutris.settings import RUNTIME_DIR, RUNTIME_URL
from lutris.util import http, jobs, system
from lutris.util.extract import extract_archive
from lutris.util.log import logger

CURRENT_UPDATES = None
STATUS_UPDATER = None


def is_updating(include_pending_updates=True):
    if include_pending_updates and CURRENT_UPDATES is None:
        return True
    return CURRENT_UPDATES > 0


def get_created_at(name):
    path = os.path.join(RUNTIME_DIR, name)
    if not os.path.exists(path):
        return time.gmtime(0)
    return time.gmtime(os.path.getctime(path))


def update(status_updater=None):
    global STATUS_UPDATER
    if is_updating(False):
        logger.debug("Runtime already updating")
        return []

    if status_updater:
        STATUS_UPDATER = status_updater

    return get_runtimes()


def get_runtimes():
    global CURRENT_UPDATES
    global STATUS_UPDATER
    if CURRENT_UPDATES is None:
        CURRENT_UPDATES = 0
    request = http.Request(RUNTIME_URL)
    response = request.get()
    cancellables = []
    for runtime in response.json:
        name = runtime['name']
        if '64' in name and not system.is_64bit:
            continue
        created_at = runtime['created_at']
        created_at = time.strptime(created_at[:created_at.find('.')],
                                   "%Y-%m-%dT%H:%M:%S")
        if get_created_at(name) < created_at:
            STATUS_UPDATER("Updating Runtime")
            logger.debug('Updating runtime %s', name)
            url = runtime['url']
            archive_path = os.path.join(RUNTIME_DIR, os.path.basename(url))
            CURRENT_UPDATES += 1
            downloader = Downloader(url, archive_path, overwrite=True)
            cancellables.append(downloader.cancel)
            downloader.start()
            GLib.timeout_add(100, check_download_progress, downloader)
        else:
            logger.debug("Runtime %s up to date", name)
    return cancellables


def check_download_progress(downloader):
    """Call download.check_progress(), return True if download finished."""
    if (not downloader or downloader.state in [downloader.CANCELLED,
                                               downloader.ERROR]):
        logger.debug("Runtime update interrupted")
        return False

    downloader.check_progress()
    if downloader.state == downloader.COMPLETED:
        on_downloaded(downloader.dest)
        return False
    return True


def on_downloaded(path):
    dir, filename = os.path.split(path)
    folder = os.path.join(dir, filename[:filename.find('.')])
    system.remove_folder(folder)
    jobs.AsyncCall(extract_archive, on_extracted, path, RUNTIME_DIR,
                   merge_single=False)


def on_extracted(result, error):
    global CURRENT_UPDATES
    global STATUS_UPDATER
    CURRENT_UPDATES -= 1
    if error:
        logger.debug("Runtime update failed")
        return
    archive_path = result[0]
    os.unlink(archive_path)

    if STATUS_UPDATER and CURRENT_UPDATES == 0:
        STATUS_UPDATER("Runtime updated")
    logger.debug("Runtime updated")


def get_env():
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars."""
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
