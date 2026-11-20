"""Expose a running installation's progress and questions to Qt Quick."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from lutris.backend import installations
from lutris.backend.models import InstallationInfo
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task
from lutris.util.notifications import NotificationRegistration

# How long log updates are gathered before the dialog's log is refreshed
LOG_REFRESH_MS = 200


class InstallationController(QObject):
    stateChanged = Signal()
    logChanged = Signal()
    launchRequested = Signal(str)

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._info: InstallationInfo | None = None
        self._starting = False
        self._start_task: asyncio.Task[None] | None = None
        self._log = ""
        self._default_shortcuts: tuple[str, ...] = ()
        self._registrations: list[NotificationRegistration] = []
        self._log_timer = QTimer(self)
        self._log_timer.setSingleShot(True)
        self._log_timer.setInterval(LOG_REFRESH_MS)
        self._log_timer.timeout.connect(self._refresh_log)
        start_task(self._load_defaults(), self._prompts.error)

    async def _load_defaults(self) -> None:
        self._default_shortcuts = await installations.get_default_shortcuts()
        self.stateChanged.emit()

    @Property(bool, notify=stateChanged)
    def active(self) -> bool:
        return self._starting or self._info is not None

    @Property(bool, notify=stateChanged)
    def running(self) -> bool:
        return self._starting or bool(self._info and self._info.running)

    @Property(str, notify=stateChanged)
    def stage(self) -> str:
        if self._info:
            return self._info.stage
        return "preparing" if self._starting else ""

    @Property(str, notify=stateChanged)
    def status(self) -> str:
        return self._info.status if self._info else ""

    @Property(bool, notify=stateChanged)
    def progressVisible(self) -> bool:  # noqa: N802
        return self._starting or bool(self._info and self._info.progress is not None)

    @Property(float, notify=stateChanged)
    def progress(self) -> float:
        if self._info and self._info.progress is not None:
            return self._info.progress
        return -1.0

    @Property(str, notify=stateChanged)
    def progressText(self) -> str:  # noqa: N802
        return self._info.progress_text if self._info else ""

    @Property(list, notify=stateChanged)
    def extras(self) -> list[dict[str, str]]:
        if not self._info:
            return []
        return [{"id": extra.id, "source": extra.source, "label": extra.label} for extra in self._info.extras]

    @Property(list, notify=stateChanged)
    def files(self) -> list[dict[str, Any]]:
        if not self._info:
            return []
        return [
            {
                "id": file.id,
                "label": file.label,
                "hint": file.hint,
                "details": file.details,
                "providers": list(file.providers),
                "provider": file.provider,
                "userPath": file.user_path,
                "ready": file.ready,
                "state": file.state,
                "fraction": file.fraction,
                "progressText": file.progress_text,
                "error": file.error,
            }
            for file in self._info.files
        ]

    @Property(bool, notify=stateChanged)
    def filesReady(self) -> bool:  # noqa: N802
        return bool(self._info and all(file.ready for file in self._info.files))

    @Property(list, notify=stateChanged)
    def menuOptions(self) -> list[dict[str, str]]:  # noqa: N802
        if not self._info:
            return []
        return [{"id": option.id, "label": option.label} for option in self._info.menu_options]

    @Property(int, notify=stateChanged)
    def menuPreselectIndex(self) -> int:  # noqa: N802
        if not self._info:
            return -1
        ids = [option.id for option in self._info.menu_options]
        return ids.index(self._info.menu_preselect) if self._info.menu_preselect in ids else -1

    @Property(bool, notify=stateChanged)
    def discCanEject(self) -> bool:  # noqa: N802
        return bool(self._info and self._info.disc_can_eject)

    @Property(str, notify=stateChanged)
    def runnerQuestion(self) -> str:  # noqa: N802
        return self._info.runner_prompt.question if self._info and self._info.runner_prompt else ""

    @Property(str, notify=stateChanged)
    def runnerFileTitle(self) -> str:  # noqa: N802
        return self._info.runner_prompt.file_title if self._info and self._info.runner_prompt else ""

    @Property(bool, notify=stateChanged)
    def hasLog(self) -> bool:  # noqa: N802
        return bool(self._info and self._info.has_log)

    @Property(str, notify=logChanged)
    def log(self) -> str:
        return self._log

    @Property(bool, notify=stateChanged)
    def canRemoveFiles(self) -> bool:  # noqa: N802
        return bool(self._info and self._info.can_remove_files)

    @Property(str, notify=stateChanged)
    def installedGameId(self) -> str:  # noqa: N802
        return self._info.game_id if self._info else ""

    @Property(str, notify=stateChanged)
    def errorDetails(self) -> str:  # noqa: N802
        return self._info.error_details if self._info else ""

    @Property(bool, notify=stateChanged)
    def desktopShortcutDefault(self) -> bool:  # noqa: N802
        return "desktop" in self._default_shortcuts

    @Property(bool, notify=stateChanged)
    def menuShortcutDefault(self) -> bool:  # noqa: N802
        return "menu" in self._default_shortcuts

    def start(self, catalog_id: str, choice_id: str, directory: str, shortcut_kinds: tuple[str, ...] | None) -> None:
        if self.active:
            return
        self._starting = True
        self._log = ""
        self._registrations = [
            installations.INSTALLATION_CHANGED.register(self._on_changed),
            installations.INSTALLATION_LOG_CHANGED.register(self._on_log_changed),
        ]
        self.stateChanged.emit()
        self.logChanged.emit()
        self._start_task = start_task(
            self._start(catalog_id, choice_id, directory, shortcut_kinds), self._prompts.error
        )

    async def _start(
        self, catalog_id: str, choice_id: str, directory: str, shortcut_kinds: tuple[str, ...] | None
    ) -> None:
        try:
            if shortcut_kinds is not None:
                await installations.set_default_shortcuts(shortcut_kinds)
                self._default_shortcuts = shortcut_kinds
            info = await installations.start_installation(catalog_id, choice_id, directory, shortcut_kinds or ())
        except BaseException:
            self._unregister()
            raise
        else:
            # Preserve a newer snapshot if the backend reported a change while starting
            if not self._info or self._info.id != info.id:
                self._info = info
        finally:
            self._starting = False
            self._start_task = None
            self.stateChanged.emit()

    def _on_changed(self, info: InstallationInfo) -> None:
        if self._starting and not self._info:
            self._info = info
        if self._info and info.id == self._info.id:
            self._info = info
            self.stateChanged.emit()

    def _on_log_changed(self, installation_id: str) -> None:
        if self._info and installation_id == self._info.id and not self._log_timer.isActive():
            self._log_timer.start()

    def _refresh_log(self) -> None:
        if self._info:
            start_task(self._load_log(self._info.id), self._prompts.error)

    async def _load_log(self, installation_id: str) -> None:
        text = await installations.get_installation_log(installation_id)
        if self._info and self._info.id == installation_id:
            self._log = text
            self.logChanged.emit()

    def _call(self, operation: Coroutine[Any, Any, None]) -> None:
        start_task(operation, self._prompts.error)

    def _id(self) -> str:
        return self._info.id if self._info else ""

    @Slot(list)
    def choose_extras(self, extra_ids: list[str]) -> None:
        if installation_id := self._id():
            self._call(installations.choose_extras(installation_id, [str(extra_id) for extra_id in extra_ids]))

    @Slot(str, str, str)
    def set_file_source(self, file_id: str, provider: str, path: str) -> None:
        if installation_id := self._id():
            self._call(installations.set_file_source(installation_id, file_id, provider, path))

    @Slot(str, QUrl)
    def choose_file(self, file_id: str, url: QUrl) -> None:
        self.set_file_source(file_id, "user", url.toLocalFile())

    @Slot()
    def start_files(self) -> None:
        if installation_id := self._id():
            self._call(installations.start_files(installation_id))

    @Slot(str)
    def retry_file(self, file_id: str) -> None:
        if installation_id := self._id():
            self._call(installations.retry_file(installation_id, file_id))

    @Slot(str)
    def answer_menu(self, option_id: str) -> None:
        if installation_id := self._id():
            self._call(installations.answer_menu(installation_id, option_id))

    @Slot(str)
    def answer_disc(self, path: str) -> None:
        if installation_id := self._id():
            self._call(installations.answer_disc(installation_id, path))

    @Slot(QUrl)
    def choose_disc(self, url: QUrl) -> None:
        self.answer_disc(url.toLocalFile())

    @Slot(bool)
    def answer_runner(self, accepted: bool) -> None:
        if (installation_id := self._id()) and self.stage == "runner_prompt":
            self._call(installations.answer_runner(installation_id, "yes" if accepted else None))

    @Slot(QUrl)
    def choose_runner_file(self, url: QUrl) -> None:
        if (installation_id := self._id()) and self.stage == "runner_prompt":
            self._call(installations.answer_runner(installation_id, url.toLocalFile() or None))

    @Slot()
    def eject_disc(self) -> None:
        if installation_id := self._id():
            self._call(installations.eject_disc(installation_id))

    @Slot(bool)
    def cancel(self, remove_files: bool) -> None:
        if installation_id := self._id():
            self._call(installations.cancel_installation(installation_id, remove_files))

    @Slot()
    def launch(self) -> None:
        if game_id := self.installedGameId:
            self.launchRequested.emit(game_id)

    @Slot()
    def close(self) -> None:
        """Forget the installation, cancelling it if it's still running."""
        if self._start_task:
            self._start_task.cancel()
            self._start_task = None
            self._starting = False
        self._unregister()
        self._log_timer.stop()
        if self._info:
            installation_id = self._info.id
            self._info = None
            start_task(installations.close_installation(installation_id), self._prompts.error)
        self._log = ""
        self.stateChanged.emit()
        self.logChanged.emit()

    def _unregister(self) -> None:
        for registration in self._registrations:
            registration.unregister()
        self._registrations = []
