import os
from gettext import gettext as _

from lutris import settings
from lutris.api import load_runtime_versions, download_runtime_versions
from lutris.runtime import RUNTIME_DISABLED, Runtime
from lutris.services.lutris import sync_media
from lutris.util import update_cache, system
from lutris.util.downloader import Downloader
from lutris.util.extract import extract_archive
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.wine.wine import get_installed_wine_versions


class RuntimeUpdater:
    """Class handling the runtime updates"""
    status_updater = None
    update_functions = []
    downloaders = {}
    status_text: str = ""

    def __init__(self, pci_ids: list = None, force: bool = False):
        self.force = force
        self.pci_ids = pci_ids or []
        self.runtime_versions = {}
        if RUNTIME_DISABLED:
            logger.warning("Runtime disabled. Safety not guaranteed.")
        else:
            self.add_update("runtime", self._update_runtime, hours=12)
            self.add_update("runners", self._update_runners, hours=12)

        self.add_update("media", self._update_media, hours=240)

    def add_update(self, key: str, update_function, hours):
        """__init__ calls this to register each update. This function
        only registers the update if it hasn't been tried in the last
        'hours' hours. This is trakced in 'updates.json', and identified
        by 'key' in that file."""
        last_call = update_cache.get_last_call(key)
        if self.force or not last_call or last_call > 3600 * hours:
            self.update_functions.append((key, update_function))

    @property
    def has_updates(self) -> bool:
        """Returns True if there are any updates to perform."""
        return len(self.update_functions) > 0

    def load_runtime_versions(self) -> dict:
        """Load runtime versions from json file"""
        self.runtime_versions = load_runtime_versions()
        return self.runtime_versions

    def update_runtimes(self):
        """Performs all the registered updates."""
        self.runtime_versions = download_runtime_versions(self.pci_ids)
        for key, func in self.update_functions:
            func()
            update_cache.write_date_to_cache(key)

    def _update_runners(self):
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

            runner_path = os.path.join(settings.RUNNER_DIR, name,
                                       "-".join([upstream_runner["version"], upstream_runner["architecture"]]))
            if system.path_exists(runner_path):
                continue
            self.status_text = _("Updating %s") % name
            archive_download_path = os.path.join(settings.CACHE_DIR, os.path.basename(upstream_runner["url"]))
            downloader = Downloader(upstream_runner["url"], archive_download_path)
            downloader.start()
            self.downloaders = {"wine": downloader}
            downloader.join()
            self.status_text = _("Extracting %s") % name
            extract_archive(archive_download_path, runner_path)

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
            runtime = Runtime(remote_runtime["name"], self)
            self.status_text = _("Updating %s") % remote_runtime['name']
            if remote_runtime["url"]:

                downloader = runtime.download(remote_runtime)
                if downloader:
                    self.downloaders[runtime] = downloader
                    downloader.join()
            else:
                runtime.download_components()

    def _update_media(self):
        self.status_text = _("Updating media")
        sync_media()
