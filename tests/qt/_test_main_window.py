"""Render the Qt Quick library from seeded backend data."""

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from lutris import settings
from lutris.backend import events, game_actions, shortcuts
from lutris.backend.launch_configurations import LaunchChoice
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import sql
from lutris.game import LOG_BUFFERS, Game
from lutris.qt.main_window import MainWindow
from lutris.services.base import LutrisBanner, LutrisCoverart
from lutris.util import path_cache
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


async def open_game_action(window: MainWindow, application: QGuiApplication, game_id: str, action: str) -> None:
    controller = window.controller
    controller.select_game(controller.model.find_row(game_id))
    button = window.window.findChild(QQuickItem, "libraryGameActions")
    menu = window.window.findChild(QObject, "libraryGameMenu")
    assert button is not None and menu is not None
    application.processEvents()
    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
    QTest.mouseClick(window.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    await wait_for_qml(application, lambda: bool(menu.property("visible")))
    item = window.window.findChild(QObject, action)
    assert item is not None and item.property("enabled")
    assert QMetaObject.invokeMethod(item, "triggered")
    assert QMetaObject.invokeMethod(menu, "close")


@pytest.mark.parametrize("link_existing", [False, True])
def test_qml_registers_a_local_game(
    qt_application: QGuiApplication,
    library: list[str],
    fake_main_loop: FakeMainLoop,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_existing: bool,
) -> None:
    executable = tmp_path / "play game"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path / "config"))
    new_game_name = PREFIX + "Local Linux Game"

    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            window.controller.set_installed_only(False)
            await settle(window)
            if link_existing:
                await open_game_action(window, qt_application, library[1], "locateLocalGame")
            else:
                action = window.window.findChild(QObject, "addLocalGame")
                assert action is not None and QMetaObject.invokeMethod(action, "triggered")

            dialog = window.window.findChild(QObject, "localGameDialog")
            assert dialog is not None
            path = dialog.findChild(QObject, "localGameExecutable")
            arguments = dialog.findChild(QObject, "localGameArguments")
            name = dialog.findChild(QObject, "localGameName")
            confirm = dialog.findChild(QObject, "confirmLocalGame")
            assert path is not None and arguments is not None and name is not None and confirm is not None
            await wait_for_qml(qt_application, lambda: bool(dialog.property("opened")))
            assert not confirm.property("enabled")
            assert name.property("visible") != link_existing
            path.setProperty("text", str(executable))
            arguments.setProperty("text", "--windowed")
            if not link_existing:
                name.setProperty("text", new_game_name)
            assert confirm.property("enabled") and QMetaObject.invokeMethod(confirm, "clicked")
            await wait_for_qml(qt_application, lambda: not dialog.property("visible"))

            row = games_db.get_game_by_field(
                library[1] if link_existing else new_game_name, "id" if link_existing else "name"
            )
            assert row is not None and row["installed"] == 1
            installed_id = row["id"]
            fake_main_loop.run_pending()

            def installed_in_library() -> bool:
                model = window.controller.model
                game = model.game_at(model.find_row(installed_id))
                return bool(game and game.installed)

            await wait_for_qml(qt_application, installed_in_library)
            config = Game(installed_id).config
            assert config is not None and config.game_level["game"] == {"exe": str(executable), "args": "--windowed"}
        finally:
            window.shutdown()
            if not link_existing and (new_row := games_db.get_game_by_field(new_game_name, "name")):
                games_db.delete_game(new_row["id"])

    asyncio.run(run())


def test_qml_move_uninstall_and_remove_from_library(
    qt_application: QGuiApplication,
    library: list[str],
    fake_main_loop: FakeMainLoop,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = library[0]
    source = tmp_path / "Installed Game"
    destination = tmp_path / "Target Folder"
    source.mkdir()
    destination.mkdir()
    (source / "play.sh").touch()
    config = tmp_path / "games" / "qt-maintenance.yml"
    config.parent.mkdir()
    config.write_text("game:\n  exe: play.sh\n", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(path_cache, "GAME_PATH_CACHE_PATH", str(tmp_path / "path-cache.json"))
    read_bool_setting = settings.read_bool_setting
    monkeypatch.setattr(
        settings,
        "read_bool_setting",
        lambda key, *args, **kwargs: key != "library_sync_enabled" and read_bool_setting(key, *args, **kwargs),
    )
    sql.db_update(settings.DB_PATH, "games", {"directory": str(source), "configpath": "qt-maintenance"}, {"id": target})

    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            window.controller.set_installed_only(False)
            await settle(window)
            await open_game_action(window, qt_application, target, "moveGame")
            confirm = window.window.findChild(QObject, "confirmGameMove")
            assert confirm is not None
            upkeep = window.controller._maintenance
            await wait_for_qml(qt_application, lambda: bool(upkeep.property("ready")))
            assert not confirm.property("enabled")
            upkeep.choose_destination(QUrl.fromLocalFile(str(destination)))
            assert upkeep.property("moveTarget") == str(destination / source.name)
            assert confirm.property("enabled") and QMetaObject.invokeMethod(confirm, "clicked")
            await wait_for_qml(qt_application, lambda: not bool(upkeep.property("working")))
            assert (destination / source.name / "play.sh").exists() and not source.exists()
            assert not upkeep.property("ready")

            await open_game_action(window, qt_application, target, "uninstallGame")
            uninstall = window.window.findChild(QObject, "confirmGameUninstall")
            trash = window.window.findChild(QObject, "trashGameFiles")
            remove = window.window.findChild(QObject, "removeGameEntry")
            assert uninstall is not None and trash is not None and remove is not None
            await wait_for_qml(qt_application, lambda: bool(uninstall.property("enabled")))
            assert trash.property("enabled") and not trash.property("checked") and not remove.property("checked")
            assert QMetaObject.invokeMethod(uninstall, "clicked")
            await wait_for_qml(qt_application, lambda: not bool(upkeep.property("working")))
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert (destination / source.name / "play.sh").exists()
            assert not config.exists() and not Game(target).is_installed

            for _ in range(3):
                fake_main_loop.run_pending()

            def entry_is_uninstalled() -> bool:
                controller = window.controller
                game = controller.model.game_at(controller.model.find_row(target))
                return bool(game and not game.installed)

            await wait_for_qml(qt_application, entry_is_uninstalled)
            await open_game_action(window, qt_application, target, "uninstallGame")
            remove_entry = window.window.findChild(QObject, "confirmGameUninstall")
            assert remove_entry is not None
            await wait_for_qml(qt_application, lambda: bool(remove_entry.property("enabled")))
            assert remove_entry.property("text") == "Remove"
            assert QMetaObject.invokeMethod(remove_entry, "clicked")
            await wait_for_qml(qt_application, lambda: not bool(upkeep.property("working")))
            for _ in range(3):
                fake_main_loop.run_pending()
            await wait_for_qml(qt_application, lambda: window.controller.model.find_row(target) < 0)
            assert (destination / source.name / "play.sh").exists()
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_log_tracks_output_and_resets_on_relaunch(
    qt_application: QGuiApplication, library: list[str], fake_main_loop: FakeMainLoop
) -> None:
    async def run() -> None:
        window = MainWindow()
        window.show()
        target = library[0]
        buffer = Game(target).log_buffer
        try:
            await settle(window)
            buffer.append("<startup>\n")
            await open_game_action(window, qt_application, target, "showGameLogs")
            text = window.window.findChild(QObject, "gameLogText")
            assert text is not None
            await wait_for_qml(qt_application, lambda: text.property("text") == "<startup>\n")

            buffer.append("next line\n")
            for _ in range(3):
                fake_main_loop.run_pending()
            await wait_for_qml(qt_application, lambda: text.property("text") == "<startup>\nnext line\n")

            buffer.clear()
            buffer.append("second launch\n")
            for _ in range(3):
                fake_main_loop.run_pending()
            await wait_for_qml(qt_application, lambda: text.property("text") == "second launch\n")
        finally:
            window.shutdown()
            LOG_BUFFERS.pop(target, None)

    asyncio.run(run())


def test_qml_launch_configuration_uses_selected_index(qt_application: QGuiApplication) -> None:
    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            await settle(window)

            def answer() -> None:
                dialog = window.window.findChild(QObject, "launchConfigurationDialog")
                choice = window.window.findChild(QObject, "launchConfigurationChoice")
                remember = window.window.findChild(QObject, "rememberLaunchConfiguration")
                if dialog is not None and choice is not None and remember is not None and choice.property("count") == 2:
                    choice.setProperty("currentIndex", 1)
                    remember.setProperty("checked", True)
                    QMetaObject.invokeMethod(dialog, "accept")

            deadline = QTimer(window, singleShot=True, interval=1000)
            deadline.timeout.connect(window.prompts.dismiss)
            QTimer.singleShot(50, answer)
            deadline.start()
            assert window.prompts.choose_configuration("Launch", ("Primary", "Alternative"), None) == LaunchChoice(
                1, True
            )
            deadline.stop()
        finally:
            window.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("kind", "label"), [("menu", "Application Menu"), ("steam_big_picture", "Steam Big Picture (Standalone)")]
)
def test_qml_shortcuts_submit_the_destination_and_configuration(
    qt_application: QGuiApplication,
    library: list[str],
    monkeypatch: pytest.MonkeyPatch,
    kind: shortcuts.ShortcutKind,
    label: str,
) -> None:
    changes: list[tuple[str, bool, str]] = []

    async def get_shortcuts(game_id: str) -> shortcuts.GameShortcuts:
        assert game_id == library[0]
        exists = bool(changes and changes[-1][1])
        return shortcuts.GameShortcuts(
            (shortcuts.ShortcutTarget(kind, label, exists),),
            ("Primary", "Windowed"),
            ("", "Windowed"),
        )

    async def set_shortcut(game_id: str, kind: str, present: bool, configuration: str) -> shortcuts.GameShortcuts:
        changes.append((kind, present, configuration))
        return await get_shortcuts(game_id)

    monkeypatch.setattr(shortcuts, "get_shortcuts", get_shortcuts)
    monkeypatch.setattr(shortcuts, "set_shortcut", set_shortcut)

    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            await settle(window)
            await open_game_action(window, qt_application, library[0], "manageGameShortcuts")
            choice = window.window.findChild(QObject, "shortcutConfigurationChoice")
            assert choice is not None
            await wait_for_qml(qt_application, lambda: choice.property("count") == 2)
            choice.setProperty("currentIndex", 1)

            def shortcut_button(item: QQuickItem | None) -> QQuickItem | None:
                if item is None or item.objectName() == f"{kind}Shortcut":
                    return item
                return next((match for child in item.childItems() if (match := shortcut_button(child))), None)

            def find_button() -> QQuickItem | None:
                return shortcut_button(window.window.contentItem())

            button = find_button()
            assert button is not None and button.property("text") == "Create"
            assert QMetaObject.invokeMethod(button, "clicked")

            def removal_available() -> bool:
                remove = find_button()
                return bool(remove and remove.property("text") == "Remove" and remove.property("enabled"))

            await wait_for_qml(qt_application, removal_available)
            remove = find_button()
            assert remove is not None and QMetaObject.invokeMethod(remove, "clicked")
            await wait_for_qml(qt_application, lambda: len(changes) == 2)
            assert changes == [(kind, True, "Windowed"), (kind, False, "")]
        finally:
            window.shutdown()

    asyncio.run(run())
