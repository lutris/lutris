"""Expose game, runner and system configuration forms to Qt Quick."""

from collections.abc import Coroutine
from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from lutris.backend import configuration
from lutris.backend.models import ConfigForm, ConfigOptionInfo
from lutris.qt.config_model import ConfigOptionModel
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task
from lutris.util.notifications import NotificationRegistration


class ConfigController(QObject):
    requested = Signal()
    stateChanged = Signal()
    closeRequested = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._form: ConfigForm | None = None
        self._page = 0
        self._search = ""
        self._show_advanced = False
        self._modified = False
        self._busy = False
        self._title = ""
        self._registration: NotificationRegistration | None = None
        self.model = ConfigOptionModel()
        self.model.setParent(self)

    @Property(QObject, constant=True)
    def options(self) -> ConfigOptionModel:
        return self.model

    @Property(bool, notify=stateChanged)
    def ready(self) -> bool:
        return self._form is not None

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=stateChanged)
    def modified(self) -> bool:
        return self._modified

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return self._form.title if self._form else self._title

    @Property(list, notify=stateChanged)
    def pages(self) -> list[str]:
        return [page.title for page in self._form.pages] if self._form else []

    @Property(int, notify=stateChanged)
    def page(self) -> int:
        return self._page

    @Property(str, notify=stateChanged)
    def pageDescription(self) -> str:  # noqa: N802
        if self._form and self._page < len(self._form.pages):
            return self._form.pages[self._page].description
        return ""

    @Property(bool, notify=stateChanged)
    def showAdvanced(self) -> bool:  # noqa: N802
        return self._show_advanced

    @Property(str, notify=stateChanged)
    def emptyText(self) -> str:  # noqa: N802
        if not self._form or self.model.rowCount():
            return ""
        if self._search:
            return _("No options match '%s'") % self._search
        if not self._show_advanced and self._visible_options(include_advanced=True):
            return _("Only advanced options available")
        return _("No options available")

    @Slot(str, str)
    def open_game(self, game_id: str, game_name: str) -> None:
        self._open(configuration.open_game_config(game_id), game_name)

    @Slot(str, str)
    def open_runner(self, runner_name: str, human_name: str) -> None:
        self._open(configuration.open_runner_config(runner_name), human_name)

    @Slot()
    def open_system(self) -> None:
        self._open(configuration.open_system_config(), "")

    def _open(self, request: Coroutine[Any, Any, ConfigForm], title: str) -> None:
        if self._busy:
            request.close()
            return
        self.close()
        self._title = title
        self._busy = True
        self._registration = configuration.CONFIG_FORM_CHANGED.register(self._on_form_changed)
        self.stateChanged.emit()
        self.requested.emit()
        start_task(self._load(request), self._prompts.error)

    async def _load(self, request: Coroutine[Any, Any, ConfigForm]) -> None:
        try:
            form = await request
        except Exception:
            self.closeRequested.emit()
            raise
        finally:
            self._busy = False
        self._show_advanced = form.show_advanced
        self._apply(form)

    def _on_form_changed(self, form_id: str) -> None:
        if self._form and form_id == self._form.id:
            self._run(configuration.get_config_form(form_id))

    @Slot(int)
    def select_page(self, page: int) -> None:
        if self._form and 0 <= page < len(self._form.pages) and page != self._page:
            self._page = page
            self._refresh()

    @Slot(str)
    def set_search(self, text: str) -> None:
        if text != self._search:
            self._search = text
            self._refresh()

    @Slot(bool)
    def set_show_advanced(self, show: bool) -> None:
        if show != self._show_advanced:
            self._show_advanced = show
            start_task(configuration.set_show_advanced(show), self._prompts.error)
            self._refresh()

    @Slot(str, str, "QVariant")
    def set_value(self, section: str, key: str, value: Any) -> None:
        if self._form:
            self._modified = True
            self._run(configuration.set_option(self._form.id, section, key, value))

    @Slot(str, str, list)
    def set_mapping(self, section: str, key: str, rows: list[dict[str, str]]) -> None:
        mapping = {str(row.get("name", "")): str(row.get("value", "")) for row in rows}
        self.set_value(section, key, mapping)

    @Slot(str, str)
    def reset(self, section: str, key: str) -> None:
        if self._form:
            self._modified = True
            self._run(configuration.reset_option(self._form.id, section, key))

    @Slot(QUrl, result=str)
    def local_path(self, url: QUrl) -> str:
        return url.toLocalFile()

    @Slot(list, result=list)
    def local_paths(self, urls: list[QUrl]) -> list[str]:
        return [QUrl(url).toLocalFile() for url in urls]

    @Slot()
    def save(self) -> None:
        if self._form and not self._busy:
            self._busy = True
            self.stateChanged.emit()
            start_task(self._save(self._form.id), self._prompts.error)

    async def _save(self, form_id: str) -> None:
        try:
            await configuration.save_config(form_id)
        finally:
            self._busy = False
            self.stateChanged.emit()
        self._modified = False
        self.closeRequested.emit()

    @Slot()
    def close(self) -> None:
        """Forget the form, discarding unsaved changes."""
        if self._registration:
            self._registration.unregister()
            self._registration = None
        if self._form:
            start_task(configuration.close_config(self._form.id), self._prompts.error)
        self._form = None
        self._page = 0
        self._search = ""
        self._modified = False
        self.model.set_options([])
        self.stateChanged.emit()

    def _run(self, request: Coroutine[Any, Any, ConfigForm]) -> None:
        start_task(self._update(request), self._prompts.error)

    async def _update(self, request: Coroutine[Any, Any, ConfigForm]) -> None:
        form = await request
        if self._form and form.id == self._form.id:
            self._apply(form)

    def _apply(self, form: ConfigForm) -> None:
        self._form = form
        self._page = min(self._page, max(len(form.pages) - 1, 0))
        self._refresh()

    def _visible_options(self, include_advanced: bool = False) -> list[ConfigOptionInfo]:
        if not self._form or self._page >= len(self._form.pages):
            return []
        search = self._search.casefold()
        return [
            option
            for option in self._form.pages[self._page].options
            if option.visible
            and (include_advanced or self._show_advanced or not option.advanced)
            and (not search or search in option.label.casefold() or search in option.help.casefold())
        ]

    def _refresh(self) -> None:
        self.model.set_options(self._visible_options())
        self.stateChanged.emit()
