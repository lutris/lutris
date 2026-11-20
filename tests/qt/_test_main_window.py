"""The Qt library window lists the library through the backend."""

import asyncio
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from lutris import settings
from lutris.backend import events
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.qt.library_model import GameRole
from lutris.qt.main_window import MainWindow
from lutris.services.base import LutrisBanner, LutrisCoverart
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()

PREFIX = "qt-window-test-"


@pytest.fixture
def library():
    ids = [
        str(games_db.add_game(name=PREFIX + "Installed", slug=PREFIX + "installed", runner="linux", installed=1)),
        str(games_db.add_game(name=PREFIX + "Uninstalled", slug=PREFIX + "uninstalled", runner="linux", installed=0)),
    ]
    category_id = categories_db.add_category(PREFIX + "Category")
    categories_db.add_game_to_category(ids[0], category_id)
    yield ids
    categories_db.remove_category_from_game(ids[0], category_id)
    categories_db.remove_category(category_id)
    for game_id in ids:
        games_db.delete_game(game_id)


async def settle(window: MainWindow) -> None:
    """Let the window's refresh finish. asyncio.run() doesn't run Qt's timers, so the
    tests refresh instead of waiting for the search field's."""
    await window._load_task
    if window._refresh_task:
        await window._refresh_task


def listed(window: MainWindow) -> list[str]:
    model = window.model
    names = [model.data(model.index(row, 0), GameRole).name for row in range(model.rowCount())]
    return [name for name in names if name.startswith(PREFIX)]


def test_the_window_follows_its_view_search_and_filter(qt_application, library):
    async def run() -> None:
        window = MainWindow()
        window.installed_check.setChecked(False)
        await settle(window)
        assert listed(window) == [PREFIX + "Installed", PREFIX + "Uninstalled"]

        window.search_entry.setText("uninstalled")
        window.refresh()
        await settle(window)
        assert listed(window) == [PREFIX + "Uninstalled"]

        window.search_entry.setText("")
        window._refresh_timer.stop()
        window.sidebar.select_view({"category": PREFIX + "Category"})
        await settle(window)
        assert listed(window) == [PREFIX + "Installed"]
        items = [window.sidebar.topLevelItem(i) for i in range(window.sidebar.topLevelItemCount())]
        sections = [item.text(0) for item in items if item]
        assert "Categories" in sections

        window.sidebar.select_view({"category": "all"})
        window.installed_check.setChecked(True)
        await settle(window)
        assert listed(window) == [PREFIX + "Installed"]
        window.close()

    asyncio.run(run())


def test_grid_switches_artwork_and_keeps_the_selected_game(
    qt_application: QApplication,
    library: list[str],
    fake_main_loop: FakeMainLoop,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SHOW_MEDIA", True)
    read_setting = settings.read_setting

    def read_test_setting(key: str, default: str = "", section: str = "lutris") -> str:
        return "covers" if key == "qt_library_layout" else read_setting(key, default, section)

    monkeypatch.setattr(settings, "read_setting", read_test_setting)
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
        try:
            window.installed_check.setChecked(False)
            await settle(window)
            row = window.model.find_row(library[0])
            assert row is not None
            index = window.model.index(row, 0)
            window.grid.setCurrentIndex(index)
            assert window.games_stack.currentWidget() is window.grid
            assert window.play_action.isEnabled()

            def artwork_color() -> QColor:
                qt_application.processEvents()
                rect = window.grid.visualRect(index)
                image = window.grid.viewport().grab().toImage()
                point = QPoint(rect.center().x(), rect.top() + 35) * image.devicePixelRatio()
                return image.pixelColor(point)

            assert artwork_color() == QColor(Qt.GlobalColor.red)
            window.change_layout("banners")
            assert artwork_color() == QColor(Qt.GlobalColor.green)

            save_image(banner, 208, 96, Qt.GlobalColor.blue)
            events.ARTWORK_CHANGED.fire()
            fake_main_loop.run_pending()
            assert artwork_color() == QColor(Qt.GlobalColor.blue)

            window.change_layout("list")
            assert window.games_stack.currentWidget() is window.table
            game = window.get_selected_game()
            assert game is not None and game.id == library[0]
            assert window.play_action.isEnabled()
        finally:
            window.close()

    asyncio.run(run())
