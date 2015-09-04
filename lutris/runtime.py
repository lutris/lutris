import os
from gi.repository import GLib

from lutris.downloader import Downloader
from lutris.settings import RUNTIME_DIR, RUNTIME_URL
from lutris.util import http, jobs, system
from lutris.util.extract import extract_archive
from lutris.util.log import logger

LOCAL_VERSION_PATH = os.path.join(RUNTIME_DIR, "VERSION")


def get_env():
    """Return a dict containing LD_LIBRARY_PATH and STEAM_RUNTIME env vars."""
    runtime_dir = os.path.join(RUNTIME_DIR, 'steam')
    ld_library_path = ':'.join(get_paths()) + ':$LD_LIBRARY_PATH'
    return {'STEAM_RUNTIME': runtime_dir, 'LD_LIBRARY_PATH': ld_library_path}


def get_paths():
    """Return a list of paths containing the runtime libraries."""
    runtime_dir = os.path.join(RUNTIME_DIR, 'steam')
    paths = ["lutris-override32",
             "i386/lib/i386-linux-gnu",
             "i386/lib",
             "i386/usr/lib/i386-linux-gnu",
             "i386/usr/lib"]
    if system.is_64bit:
        paths += ["lutris-override64",
                  "amd64/lib/x86_64-linux-gnu",
                  "amd64/lib",
                  "amd64/usr/lib/x86_64-linux-gnu",
                  "amd64/usr/lib"]
    return [os.path.join(runtime_dir, path) for path in paths]


def is_outdated():
    return Updater.get_remote_version() > Updater.get_local_version()


def is_updating():
    return Updater.is_updating


def get_downloader():
    return Updater.downloader


class Updater:
    """Download and extract the runtime."""
    is_updating = False
    downloader = None

    set_status = None

    @classmethod
    def __init__(cls):
        cls.filename = ("steam-runtime_64.tar.gz" if system.is_64bit
                        else "steam-runtime_32.tar.gz")
        url = RUNTIME_URL + cls.filename
        cls.archive_path = os.path.join(RUNTIME_DIR, cls.filename)
        if not cls.downloader:
            cls.downloader = Downloader(url, cls.archive_path, overwrite=True)

        cls.remote_version = cls.get_remote_version()

    @classmethod
    def start(cls, set_status=set_status):
        if cls.is_updating:
            return
        logger.debug("Updating runtime")
        if not is_outdated():
            logger.debug("Runtime already up to date")
            return

        cls.set_status = set_status
        cls.is_updating = True
        if set_status:
            set_status("Updating Runtime")

        cls.downloader.start()
        GLib.timeout_add(100, cls.check_download_progress)

    @classmethod
    def cancel(cls):
        if cls.downloader:
            if cls.downloader.state == cls.downloader.DOWNLOADING:
                cls.downloader.cancel()

    @classmethod
    def check_download_progress(cls):
        if (not cls.downloader
            or cls.downloader.state in [cls.downloader.CANCELLED,
                                        cls.downloader.ERROR]):
            logger.debug("Runtime update interrupted")
            if cls.set_status:
                cls.set_status("Runtime update interrupted")
            cls.is_updating = False
            cls.downloader = None
            return False

        cls.downloader.check_progress()
        if cls.downloader.state == cls.downloader.COMPLETED:
            cls.on_downloaded()
            return False
        return True

    @classmethod
    def on_downloaded(cls):
        system.remove_folder(os.path.join(RUNTIME_DIR, 'steam'))
        # Remove legacy folders
        system.remove_folder(os.path.join(RUNTIME_DIR, 'lib32'))
        system.remove_folder(os.path.join(RUNTIME_DIR, 'lib64'))

        jobs.AsyncCall(extract_archive, cls.on_extracted, cls.archive_path,
                       RUNTIME_DIR, merge_single=False)

    @classmethod
    def on_extracted(cls, result, error):
        if error:
            logger.debug("Runtime update failed")
            if cls.set_status:
                cls.set_status("Runtime update failed")
            cls.is_updating = False
            cls.downloader = None
            return

        os.unlink(cls.archive_path)
        with open(LOCAL_VERSION_PATH, 'w') as version_file:
            version_file.write(str(cls.remote_version))

        logger.debug("Runtime updated")
        if cls.set_status:
            cls.set_status("Runtime updated")
        cls.is_updating = False
        cls.downloader = None

    @classmethod
    def get_local_version(cls):
        if not os.path.exists(LOCAL_VERSION_PATH):
            return 0
        with open(LOCAL_VERSION_PATH, 'r') as version_file:
            version_content = version_file.read().strip()
        return cls.parse_version(version_content)

    @classmethod
    def get_remote_version(cls):
        version_url = RUNTIME_URL + "VERSION"
        version_content = http.download_content(version_url)
        return cls.parse_version(version_content) if version_content else 0

    @staticmethod
    def parse_version(version_content):
        try:
            version = int(version_content)
        except (ValueError, TypeError):
            version = 0
        return version
