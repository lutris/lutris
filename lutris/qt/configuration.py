"""Expose game, runner and system configuration forms to Qt Quick."""

from collections.abc import Coroutine
from dataclasses import replace
from gettext import gettext as _
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from lutris.backend import configuration
from lutris.backend.models import ConfigForm, ConfigOptionInfo, ConfigPage
from lutris.qt.config_model import ConfigOptionModel
from lutris.qt.delegates import PromptController
from lutris.qt.game_artwork import GameArtworkController
from lutris.qt.game_maintenance import GameMaintenanceController
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
        self._game_id = ""
        self._registration: NotificationRegistration | None = None
        self.model = ConfigOptionModel()
        self.model.setParent(self)
        self.artwork_controller = GameArtworkController(prompts, self)
        self._maintenance = GameMaintenanceController(prompts, self)
        self._maintenance.finished.connect(self._reload_moved_game)

    @Property(QObject, constant=True)
    def maintenance(self) -> GameMaintenanceController:
        return self._maintenance

    @Property(QObject, constant=True)
    def artwork(self) -> GameArtworkController:
        return self.artwork_controller

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
        return self._page_titles()

    def _page_titles(self) -> list[str]:
        if not self._form:
            return []
        titles = [page.title for page in self._form.pages]
        return [_("Game info"), *titles] if self._form.game else titles

    @Property(int, notify=stateChanged)
    def page(self) -> int:
        return self._page

    @Property(bool, notify=stateChanged)
    def infoPage(self) -> bool:  # noqa: N802
        return bool(self._form and self._form.game and self._page == 0)

    @Property(str, notify=stateChanged)
    def pageDescription(self) -> str:  # noqa: N802
        if page := self._option_page():
            return page.description
        return ""

    @Property(bool, notify=stateChanged)
    def isGame(self) -> bool:  # noqa: N802
        return bool(self._form and self._form.game)

    @Property(bool, notify=stateChanged)
    def isNewGame(self) -> bool:  # noqa: N802
        return bool(self._form and self._form.game and not self._game_id)

    @Property(dict, notify=stateChanged)
    def game(self) -> dict[str, str]:
        details = self._form.game if self._form else None
        if not details:
            return {}
        return {
            "name": details.name,
            "sortname": details.sortname,
            "slug": details.slug,
            "runner": details.runner,
            "year": details.year,
            "playtime": details.playtime,
            "directory": details.directory,
            "configPath": details.config_path,
            "preferredLaunch": details.preferred_launch,
        }

    @Slot()
    def open_config_folder(self) -> None:
        if self._form and (details := self._form.game) and details.config_path:
            directory = str(Path(details.config_path).parent)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(directory)):
                self._prompts.error(RuntimeError(_("Could not open %s") % directory))

    @Slot(result=bool)
    def prepare_move(self) -> bool:
        if not self._game_id or self._modified or self._busy:
            return False
        self._maintenance.open_maintenance(self._game_id)
        return True

    def _reload_moved_game(self) -> None:
        if self._form and self._form.game and self._game_id:
            self.open_game(self._game_id, self._form.game.name)

    @Slot()
    def reset_preferred_launch(self) -> None:
        if self._form and self._form.game:
            self._modified = True
            self._run(configuration.reset_preferred_launch(self._form.id))

    @Property(list, notify=stateChanged)
    def runnerChoices(self) -> list[dict[str, str]]:  # noqa: N802
        if not self._form:
            return []
        choices = [{"label": _("Select a runner from the list"), "value": ""}]
        return choices + [{"label": choice.label, "value": choice.value} for choice in self._form.runner_choices]

    @Property(bool, notify=stateChanged)
    def showAdvanced(self) -> bool:  # noqa: N802
        return self._show_advanced

    @Property(str, notify=stateChanged)
    def emptyText(self) -> str:  # noqa: N802
        if not self._form or self.model.rowCount() or self.infoPage:
            return ""
        if self._search:
            return _("No options match '%s'") % self._search
        if not self._show_advanced and self._visible_options(include_advanced=True):
            return _("Only advanced options available")
        if self._form.game and not self._form.game.runner:
            return _("Select a runner in the Game info tab")
        return _("No options available")

    @Slot(str, str)
    def open_game(self, game_id: str, game_name: str) -> None:
        self._open(configuration.open_game_config(game_id), game_name)
        self._game_id = game_id

    @Slot()
    def open_new_game(self) -> None:
        self._open(configuration.open_new_game_config(), _("Add a new game"))

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
        self.artwork_controller.open_game(self._game_id)

    def _on_form_changed(self, form_id: str) -> None:
        if self._form and form_id == self._form.id:
            self._run(configuration.get_config_form(form_id))

    @Slot(int)
    def select_page(self, page: int) -> None:
        if self._form and 0 <= page < len(self._page_titles()) and page != self._page:
            self._page = page
            self._refresh()

    @Slot(str, str)
    def set_detail(self, field: str, value: str) -> None:
        """Change one of a game's details: name, sortname, slug, year or playtime."""
        details = self._form.game if self._form else None
        if not self._form or not details or field not in ("name", "sortname", "slug", "year", "playtime"):
            return
        if getattr(details, field) != value:
            self._modified = True
            self._run(configuration.set_game_details(self._form.id, replace(details, **{field: value})))

    @Slot(str)
    def set_runner(self, runner_name: str) -> None:
        if self._form and self._form.game and runner_name != self._form.game.runner:
            self._modified = True
            self._run(configuration.set_game_runner(self._form.id, runner_name))

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
            self._game_id = await configuration.save_config(form_id) or self._game_id
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
        self._game_id = ""
        self.artwork_controller.open_game("")
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
        self._page = min(self._page, max(len(self._page_titles()) - 1, 0))
        self._refresh()

    def _option_page(self) -> ConfigPage | None:
        if not self._form:
            return None
        index = self._page - 1 if self._form.game else self._page
        return self._form.pages[index] if 0 <= index < len(self._form.pages) else None

    def _visible_options(self, include_advanced: bool = False) -> list[ConfigOptionInfo]:
        page = self._option_page()
        if not page:
            return []
        search = self._search.casefold()
        return [
            option
            for option in page.options
            if option.visible
            and (include_advanced or self._show_advanced or not option.advanced)
            and (not search or search in option.label.casefold() or search in option.help.casefold())
        ]

    def _refresh(self) -> None:
        self.model.set_options(self._visible_options())
        self.stateChanged.emit()
