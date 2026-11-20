"""Run runtime updates for Qt Quick and show how far they've got."""

from gettext import gettext as _

from PySide6.QtCore import Property, QObject, Signal, Slot

from lutris.backend import runtime_updates
from lutris.backend.models import RuntimeUpdateStatus
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task
from lutris.util.notifications import NotificationRegistration


class RuntimeUpdatesController(QObject):
    stateChanged = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._status = RuntimeUpdateStatus(running=False)
        self._result = ""
        self._auto_update = True
        self._registration: NotificationRegistration | None = runtime_updates.RUNTIME_UPDATE_CHANGED.register(
            self._on_changed
        )
        start_task(self._load(), self._prompts.error)

    async def _load(self) -> None:
        self._auto_update = await runtime_updates.is_auto_update_enabled()
        self.stateChanged.emit()

    @Property(bool, notify=stateChanged)
    def running(self) -> bool:
        return self._status.running

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:  # noqa: N802
        """What's being updated, or how the last update ended."""
        if not self._status.running:
            return self._result
        active = [component for component in self._status.components if not component.finished]
        if not active:
            return _("Updating the runtime…")
        component = active[0]
        if component.fraction is None:
            return component.status
        return _("%(status)s (%(percent)d%%)") % {"status": component.status, "percent": component.fraction * 100}

    @Property(bool, notify=stateChanged)
    def autoUpdate(self) -> bool:  # noqa: N802
        return self._auto_update

    @Slot(bool)
    def set_auto_update(self, enabled: bool) -> None:
        self._auto_update = enabled
        self.stateChanged.emit()
        start_task(runtime_updates.set_auto_update_enabled(enabled), self._prompts.error)

    @Slot()
    def check(self) -> None:
        """Check for updates now, whatever the last check found."""
        self.update(force=True)

    def update(self, force: bool = False) -> None:
        if not self._status.running:
            self._result = _("Checking for runtime updates…") if force else ""
            self.stateChanged.emit()
            start_task(self._update(force), self._prompts.error)

    async def _update(self, force: bool) -> None:
        try:
            updated = await runtime_updates.update_runtime(force=force)
        except Exception:
            self._result = _("The runtime could not be updated.")
            self.stateChanged.emit()
            raise
        if updated:
            self._result = _("Updated %s.") % ", ".join(updated)
        elif force:
            self._result = _("The runtime is up to date.")
        self.stateChanged.emit()

    def _on_changed(self, status: RuntimeUpdateStatus) -> None:
        self._status = status
        self.stateChanged.emit()

    def shutdown(self) -> None:
        if self._registration:
            self._registration.unregister()
            self._registration = None
