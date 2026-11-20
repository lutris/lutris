"""The Qt frontend's main window: the library."""

import asyncio
from gettext import gettext as _
from gettext import ngettext
from typing import Any

from PySide6.QtCore import QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QTableView,
    QToolBar,
)

from lutris import settings
from lutris.backend import events, games, library
from lutris.backend.library import LibraryQuery, LibrarySort
from lutris.backend.models import GameInfo, LibraryGame
from lutris.qt.delegates import QtLaunchUIDelegate
from lutris.qt.library_model import COLUMNS, GameRole, LibraryModel
from lutris.qt.sidebar import ALL_GAMES, Sidebar
from lutris.qt.tasks import show_error, start_task
from lutris.util.notifications import NotificationRegistration

# How long typing in the search field pauses before the view follows it, in milliseconds
SEARCH_DELAY_MS = 250


class MainWindow(QMainWindow):
    """Lists the library's games, by the view the sidebar selects, and launches them."""

    # Emitted when the window closes
    closed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lutris")
        self.resize(1100, 700)
        self.launch_ui_delegate = QtLaunchUIDelegate(self)

        self._view: dict[str, str] = dict(ALL_GAMES)
        self._running_game_ids: set[str] = set()
        self._refresh_task: asyncio.Task[None] | None = None
        self._refresh_timer = QTimer(self, singleShot=True, interval=SEARCH_DELAY_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        self.sidebar = Sidebar()
        self.sidebar.view_selected.connect(self.on_view_selected)

        self.model = LibraryModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)  # The backend sorts; the header only picks how
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self.on_header_clicked)
        self.table.doubleClicked.connect(self.on_game_activated)
        self.table.selectionModel().selectionChanged.connect(lambda *_args: self.update_actions())

        self.empty_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.games_stack = QStackedWidget()
        self.games_stack.addWidget(self.table)
        self.games_stack.addWidget(self.empty_label)

        splitter = QSplitter()
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.games_stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 880])
        self.setCentralWidget(splitter)

        self.search_entry = QLineEdit(placeholderText=_("Search games"), clearButtonEnabled=True)
        self.search_entry.textChanged.connect(lambda _text: self._refresh_timer.start())
        self.installed_check = QCheckBox(_("Installed only"))
        self.installed_check.setChecked(settings.read_bool_setting("filter_installed"))
        self.installed_check.toggled.connect(self.on_installed_toggled)
        self.play_action = QAction(_("Play"), self)
        self.play_action.triggered.connect(self.on_play)
        self.stop_action = QAction(_("Stop"), self)
        self.stop_action.triggered.connect(self.on_stop)
        focus_search = QAction(self)
        focus_search.setShortcut(QKeySequence.StandardKey.Find)
        focus_search.triggered.connect(lambda: self.search_entry.setFocus())
        self.addAction(focus_search)

        toolbar = QToolBar(movable=False)
        toolbar.addAction(self.play_action)
        toolbar.addAction(self.stop_action)
        toolbar.addSeparator()
        toolbar.addWidget(self.search_entry)
        toolbar.addWidget(self.installed_check)
        self.addToolBar(toolbar)

        self._registrations: list[NotificationRegistration] = [
            events.GAME_CHANGED.register(self.on_game_changed),
            events.GAME_INSTALLED.register(self.on_game_changed),
            events.GAME_LAUNCHING.register(self.on_game_launching),
            events.GAME_STOPPED.register(self.on_game_stopped),
            events.GAME_FAILED.register(self.on_game_failed),
            events.CATEGORIES_CHANGED.register(self.refresh_sidebar),
            events.SAVED_SEARCHES_CHANGED.register(self.refresh_sidebar),
        ]
        self.update_sort_indicator()
        self.update_actions()
        start_task(self.load(), self)

    async def load(self) -> None:
        self._running_game_ids = set(await games.list_running_game_ids())
        self.model.set_running_game_ids(self._running_game_ids)
        await self.sidebar.refresh()
        self.refresh()

    @property
    def sort(self) -> LibrarySort:
        key = settings.read_setting("view_sorting") or "name"
        return LibrarySort(
            # Older versions of Lutris saved the name of the column showing the value
            key=key.removesuffix("_text"),
            reverse=settings.read_bool_setting("view_reverse_order"),
            installed_first=settings.read_bool_setting("view_sorting_installed_first", True),
        )

    def get_query(self) -> LibraryQuery:
        """Return the query for the games the window shows now."""
        return LibraryQuery(
            text=self.search_entry.text().strip(),
            installed_only=self.installed_check.isChecked(),
            running_game_ids=tuple(self._running_game_ids),
            sort=self.sort,
            **self._view,  # type: ignore[arg-type]
        )

    def refresh(self) -> None:
        """Show the games the view selects, replacing any refresh in progress."""
        if self._refresh_task:
            self._refresh_task.cancel()
        self._refresh_task = start_task(self._refresh(), self)

    async def _refresh(self) -> None:
        query = self.get_query()
        selected = self.get_selected_game()
        game_list = await library.query_games(query)
        self.model.set_games(game_list)
        if selected:
            row = self.model.find_row(selected.id)
            if row is not None:
                self.table.selectRow(row)

        if game_list:
            self.games_stack.setCurrentWidget(self.table)
        else:
            self.empty_label.setText(await self.get_empty_text(query))
            self.games_stack.setCurrentWidget(self.empty_label)
        self.search_entry.setPlaceholderText(
            ngettext("Search %d game", "Search %d games", len(game_list)) % len(game_list)
            if game_list
            else _("Search games")
        )
        self.update_actions()

    async def get_empty_text(self, query: LibraryQuery) -> str:
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

    def refresh_sidebar(self, *_args: Any) -> None:
        start_task(self.sidebar.refresh(), self)

    def get_selected_game(self) -> LibraryGame | None:
        indexes = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self.model.get_game(indexes[0]) if indexes else None

    def update_actions(self) -> None:
        game = self.get_selected_game()
        running = bool(game and game.game_id in self._running_game_ids)
        self.play_action.setEnabled(bool(game and game.installed and game.game_id and not running))
        self.stop_action.setEnabled(running)

    def update_sort_indicator(self) -> None:
        sort = self.sort
        column = next((index for index, (_name, _title, key) in enumerate(COLUMNS) if key == sort.key), 0)
        # Names sort A to Z unless reversed, but the rest newest or most first
        descending = sort.reverse if sort.key == "name" else not sort.reverse
        order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(column, order)

    def on_header_clicked(self, column: int) -> None:
        """Sort by a column, or flip the order if it sorts by it already."""
        key = COLUMNS[column][2]
        if key:
            sort = self.sort
            settings.write_setting("view_reverse_order", not sort.reverse if key == sort.key else False)
            settings.write_setting("view_sorting", key)
            self.refresh()
        self.update_sort_indicator()

    def on_view_selected(self, view: dict[str, str]) -> None:
        self._view = view
        self.refresh()

    def on_installed_toggled(self, checked: bool) -> None:
        settings.write_setting("filter_installed", bool(checked))
        self.refresh()

    def on_game_activated(self, index: QModelIndex) -> None:
        game = self.model.data(index, GameRole)
        if game and game.installed and game.game_id:
            start_task(self.launch(game.game_id), self)

    def on_play(self) -> None:
        game = self.get_selected_game()
        if game and game.game_id:
            start_task(self.launch(game.game_id), self)

    def on_stop(self) -> None:
        game = self.get_selected_game()
        if game and game.game_id:
            start_task(games.stop_game(game.game_id), self)

    async def launch(self, game_id: str) -> None:
        await games.launch_game(game_id, self.launch_ui_delegate)

    def on_game_changed(self, _game: GameInfo) -> None:
        # Games change in batches (a library sync, say), so let them settle first
        self._refresh_timer.start()

    def on_game_launching(self, game: GameInfo) -> None:
        self._running_game_ids.add(game.id)
        self.model.set_running_game_ids(self._running_game_ids)
        self.update_actions()

    def on_game_stopped(self, game: GameInfo) -> None:
        self._running_game_ids.discard(game.id)
        self.model.set_running_game_ids(self._running_game_ids)
        self.update_actions()
        if self._view.get("dynamic_category") == "running":
            self.refresh()

    def on_game_failed(self, _game_id: str, error: BaseException) -> None:
        show_error(error, self)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        for registration in self._registrations:
            registration.unregister()
        if self._refresh_task:
            self._refresh_task.cancel()
        super().closeEvent(event)
        self.closed.emit()
