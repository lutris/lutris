"""Expose live cloud-save transfer snapshots to Qt Quick."""

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from lutris.backend import cloud_saves
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class CloudSaveController(QObject):
    changed = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._transfers: tuple[cloud_saves.CloudSaveTransfer, ...] = ()
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._refresh)
        self._registrations = (
            cloud_saves.CLOUD_SAVE_STARTED.register(self._refresh),
            cloud_saves.CLOUD_SAVE_ENDED.register(self._refresh),
        )

    @Property(list, notify=changed)
    def transfers(self) -> list[dict[str, str | float | bool]]:
        return [
            {"id": entry.id, "label": entry.label, "progress": entry.progress, "canSkip": entry.can_skip}
            for entry in self._transfers
        ]

    def _refresh(self, _transfer_id: str = "") -> None:
        start_task(self._load(), self._prompts.error)

    async def _load(self) -> None:
        transfers = await cloud_saves.list_transfers()
        if transfers and not self._timer.isActive():
            self._timer.start()
        elif not transfers:
            self._timer.stop()
        if transfers != self._transfers:
            self._transfers = transfers
            self.changed.emit()

    @Slot(str)
    def skip(self, transfer_id: str) -> None:
        start_task(cloud_saves.skip_transfer(transfer_id), self._prompts.error)

    def shutdown(self) -> None:
        self._timer.stop()
        for registration in self._registrations:
            registration.unregister()
