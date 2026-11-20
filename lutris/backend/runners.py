"""Calls about runners, the programs (emulators, Wine, ...) that run games.

Errors are LutrisError subclasses, such as InvalidRunnerError for a name no
runner has, and RunnerInstallationError.
"""

import asyncio
import os
from collections.abc import Callable
from typing import Any

from lutris import settings
from lutris.api import get_runners
from lutris.delegates import InstallUIDelegate
from lutris.runners import get_runner_names, import_runner
from lutris.util import system


def _get_wine_version_path(version: str) -> str:
    """Return where a Wine version Lutris downloads (such as lutris-GE-Proton8-26) goes."""
    return os.path.join(settings.RUNNER_DIR, "wine", f"{version}{'' if '-x86_64' in version else '-x86_64'}")


async def list_runners() -> list[str]:
    """Return the names of every runner Lutris knows, in alphabetical order."""
    return sorted(get_runner_names(), key=lambda name: name.lower())


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


async def install_runner(name: str, version: str | None = None) -> None:
    """Download and install a runner, or one version of it."""
    runner = import_runner(name)()
    await asyncio.to_thread(runner.install, InstallUIDelegate(), version=version)


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
        path = _get_wine_version_path(version)
        await _wait_for_callbacks(lambda done, error: system.remove_folder(path, done, error))
        return
    runner = import_runner(name)()
    await _wait_for_callbacks(runner.uninstall)
