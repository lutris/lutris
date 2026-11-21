"""Update the components Lutris runs games with: umu, gogdl, Winetricks and the
rest. Progress is announced with RUNTIME_UPDATE_CHANGED."""

import asyncio
import html
import re
from collections.abc import Sequence

from lutris import settings
from lutris.backend.models import RuntimeComponentProgress, RuntimeUpdateStatus
from lutris.exceptions import LutrisError
from lutris.runtime import ComponentUpdater, RuntimeUpdater
from lutris.util.log import logger
from lutris.util.notifications import NotificationSource
from lutris.util.wine.wine import clear_wine_version_cache

# Fired with a RuntimeUpdateStatus while an update runs, and once when it ends
RUNTIME_UPDATE_CHANGED = NotificationSource()

AUTO_UPDATE_SETTING = "auto_update_runtime"
POLL_SECONDS = 0.5

_running = False


def _plain(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", markup or "")).strip()


def _status(updaters: Sequence[ComponentUpdater], running: bool) -> RuntimeUpdateStatus:
    components = []
    for updater in updaters:
        progress = updater.get_progress()
        components.append(
            RuntimeComponentProgress(
                name=updater.name,
                status=_plain(progress.label_markup),
                fraction=progress.progress if progress.progress is None else max(0.0, min(1.0, progress.progress)),
                finished=progress.has_ended,
            )
        )
    return RuntimeUpdateStatus(running=running, components=tuple(components))


async def get_runtime_update_status() -> RuntimeUpdateStatus:
    return RuntimeUpdateStatus(running=_running)


async def is_auto_update_enabled() -> bool:
    return settings.read_bool_setting(AUTO_UPDATE_SETTING, default=True)


async def set_auto_update_enabled(enabled: bool) -> None:
    settings.write_setting(AUTO_UPDATE_SETTING, enabled)


async def update_runtime(force: bool = False) -> tuple[str, ...]:
    """Download the runtime components that are out of date, and return their names.
    Without force this only checks when the last check is stale and automatic updates
    are on, as at startup. Returns nothing when an update is already running."""
    global _running
    if _running:
        return ()
    _running = True
    updaters: list[ComponentUpdater] = []
    try:

        def plan() -> tuple[RuntimeUpdater, list[ComponentUpdater]]:
            runtime_updater = RuntimeUpdater(force=force)
            return runtime_updater, runtime_updater.create_component_updaters()

        runtime_updater, updaters = await asyncio.to_thread(plan)
        if not updaters:
            logger.debug("The runtime is up to date")
            return ()

        def install() -> None:
            failures = []
            for updater in updaters:
                try:
                    updater.install_update(runtime_updater)
                    updater.join()
                except LutrisError as error:
                    failures.append(error.message)
            # Proton builds come from outside Lutris too
            clear_wine_version_cache()
            if failures:
                raise LutrisError("\n".join(failures))

        installing = asyncio.create_task(asyncio.to_thread(install))
        while not installing.done():
            RUNTIME_UPDATE_CHANGED.fire(_status(updaters, running=True))
            await asyncio.wait({installing}, timeout=POLL_SECONDS)
        await installing
        return tuple(updater.name for updater in updaters)
    finally:
        _running = False
        RUNTIME_UPDATE_CHANGED.fire(_status(updaters, running=False))
