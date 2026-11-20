"""The Qt library window lists the library through the backend."""

import asyncio

import pytest

from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.qt.library_model import GameRole
from lutris.qt.main_window import MainWindow
from lutris.util.test_config import setup_test_environment

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
    for _attempt in range(200):
        await asyncio.sleep(0.01)
        if window._refresh_task and window._refresh_task.done():
            return


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
