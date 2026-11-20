"""Expose a game's shortcut destinations and launch targets to Qt Quick."""

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from lutris.backend import shortcuts
from lutris.qt.tasks import start_task

if TYPE_CHECKING:
    from lutris.qt.delegates import PromptController


class GameShortcutController(QObject):
    changed = Signal()

    def __init__(self, prompts: "PromptController", parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._state: shortcuts.GameShortcuts | None = None
        self._task: asyncio.Task[None] | None = None
        self._game_id = ""

    @Property(list, notify=changed)
    def targets(self) -> list[dict[str, str | bool]]:
        if self._state is None:
            return []
        return [{"kind": target.kind, "label": target.label, "exists": target.exists} for target in self._state.targets]

    @Property(list, notify=changed)
    def configurationLabels(self) -> list[str]:  # noqa: N802
        return list(self._state.configuration_labels) if self._state else []

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    @Slot(str)
    def open_shortcuts(self, game_id: str) -> None:
        self._game_id = game_id
        self._state = None
        self._run(self._load(game_id))

    async def _load(self, game_id: str) -> None:
        state = await shortcuts.get_shortcuts(game_id)
        if self._game_id == game_id:
            self._state = state

    @Slot(str, bool, int)
    def set_shortcut(self, kind: str, present: bool, index: int) -> None:
        if self.busy or self._state is None:
            return
        names = self._state.configuration_names
        if present and not 0 <= index < len(names):
            return
        self._run(self._set_shortcut(self._game_id, kind, present, names[index] if present else ""))

    async def _set_shortcut(self, game_id: str, kind: str, present: bool, configuration: str) -> None:
        state = await shortcuts.set_shortcut(game_id, kind, present, configuration)
        if self._game_id == game_id:
            self._state = state

    def _run(self, work: Coroutine[None, None, None]) -> None:
        self._task = start_task(work, self._prompts.error)
        self._task.add_done_callback(self._completed)
        self.changed.emit()

    def _completed(self, _task: asyncio.Task[None]) -> None:
        self.changed.emit()
