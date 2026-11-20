"""Qt Quick library state and the commands that operate on it."""

import asyncio
from collections.abc import Coroutine
from gettext import gettext as _
from gettext import ngettext
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from lutris import settings
from lutris.backend import events, game_actions, games, installers, library, local_games, media
from lutris.backend.library import LibraryQuery, LibrarySort
from lutris.backend.models import GameInfo, LibraryGame
from lutris.exceptions import LutrisError
from lutris.qt.artwork_settings import ArtworkSettingsController
from lutris.qt.category_model import CategoryModel
from lutris.qt.configuration import ConfigController
from lutris.qt.delegates import PromptController, QtLaunchUIDelegate
from lutris.qt.game_log import GameLogController
from lutris.qt.game_maintenance import GameMaintenanceController
from lutris.qt.game_shortcuts import GameShortcutController
from lutris.qt.installers import InstallerController
from lutris.qt.library_model import LibraryModel
from lutris.qt.local_games import LocalGameController
from lutris.qt.preferences import PreferencesController
from lutris.qt.runner_manager import RunnerManagerController
from lutris.qt.runtime_updates import RuntimeUpdatesController
from lutris.qt.sidebar import ALL_GAMES, SidebarModel
from lutris.qt.tasks import start_task
from lutris.util import datapath

_LAYOUTS = {"covers", "banners", "list"}
_SORT_KEYS = {"name", "year", "lastplayed", "installed_at", "playtime"}


class LibraryController(QObject):
    libraryChanged = Signal()
    sidebarChanged = Signal()
    selectionChanged = Signal()
    layoutChanged = Signal()
    filterChanged = Signal()
    sortChanged = Signal()
    statusChanged = Signal()
    organizationChanged = Signal()

    def __init__(self, prompts: PromptController) -> None:
        super().__init__()
        self._prompts = prompts
        self.model = LibraryModel()
        self.sidebar = SidebarModel()
        self.categories = CategoryModel()
        self._log = GameLogController(prompts, self)
        self._maintenance = GameMaintenanceController(prompts, self)
        self._maintenance.stateChanged.connect(self.selectionChanged.emit)
        self._shortcuts = GameShortcutController(prompts, self)
        self._local_games = LocalGameController(prompts, self)
        self._local_games.registered.connect(self._on_local_game_registered)
        self._installers = InstallerController(prompts, self)
        self._configuration = ConfigController(prompts, self)
        self._artwork_settings = ArtworkSettingsController(prompts, self)
        # A new key can find artwork that stores didn't have
        self._artwork_settings.saved.connect(self.update_artwork)
        self._preferences = PreferencesController(prompts, self)
        self._preferences.sourcesChanged.connect(self._on_sources_changed)
        self._runner_manager = RunnerManagerController(prompts, self)
        self._runner_manager.runnersChanged.connect(self.refresh_sidebar)
        self.runtime_updates_controller = RuntimeUpdatesController(prompts, self)
        self._installers.installation_controller.launchRequested.connect(lambda game_id: self.launch(game_id, False))
        self.model.setParent(self)
        self.sidebar.setParent(self)
        self.categories.setParent(self)
        self._selected_row = -1
        self._sidebar_row = -1
        self._view: dict[str, str] = dict(ALL_GAMES)
        self._sort = LibrarySort(
            key=settings.read_setting("view_sorting", "name").removesuffix("_text"),
            reverse=settings.read_bool_setting("view_reverse_order"),
            installed_first=settings.read_bool_setting("view_sorting_installed_first", True),
        )
        if self._sort.key not in _SORT_KEYS:
            self._sort = LibrarySort(installed_first=self._sort.installed_first)
        self._search = ""
        self._installed_only = settings.read_bool_setting("filter_installed")
        saved_layout = settings.read_setting("qt_library_layout", "covers")
        self._layout = saved_layout if saved_layout in _LAYOUTS and settings.SHOW_MEDIA else "list"
        self._empty_text = ""
        self._status = ""
        self._running_ids: set[str] = set()
        self._launch_requests: set[str] = set()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._refresh_task: asyncio.Task[None] | None = None
        self._sidebar_task: asyncio.Task[None] | None = None
        self._organization_task: asyncio.Task[None] | None = None
        self._artwork_task: asyncio.Task[None] | None = None
        self._organization: game_actions.GameOrganization | None = None
        self._organization_game_id = ""
        self._closed = False
        self._refresh_timer = QTimer(self, singleShot=True, interval=250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._status_timer = QTimer(self, singleShot=True, interval=5000)
        self._status_timer.timeout.connect(lambda: self._set_status(""))
        self._registrations = [
            events.GAME_CHANGED.register(self._on_game_changed),
            events.GAME_INSTALLED.register(self._on_game_changed),
            events.GAME_REMOVED.register(self._on_game_removed),
            events.GAME_LAUNCHING.register(self._on_game_launching),
            events.GAME_STOPPED.register(self._on_game_stopped),
            events.GAME_FAILED.register(self._on_game_failed),
            events.CATEGORIES_CHANGED.register(self._on_categories_changed),
            events.SAVED_SEARCHES_CHANGED.register(self.refresh_sidebar),
            events.ARTWORK_CHANGED.register(self._on_artwork_changed),
        ]

    def start(self) -> asyncio.Task[None]:
        return self._start_task(self._load())

    def _start_task[T](self, coroutine: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = start_task(coroutine, self._prompts.error)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _load(self) -> None:
        self._running_ids = set(await games.list_running_game_ids())
        self.model.set_running_game_ids(self._running_ids | self._launch_requests)
        self.refresh_sidebar()
        self.refresh()

    @Property(QObject, constant=True)
    def gameLog(self) -> GameLogController:  # noqa: N802
        return self._log

    @Property(QObject, constant=True)
    def gameMaintenance(self) -> GameMaintenanceController:  # noqa: N802
        return self._maintenance

    @Property(QObject, constant=True)
    def gameShortcuts(self) -> GameShortcutController:  # noqa: N802
        return self._shortcuts

    @Property(QObject, constant=True)
    def localGames(self) -> LocalGameController:  # noqa: N802
        return self._local_games

    @Property(QObject, constant=True)
    def preferences(self) -> PreferencesController:
        return self._preferences

    @Property(QObject, constant=True)
    def runnerManager(self) -> RunnerManagerController:  # noqa: N802
        return self._runner_manager

    @Property(QObject, constant=True)
    def runtimeUpdates(self) -> RuntimeUpdatesController:  # noqa: N802
        return self.runtime_updates_controller

    @Property(QObject, constant=True)
    def artworkSettings(self) -> ArtworkSettingsController:  # noqa: N802
        return self._artwork_settings

    @Property(QObject, constant=True)
    def configuration(self) -> ConfigController:
        return self._configuration

    @Property(QObject, constant=True)
    def installers(self) -> InstallerController:
        return self._installers

    @Property(QObject, constant=True)
    def gamesModel(self) -> LibraryModel:  # noqa: N802
        return self.model

    @Property(QObject, constant=True)
    def sidebarModel(self) -> SidebarModel:  # noqa: N802
        return self.sidebar

    @Property(int, notify=libraryChanged)
    def gameCount(self) -> int:  # noqa: N802
        return self.model.rowCount()

    @Property(int, notify=selectionChanged)
    def selectedRow(self) -> int:  # noqa: N802
        return self._selected_row

    @Property(int, notify=sidebarChanged)
    def sidebarRow(self) -> int:  # noqa: N802
        return self._sidebar_row

    @Property(str, notify=layoutChanged)
    def layout(self) -> str:
        return self._layout

    @Property(bool, constant=True)
    def showMedia(self) -> bool:  # noqa: N802
        return settings.SHOW_MEDIA

    @Property(QUrl, constant=True)
    def placeholderArtwork(self) -> QUrl:  # noqa: N802
        return QUrl.fromLocalFile(str(Path(datapath.get()) / "media" / "default_icon.png"))

    @Property(bool, notify=filterChanged)
    def installedOnly(self) -> bool:  # noqa: N802
        return self._installed_only

    @Property(str, notify=sortChanged)
    def sortKey(self) -> str:  # noqa: N802
        return self._sort.key

    @Property(bool, notify=sortChanged)
    def sortReversed(self) -> bool:  # noqa: N802
        return self._sort.reverse

    @Property(str, notify=libraryChanged)
    def emptyText(self) -> str:  # noqa: N802
        return self._empty_text

    @Property(str, notify=libraryChanged)
    def searchHint(self) -> str:  # noqa: N802
        count = self.model.rowCount()
        return ngettext("Search %d game", "Search %d games", count) % count if count else _("Search games")

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:  # noqa: N802
        return self._status

    @Property(bool, notify=statusChanged)
    def updatingArtwork(self) -> bool:  # noqa: N802
        return self._artwork_task is not None and not self._artwork_task.done()

    @property
    def selected_game(self) -> LibraryGame | None:
        return self.model.game_at(self._selected_row)

    @Property(str, notify=selectionChanged)
    def selectedGameName(self) -> str:  # noqa: N802
        game = self.selected_game
        return game.name if game else ""

    @Property(bool, notify=selectionChanged)
    def selectedGameInstalled(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(game and game.installed)

    @Property(bool, notify=selectionChanged)
    def canLinkLocalGame(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(
            game
            and self._can_maintain(game.game_id)
            and local_games.can_link_linux_game(game.installed, game.runner, game.service)
        )

    @Property(bool, notify=selectionChanged)
    def canInstall(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(
            game
            and self._can_maintain(game.game_id)
            and installers.can_install_game(game.installed, game.slug, game.service)
        )

    @Property(bool, notify=selectionChanged)
    def canPlay(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(game and game.installed and self._can_maintain(game.game_id))

    @Property(bool, notify=selectionChanged)
    def canMaintain(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(game and self._can_maintain(game.game_id))

    def _can_maintain(self, game_id: str | None) -> bool:
        return bool(game_id and not self._is_running(game_id) and not self._maintenance.is_working)

    @Property(bool, notify=selectionChanged)
    def canStop(self) -> bool:  # noqa: N802
        game = self.selected_game
        return bool(game and game.game_id and game.game_id in self._running_ids)

    @Property(str, notify=selectionChanged)
    def selectedGameId(self) -> str:  # noqa: N802
        game = self.selected_game
        return game.game_id or "" if game else ""

    @Property(QObject, constant=True)
    def categoryModel(self) -> CategoryModel:  # noqa: N802
        return self.categories

    @Property(bool, notify=organizationChanged)
    def organizationReady(self) -> bool:  # noqa: N802
        return self._organization is not None

    @Property(bool, notify=organizationChanged)
    def favorite(self) -> bool:
        return bool(self._organization and self._organization.favorite)

    @Property(bool, notify=organizationChanged)
    def hidden(self) -> bool:
        return bool(self._organization and self._organization.hidden)

    @Slot(str)
    def set_search(self, text: str) -> None:
        self._search = text
        self._refresh_timer.start()

    @Slot(bool)
    def set_installed_only(self, installed_only: bool) -> None:
        self._installed_only = installed_only
        settings.write_setting("filter_installed", installed_only)
        self.filterChanged.emit()
        self.refresh()

    @Slot(str)
    def set_layout(self, layout: str) -> None:
        if layout not in _LAYOUTS or layout == self._layout or not settings.SHOW_MEDIA:
            return
        needs_artwork = self._layout == "list" and layout != "list"
        self._layout = layout
        settings.write_setting("qt_library_layout", layout)
        self.layoutChanged.emit()
        if needs_artwork:
            self.refresh()

    @Slot(str)
    def set_sort(self, key: str) -> None:
        if key in _SORT_KEYS and key != self._sort.key:
            self._set_sort(key, False)

    @Slot()
    def reverse_sort(self) -> None:
        self._set_sort(self._sort.key, not self._sort.reverse)

    @Slot(str)
    def sort_by_column(self, key: str) -> None:
        if key in _SORT_KEYS:
            self._set_sort(key, key == self._sort.key and not self._sort.reverse)

    def _set_sort(self, key: str, reverse: bool) -> None:
        self._sort = LibrarySort(key, reverse, self._sort.installed_first)
        settings.write_setting("view_sorting", key)
        settings.write_setting("view_reverse_order", reverse)
        self.sortChanged.emit()
        self.refresh()

    @Slot(int)
    def select_game(self, row: int) -> None:
        if row != self._selected_row and self.model.game_at(row):
            self._selected_row = row
            self.selectionChanged.emit()

    @Slot(int)
    def select_view(self, row: int) -> None:
        view = self.sidebar.view_at(row)
        if view is not None and view != self._view:
            self._view = view
            self._sidebar_row = row
            self.sidebarChanged.emit()
            self._selected_row = -1
            self.selectionChanged.emit()
            self.refresh()

    def refresh(self) -> None:
        if self._closed:
            return
        self._refresh_timer.stop()
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        self._refresh_task = self._start_task(self._refresh())

    async def _refresh(self) -> None:
        query = LibraryQuery(
            text=self._search.strip(),
            installed_only=self._installed_only,
            running_game_ids=tuple(self._running_ids | self._launch_requests),
            sort=self._sort,
            include_artwork=self._layout != "list",
            **self._view,  # type: ignore[arg-type]
        )
        rows = await library.query_games(query)
        self._empty_text = await self._get_empty_text(query) if not rows else ""
        selected = self.selected_game
        self.model.set_games(rows)
        self._selected_row = self.model.find_row(selected.id) if selected else -1
        self.selectionChanged.emit()
        self.libraryChanged.emit()

    async def _get_empty_text(self, query: LibraryQuery) -> str:
        if query.text:
            return _("No games matching '%s' found.") % query.text
        if query.category == "favorite":
            return _("Add games to your favorites to see them here.")
        if query.category == ".hidden":
            return _("No games are hidden.")
        if query.installed_only and await library.has_uninstalled_games():
            return _("No installed games found. Uncheck 'Installed only' to show the others.")
        if query.service:
            return _("No games found. If this service needs you to log in, the GTK version of Lutris can do that.")
        return _("No games found")

    def refresh_sidebar(self) -> None:
        if self._closed:
            return
        if self._sidebar_task and not self._sidebar_task.done():
            self._sidebar_task.cancel()
        self._sidebar_task = self._start_task(self._refresh_sidebar())

    async def _refresh_sidebar(self) -> None:
        await self.sidebar.refresh()
        self._sidebar_row = self.sidebar.find_row(self._view)
        if self._sidebar_row < 0:
            self.select_view(self.sidebar.find_row(ALL_GAMES))
        self.sidebarChanged.emit()

    def _on_artwork_changed(self) -> None:
        if not self._closed and self._layout != "list":
            self.model.invalidate_artwork()
            self._refresh_timer.start()

    @Slot()
    def update_artwork(self, quiet: bool = False) -> None:
        if not self.updatingArtwork:
            self._artwork_task = self._start_task(self._update_artwork(quiet))
            self._artwork_task.add_done_callback(lambda _: self.statusChanged.emit())
            if not quiet:
                self._status_timer.stop()
                self._set_status(_("Updating artwork…"))

    async def _update_artwork(self, quiet: bool) -> None:
        try:
            count = await media.update_artwork()
        except Exception:
            self._set_status("")
            raise
        if quiet and not count:
            return
        message = (
            ngettext("Downloaded %d image", "Downloaded %d images", count) % count
            if count
            else _("No new artwork found")
        )
        self._set_status(message)
        self._status_timer.start()

    def _set_status(self, message: str) -> None:
        self._status = message
        self.statusChanged.emit()

    def _on_sources_changed(self) -> None:
        if not self._closed:
            self.refresh_sidebar()
            self.refresh()

    def _on_local_game_registered(self, name: str) -> None:
        self._set_status(_("Registered %s in the library.") % name)
        self._status_timer.start()

    def _is_running(self, game_id: str) -> bool:
        return game_id in self._running_ids or game_id in self._launch_requests

    @Slot()
    def play(self) -> None:
        game = self.selected_game
        if game and game.game_id and game.installed:
            self.launch(game.game_id, False)

    @Slot(str, bool)
    def launch(self, game_id: str, choose_again: bool) -> None:
        if not self._can_maintain(game_id):
            return
        self._launch_requests.add(game_id)
        self._update_running_state()
        self._start_task(self._launch(game_id, choose_again))

    async def _launch(self, game_id: str, choose_again: bool) -> None:
        try:
            if await games.launch_game(game_id, QtLaunchUIDelegate(self._prompts, choose_again=choose_again)):
                self._running_ids.add(game_id)
        finally:
            self._launch_requests.discard(game_id)
            self._update_running_state()

    @Slot()
    def stop(self) -> None:
        game = self.selected_game
        if game and game.game_id and game.game_id in self._running_ids:
            self._start_task(games.stop_game(game.game_id))

    def _on_game_changed(self, _game: GameInfo) -> None:
        if not self._closed:
            self._refresh_timer.start()

    def _on_game_removed(self, _game_id: str) -> None:
        if not self._closed:
            self._refresh_timer.start()

    def _on_game_launching(self, game: GameInfo) -> None:
        self._running_ids.add(game.id)
        self._update_running_state()

    def _on_game_stopped(self, game: GameInfo) -> None:
        self._running_ids.discard(game.id)
        self._update_running_state()

    def _update_running_state(self) -> None:
        if not self._closed:
            self.model.set_running_game_ids(self._running_ids | self._launch_requests)
            self.selectionChanged.emit()
            if self._view.get("dynamic_category") == "running":
                self.refresh()

    def _on_game_failed(self, _game_id: str, error: BaseException) -> None:
        if not self._closed:
            self._prompts.error(error)

    def _on_categories_changed(self) -> None:
        self.refresh_sidebar()
        self.refresh()

    @Slot(str)
    def load_organization(self, game_id: str) -> None:
        if self._organization_task and not self._organization_task.done():
            self._organization_task.cancel()
        self._organization = None
        self.categories.set_memberships(())
        self._organization_game_id = game_id
        self.organizationChanged.emit()
        if game_id:
            self._organization_task = self._start_task(self._load_organization(game_id))

    async def _load_organization(self, game_id: str) -> None:
        self._organization = await game_actions.get_organization(game_id)
        self.categories.set_memberships(self._organization.categories)
        self.organizationChanged.emit()

    @Slot(str, bool)
    def set_favorite(self, game_id: str, favorite: bool) -> None:
        self._start_task(game_actions.set_favorite(game_id, favorite))

    @Slot(str, bool)
    def set_hidden(self, game_id: str, hidden: bool) -> None:
        self._start_task(game_actions.set_hidden(game_id, hidden))

    @Slot(str, str, bool)
    def set_category(self, game_id: str, name: str, included: bool) -> None:
        self._start_task(self._set_category(game_id, name, included))

    async def _set_category(self, game_id: str, name: str, included: bool) -> None:
        await game_actions.set_category(game_id, name, included)
        if self._organization_game_id == game_id:
            if self._organization_task and not self._organization_task.done():
                self._organization_task.cancel()
            self._organization_task = self._start_task(self._load_organization(game_id))

    @Slot(str)
    def browse_files(self, game_id: str) -> None:
        self._start_task(self._browse_files(game_id))

    async def _browse_files(self, game_id: str) -> None:
        directory = await game_actions.get_installation_directory(game_id)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(directory)):
            raise LutrisError(_("Could not open %s") % directory)

    def shutdown(self) -> None:
        self._closed = True
        self.runtime_updates_controller.shutdown()
        self._log.close_log()
        self._maintenance.close_maintenance()
        for registration in self._registrations:
            registration.unregister()
        self._refresh_timer.stop()
        self._status_timer.stop()
        for task in self._tasks:
            task.cancel()
