"""Render the Qt Quick library from seeded backend data."""

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from lutris import settings
from lutris.backend import events, game_actions
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.qt.main_window import MainWindow
from lutris.services.base import LutrisBanner, LutrisCoverart
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()

PREFIX = "qt-window-test-"


@pytest.fixture
def library() -> Iterator[list[str]]:
    ids = [
        str(games_db.add_game(name=PREFIX + "Installed", slug=PREFIX + "installed", runner="linux", installed=1)),
        str(games_db.add_game(name=PREFIX + "Uninstalled", slug=PREFIX + "uninstalled", runner="linux", installed=0)),
    ]
    category_id = categories_db.add_category(PREFIX + "Category")
    categories_db.add_game_to_category(ids[0], category_id)
    yield ids
    for game_id in ids:
        for category in categories_db.get_categories_in_game(game_id):
            if row := categories_db.get_category_by_name(category):
                categories_db.remove_category_from_game(game_id, int(row["id"]))
        games_db.delete_game(game_id)
    categories_db.remove_category(category_id)


async def settle(window: MainWindow) -> None:
    await window.load_task
    for task in (window.controller._sidebar_task, window.controller._refresh_task):
        if task:
            await task


def listed(window: MainWindow) -> list[str]:
    model = window.controller.model
    names = []
    for row in range(model.rowCount()):
        game = model.game_at(row)
        assert game is not None
        if game.name.startswith(PREFIX):
            names.append(game.name)
    return names


def test_the_window_follows_sidebar_search_and_filter(qt_application: QGuiApplication, library: list[str]) -> None:
    async def run() -> None:
        window = MainWindow()
        controller = window.controller
        try:
            controller.set_installed_only(False)
            await settle(window)
            assert window.window.title() == "Lutris"
            assert listed(window) == [PREFIX + "Installed", PREFIX + "Uninstalled"]

            controller.set_search("uninstalled")
            controller.refresh()
            await settle(window)
            assert listed(window) == [PREFIX + "Uninstalled"]

            controller.set_search("")
            row = controller.sidebar.find_row({"category": PREFIX + "Category"})
            assert row >= 0
            controller.select_view(row)
            await settle(window)
            assert listed(window) == [PREFIX + "Installed"]

            controller.select_view(controller.sidebar.find_row({"category": "all"}))
            controller.set_installed_only(True)
            await settle(window)
            assert listed(window) == [PREFIX + "Installed"]
        finally:
            window.shutdown()

    asyncio.run(run())


async def wait_for_qml(application: QGuiApplication, ready: Callable[[], bool]) -> None:
    for _ in range(100):
        application.processEvents()
        if ready():
            return
        await asyncio.sleep(0.02)
    pytest.fail("Qt Quick did not reach the expected state")


def test_grid_reloads_artwork_and_keeps_selection_across_layouts(
    qt_application: QGuiApplication,
    library: list[str],
    fake_main_loop: FakeMainLoop,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SHOW_MEDIA", True)
    read_setting = settings.read_setting
    monkeypatch.setattr(
        settings,
        "read_setting",
        lambda key, default="", section="lutris": (
            "covers" if key == "qt_library_layout" else read_setting(key, default, section)
        ),
    )
    monkeypatch.setattr(settings, "write_setting", lambda *_args: None)
    monkeypatch.setattr(LutrisCoverart, "dest_path", str(tmp_path / "covers"))
    monkeypatch.setattr(LutrisBanner, "dest_path", str(tmp_path / "banners"))
    cover = LutrisCoverart().get_possible_media_paths(PREFIX + "installed")[1].path
    banner = LutrisBanner().get_possible_media_paths(PREFIX + "installed")[1].path

    def save_image(path: str, width: int, height: int, color: Qt.GlobalColor) -> None:
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(color)
        assert image.save(path)

    save_image(cover, 144, 192, Qt.GlobalColor.red)
    save_image(banner, 208, 96, Qt.GlobalColor.green)

    async def run() -> None:
        window = MainWindow()
        window.show()
        controller = window.controller
        try:
            controller.set_installed_only(False)
            await settle(window)
            row = controller.model.find_row(library[0])
            assert row >= 0
            controller.select_game(row)

            grid = window.window.findChild(QQuickItem, "libraryGrid")
            assert grid is not None

            def artwork_color() -> QColor:
                image = window.window.grabWindow()
                point = grid.mapToScene(QPointF(grid.property("cellWidth") * (row + 0.5), 45))
                return image.pixelColor((point * image.devicePixelRatio()).toPoint())

            await wait_for_qml(qt_application, lambda: artwork_color() == QColor(Qt.GlobalColor.red))
            assert controller.property("canPlay")
            controller.set_layout("banners")
            await wait_for_qml(qt_application, lambda: artwork_color() == QColor(Qt.GlobalColor.green))

            save_image(banner, 208, 96, Qt.GlobalColor.blue)
            events.ARTWORK_CHANGED.fire()
            fake_main_loop.run_pending()
            await wait_for_qml(qt_application, lambda: artwork_color() == QColor(Qt.GlobalColor.blue))

            controller.set_layout("list")
            assert window.window.findChild(QObject, "libraryList") is not None
            assert controller.property("selectedGameId") == library[0]
            assert controller.property("canPlay")
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_dialog_answers_a_launch_question(qt_application: QGuiApplication, library: list[str]) -> None:
    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            await settle(window)

            def answer() -> None:
                prompt = window.window.findChild(QObject, "lutrisInput")
                if prompt is not None and prompt.property("visible"):
                    seen_prompt.append(True)
                    QTest.keyClick(window.window, Qt.Key.Key_Escape)

            seen_prompt: list[bool] = []
            deadline = QTimer(window)
            deadline.setSingleShot(True)
            deadline.timeout.connect(lambda: window.prompts.answer(True, "timeout"))

            QTimer.singleShot(50, answer)
            deadline.start(1000)
            assert window.prompts.ask("question", "Launch", "Proceed?") is None
            deadline.stop()
            assert seen_prompt
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_actions_update_favorites_and_categories(
    qt_application: QGuiApplication, library: list[str], fake_main_loop: FakeMainLoop
) -> None:
    async def run() -> None:
        window = MainWindow()
        window.show()
        controller = window.controller
        target = library[0]
        category_name = PREFIX + "Arcade"
        try:
            await settle(window)
            controller.select_game(controller.model.find_row(target))
            button = window.window.findChild(QQuickItem, "libraryGameActions")
            menu = window.window.findChild(QObject, "libraryGameMenu")
            assert button is not None and menu is not None
            qt_application.processEvents()
            point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()

            async def open_menu() -> None:
                QTest.mouseClick(window.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                await wait_for_qml(
                    qt_application, lambda: menu.property("visible") and controller.property("organizationReady")
                )

            await open_menu()
            favorite = window.window.findChild(QObject, "toggleFavorite")
            assert favorite is not None and QMetaObject.invokeMethod(favorite, "triggered")
            await asyncio.gather(*controller._tasks)
            assert (await game_actions.get_organization(target)).favorite
            assert QMetaObject.invokeMethod(menu, "close")

            await open_menu()
            edit = window.window.findChild(QObject, "editGameCategories")
            assert edit is not None and QMetaObject.invokeMethod(edit, "triggered")
            category_field = window.window.findChild(QObject, "newGameCategory")
            assert category_field is not None
            category_field.setProperty("text", "  " + category_name + "  ")
            assert QMetaObject.invokeMethod(category_field, "accepted")
            await asyncio.gather(*controller._tasks)
            assert category_name in categories_db.get_categories_in_game(target)

            fake_main_loop.run_pending()
            fake_main_loop.run_pending()
            await settle(window)
            assert controller.sidebar.find_row({"category": category_name}) >= 0
        finally:
            window.shutdown()
            if category := categories_db.get_category_by_name(category_name):
                categories_db.remove_category(int(category["id"]))

    asyncio.run(run())
