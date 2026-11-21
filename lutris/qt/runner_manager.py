"""Expose runner management to Qt Quick."""

import asyncio
from collections.abc import Callable, Coroutine
from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from lutris.backend import runners
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class RunnerManagerController(QObject):
    stateChanged = Signal()
    progressChanged = Signal()
    runnersChanged = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._runners: tuple[runners.RunnerCatalogEntry, ...] = ()
        self._builds: tuple[runners.ProtonBuild, ...] = ()
        self._releases: tuple[str, ...] = ()
        self._proton = False
        self._task: asyncio.Task[None] | None = None
        self._message = ""
        self._fraction = -1.0

    @Property(list, notify=stateChanged)
    def entries(self) -> list[dict[str, str | bool]]:
        return self._entries()

    def _entries(self) -> list[dict[str, str | bool]]:
        if self._proton:
            return [
                {
                    "key": build.version,
                    "label": build.version,
                    "description": "",
                    "installed": build.installed,
                    "canInstall": not build.installed,
                    "canRemove": build.can_remove,
                    "canConfigure": False,
                    "manageProton": False,
                }
                for build in self._builds
            ]
        return [
            {
                "key": entry.name,
                "label": entry.label,
                "description": entry.description,
                "installed": entry.installed,
                "canInstall": entry.can_install,
                "canRemove": entry.can_remove,
                "canConfigure": True,
                "manageProton": entry.name == "wine",
            }
            for entry in self._runners
        ]

    @Property(bool, notify=stateChanged)
    def proton(self) -> bool:
        return self._proton

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._task is not None

    @Property(str, notify=progressChanged)
    def message(self) -> str:
        return self._message

    @Property(float, notify=progressChanged)
    def fraction(self) -> float:
        return self._fraction

    @Slot()
    def open(self) -> None:
        if self._task is None:
            self._proton = False
            self._start(self._load_runners(), _("Checking runners…"))

    @Slot()
    def show_proton(self) -> None:
        if self._task is None:
            self._proton = True
            self._start(self._load_proton(), _("Looking up Proton releases…"))

    @Slot(str)
    def install(self, key: str) -> None:
        entry = next((item for item in self._entries() if item["key"] == key and item["canInstall"]), None)
        if self._task is None and entry:
            self._start(self._install(key), _("Installing %s…") % entry["label"])

    @Slot(str)
    def remove(self, key: str) -> None:
        entry = next((item for item in self._entries() if item["key"] == key and item["canRemove"]), None)
        if self._task is None and entry:
            self._start(self._remove(key, str(entry["label"])), _("Removing %s…") % entry["label"])

    def _start(self, operation: Coroutine[Any, Any, None], message: str) -> None:
        self._task = start_task(self._run(operation), self._prompts.error)
        self._set_progress(message)
        self.stateChanged.emit()

    async def _run(self, operation: Coroutine[Any, Any, None]) -> None:
        try:
            await operation
        finally:
            self._task = None
            self._set_progress("")
            self.stateChanged.emit()

    def _set_progress(self, message: str, fraction: float | None = None) -> None:
        self._message = message
        self._fraction = fraction if fraction is not None else -1.0
        self.progressChanged.emit()

    async def _load_runners(self) -> None:
        self._runners = await runners.list_runner_catalog()

    async def _load_proton(self) -> None:
        self._builds = await runners.list_proton_builds(self._releases)
        self.stateChanged.emit()
        self._releases = await runners.list_proton_releases()
        self._builds = await runners.list_proton_builds(self._releases)

    async def _install(self, key: str) -> None:
        name, version = ("wine", key) if self._proton else (key, None)
        interaction = runners.RunnerInstallInteraction(self._set_progress, self._ask, self._choose_file)
        try:
            await runners.install_runner(name, version, interaction=interaction)
        finally:
            await self._refresh_after_change()

    async def _remove(self, key: str, label: str) -> None:
        if not await self._ask(_("Remove runner"), _("Move %s to the Trash?") % label):
            return
        name, version = ("wine", key) if self._proton else (key, None)
        try:
            await runners.uninstall_runner(name, version)
        finally:
            await self._refresh_after_change()

    async def _refresh_after_change(self) -> None:
        self.runnersChanged.emit()
        if self._proton:
            self._builds = await runners.list_proton_builds(self._releases)
        else:
            await self._load_runners()

    async def _ask(self, title: str, message: str) -> bool:
        return await self._prompts.ask_async("question", title, message) is not None

    async def _choose_file(self, title: str, question: str, message: str) -> str | None:
        if not await self._ask(title, question):
            return None
        return await self._prompts.ask_async("file", message, "")

    async def prepare_for_launch(self, game_id: str, progress: Callable[[str, float | None], None]) -> bool:
        interaction = runners.RunnerInstallInteraction(progress, self._ask, self._choose_file)
        return await runners.prepare_game_runner(game_id, interaction)
