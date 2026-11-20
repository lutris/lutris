"""Calls about runners, the programs (emulators, Wine, ...) that run games.

Errors are LutrisError subclasses, such as InvalidRunnerError for a name no
runner has, and RunnerInstallationError.
"""

import asyncio
import os
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path
from time import monotonic
from typing import Any

from lutris import settings
from lutris.api import get_runners
from lutris.backend.models import RunnerInfo
from lutris.delegates import InstallUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import Game
from lutris.runners import RunnerInstallationError, get_installed, get_runner_names, import_runner
from lutris.util import linux, system
from lutris.util.downloader import BaseDownloader, SimpleDownloader
from lutris.util.http import HTTPError
from lutris.util.strings import get_natural_sort_key, human_size
from lutris.util.wine import proton
from lutris.util.wine.wine import clear_wine_version_cache


@dataclass(frozen=True)
class RunnerCatalogEntry:
    name: str
    label: str
    description: str
    installed: bool
    can_install: bool
    can_remove: bool


@dataclass(frozen=True)
class ProtonBuild:
    version: str
    installed: bool
    can_remove: bool


@dataclass(frozen=True)
class RunnerInstallInteraction:
    progress: Callable[[str, float | None], None]
    question: Callable[[str, str], Coroutine[Any, Any, bool]]
    file: Callable[[str, str, str], Coroutine[Any, Any, str | None]]


class _InstallDelegate(InstallUIDelegate):
    def __init__(self, interaction: RunnerInstallInteraction, loop: asyncio.AbstractEventLoop) -> None:
        self._interaction = interaction
        self._loop = loop
        self._last_progress = 0.0

    def show_install_yesno_inquiry(self, question: str, title: str) -> bool:
        return asyncio.run_coroutine_threadsafe(self._interaction.question(title, question), self._loop).result()

    def show_install_file_inquiry(self, question: str, title: str, message: str) -> str | None:
        return asyncio.run_coroutine_threadsafe(self._interaction.file(title, question, message), self._loop).result()

    def download_install_file(self, url: str, destination: str) -> bool:
        self._publish(_("Downloading…"), None)
        self._last_progress = 0.0
        downloader = SimpleDownloader(url, destination, overwrite=True)
        downloader.start()
        completed = downloader.join(self._download_progress)
        if completed:
            self._publish(_("Verifying and installing…"), None)
        return completed

    def _publish(self, label: str, fraction: float | None) -> None:
        self._loop.call_soon_threadsafe(self._interaction.progress, label, fraction)

    def _download_progress(self, downloader: BaseDownloader) -> None:
        now = monotonic()
        if not downloader.full_size or now - self._last_progress < 0.1:
            return
        self._last_progress = now
        self._publish(
            _("%(downloaded)s of %(total)s")
            % {"downloaded": human_size(downloader.downloaded_size), "total": human_size(downloader.full_size)},
            min(1.0, downloader.progress_fraction),
        )


def _get_wine_version_path(version: str) -> str:
    """Return where a Wine version Lutris downloads (such as lutris-GE-Proton8-26) goes."""
    return os.path.join(settings.RUNNER_DIR, "wine", f"{version}{'' if '-x86_64' in version else '-x86_64'}")


async def list_runners() -> list[str]:
    """Return the names of every runner Lutris knows, in alphabetical order."""
    return sorted(get_runner_names(), key=lambda name: name.lower())


async def list_installed_runners() -> list[RunnerInfo]:
    """Return the runners that are installed, in alphabetical order of their names."""
    installed = await asyncio.to_thread(get_installed)
    return sorted((RunnerInfo(r.name, r.human_name) for r in installed), key=lambda r: r.human_name.casefold())


async def list_runner_catalog() -> tuple[RunnerCatalogEntry, ...]:
    """Describe the runners and which actions Lutris can perform."""
    return await asyncio.to_thread(_runner_catalog)


def _runner_catalog() -> tuple[RunnerCatalogEntry, ...]:
    entries = []
    for name in get_runner_names():
        runner = import_runner(name)()
        installed = runner.is_installed()
        entries.append(
            RunnerCatalogEntry(
                name,
                runner.human_name,
                str(getattr(runner, "description", "")),
                installed,
                not installed and name not in {"linux", "steam", "wine"},
                name != "wine" and runner.can_uninstall(),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.label.casefold()))


def _managed_proton_path(version: str) -> Path | None:
    if not proton.is_ge_proton_release(version):
        return None
    root = Path(proton.get_steam_compat_dir())
    for name in (version, f"{version}-{linux.LINUX_SYSTEM.arch}"):
        path = root / name
        if not path.is_symlink() and (path / "proton").is_file():
            return path
    return None


async def list_proton_builds(available: tuple[str, ...] = ()) -> tuple[ProtonBuild, ...]:
    """List installed and available GE-Proton builds with removable copies identified."""
    return await asyncio.to_thread(_proton_builds, available)


def _proton_builds(available: tuple[str, ...]) -> tuple[ProtonBuild, ...]:
    compat_dir = Path(proton.get_steam_compat_dir())
    installed_names = list(proton.get_proton_versions())
    if compat_dir.is_dir():
        installed_names.extend(path.name for path in compat_dir.iterdir() if (path / "proton").is_file())
    installed = {tag for name in installed_names if (tag := proton.get_ge_proton_release_tag(name))}
    builds = []
    for version in sorted(installed.union(available), key=get_natural_sort_key, reverse=True):
        managed = _managed_proton_path(version) is not None
        builds.append(ProtonBuild(version, managed or version in installed, managed))
    return tuple(builds)


async def list_ge_proton_releases() -> tuple[str, ...]:
    """Fetch recent released builds for the current architecture."""
    try:
        return await asyncio.to_thread(proton.get_ge_proton_releases)
    except (HTTPError, ValueError) as error:
        raise LutrisError(_("Could not load GE-Proton releases.")) from error


async def list_wine_versions() -> list[dict[str, Any]]:
    """Return the Wine versions Lutris can download, as lutris.net describes them."""
    runner_info = await asyncio.to_thread(get_runners, "wine")
    return [version for version in runner_info["versions"] if version["version"]]


async def is_runner_installed(name: str, version: str | None = None) -> bool:
    """True if a runner is installed; for "wine", a version names one of the Wine
    versions Lutris downloads."""
    if name == "wine" and version:
        return os.path.isdir(_get_wine_version_path(version))
    return import_runner(name)().is_installed()


async def install_runner(
    name: str, version: str | None = None, *, interaction: RunnerInstallInteraction | None = None
) -> None:
    """Download and install a runner, or one version of it."""
    runner = import_runner(name)()
    if version and name == "wine" and proton.is_ge_proton_release(version):
        if _managed_proton_path(version) or proton.is_proton_version(version):
            return
    delegate = _InstallDelegate(interaction, asyncio.get_running_loop()) if interaction else InstallUIDelegate()
    await asyncio.to_thread(runner.install, delegate, version=version)
    if (
        interaction
        and name == "wine"
        and version
        and proton.is_ge_proton_release(version)
        and not _managed_proton_path(version)
    ):
        raise RunnerInstallationError(_("%s was not installed.") % version)
    if interaction and name != "wine" and not await asyncio.to_thread(runner.is_installed):
        raise RunnerInstallationError(_("%s was not installed.") % runner.human_name)


async def prepare_game_runner(game_id: str, interaction: RunnerInstallInteraction) -> bool:
    """Offer to install the runner configured for this game, if it is missing."""
    delegate = _InstallDelegate(interaction, asyncio.get_running_loop())

    def prepare() -> bool:
        game = Game(game_id)
        if not game.runner or not game.is_installed:
            return True
        return game.runner.is_installed() or game.runner.install_dialog(delegate)

    return await asyncio.to_thread(prepare)


async def can_uninstall_runner(name: str) -> bool:
    """True if Lutris installed a runner, and so can uninstall it."""
    return import_runner(name)().can_uninstall()


async def _wait_for_callbacks(start: Callable[[Callable[[], None], Callable[[Exception], None]], None]) -> None:
    """Call start with a completion and an error callback, and wait until it calls one."""
    done = asyncio.get_running_loop().create_future()

    def on_completed() -> None:
        if not done.done():
            done.set_result(None)

    def on_error(error: Exception) -> None:
        if not done.done():
            done.set_exception(error)

    start(on_completed, on_error)
    await done


async def uninstall_runner(name: str, version: str | None = None) -> None:
    """Move a runner, or one Wine version Lutris downloaded, to the trash."""
    if name == "wine" and version:
        if proton.is_ge_proton_release(version):
            proton_path = _managed_proton_path(version)
            if proton_path is None:
                raise LutrisError(_("%s is outside the GE-Proton folder managed here.") % version)
            await _wait_for_callbacks(lambda done, error: system.remove_folder(str(proton_path), done, error))
            clear_wine_version_cache()
            return
        path = _get_wine_version_path(version)
        await _wait_for_callbacks(lambda done, error: system.remove_folder(path, done, error))
        clear_wine_version_cache()
        return
    runner = import_runner(name)()
    await _wait_for_callbacks(runner.uninstall)
