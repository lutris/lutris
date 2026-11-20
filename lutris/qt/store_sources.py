"""Expose game sources and host-browser sign-in to Qt Quick."""

import asyncio
from collections.abc import Coroutine
from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from lutris.backend import services, store_login
from lutris.exceptions import LutrisError
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task


class StoreSourcesController(QObject):
    changed = Signal()
    gamesChanged = Signal()
    loginRequested = Signal()
    loginClosed = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._source = ""
        self._info: services.SourceStatus | None = None
        self._request: store_login.BrowserLogin | None = None
        self._task: asyncio.Task[None] | None = None
        self._error = ""

    @Property(dict, notify=changed)
    def source(self) -> dict[str, str | bool]:
        info = self._info
        if not info:
            return {}
        return {
            "name": info.name,
            "online": info.online,
            "signedIn": info.signed_in,
            "canSignIn": info.can_sign_in,
        }

    @Property(dict, notify=changed)
    def login(self) -> dict[str, str]:
        request = self._request
        return {"name": request.name, "inputKind": request.input_kind} if request else {}

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._task is not None

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error

    def select(self, service_id: str) -> None:
        self._source = service_id
        self._info = None
        self.changed.emit()
        if service_id:
            start_task(self._load(service_id), self._prompts.error)

    async def _load(self, service_id: str) -> None:
        info = await services.get_source_status(service_id)
        if service_id == self._source:
            self._info = info
            self.changed.emit()

    @Slot()
    def sign_in(self) -> None:
        if self._info and self._info.can_sign_in and not self._info.signed_in and not self._request and not self._task:
            self._start(self._begin(self._source))

    async def _begin(self, service_id: str) -> None:
        request = await store_login.begin(service_id)
        if self._source != service_id:
            await store_login.cancel(request.id)
            return
        self._request = request
        self._error = ""
        self.loginRequested.emit()

    @Slot()
    def open_browser(self) -> None:
        if self._request and not QDesktopServices.openUrl(QUrl(self._request.url)):
            self._error = _("Could not open your default browser.")
            self.changed.emit()

    @Slot(str)
    def submit(self, text: str) -> None:
        if self._request and not self._task:
            self._start(self._submit(self._source, self._request.id, text))

    @Slot(QUrl, str)
    def submit_cookie_file(self, url: QUrl, redirect: str) -> None:
        if self._request and not self._task and url.isLocalFile():
            if self._request.input_kind == "cookies":
                self.submit(url.toLocalFile())
            elif self._request.input_kind == "gog":
                self._start(self._submit(self._source, self._request.id, redirect, url.toLocalFile()))

    async def _submit(self, service_id: str, request_id: str, text: str, cookie_file: str = "") -> None:
        try:
            await store_login.finish(request_id, text, cookie_file)
        except LutrisError as error:
            self._error = error.message
            return
        self._request = None
        self.loginClosed.emit()
        await self._reload(service_id)

    @Slot()
    def close_login(self) -> None:
        if self._request and not self._task:
            request, self._request = self._request, None
            start_task(store_login.cancel(request.id), self._prompts.error)
            self.changed.emit()

    @Slot()
    def sync(self) -> None:
        if self._info and (not self._info.online or self._info.signed_in) and not self._task:
            self._start(self._reload(self._source))

    async def _reload(self, service_id: str) -> None:
        try:
            await services.sync_source(service_id)
        finally:
            await self._load(service_id)
            self.gamesChanged.emit()

    @Slot()
    def disconnect_store(self) -> None:
        if self._info and self._info.signed_in and not self._task:
            self._start(self._disconnect(self._source))

    async def _disconnect(self, service_id: str) -> None:
        await services.disconnect_source(service_id)
        await self._load(service_id)
        self.gamesChanged.emit()

    def _start(self, operation: Coroutine[Any, Any, None]) -> None:
        self._task = start_task(self._run(operation), self._prompts.error)
        self.changed.emit()

    async def _run(self, operation: Coroutine[Any, Any, None]) -> None:
        try:
            await operation
        finally:
            self._task = None
            self.changed.emit()
