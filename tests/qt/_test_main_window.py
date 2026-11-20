"""Render the Qt Quick library from seeded backend data."""

import asyncio
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QCoreApplication, QEvent, QMetaObject, QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from lutris import settings
from lutris.backend import (
    configuration,
    events,
    game_actions,
    installations,
    installers,
    media,
    preferences,
    runtime_updates,
    shortcuts,
)
from lutris.backend.launch_configurations import LaunchChoice
from lutris.backend.models import ArtworkSettings, SourceSetting, StoragePaths
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import sql
from lutris.game import LOG_BUFFERS, Game
from lutris.installer import interpreter
from lutris.installer.installer import LutrisInstaller
from lutris.qt.main_window import MainWindow
from lutris.services.base import LutrisBanner, LutrisCoverart
from lutris.util import path_cache
from lutris.util.test_config import setup_test_environment
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file
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


def find_item(root: QQuickItem, name: str) -> QQuickItem | None:
    for child in root.childItems():
        if child.objectName() == name:
            return child
        if found := find_item(child, name):
            return found
    return None


def test_qml_lists_and_selects_installers_without_running_them(
    qt_application: QGuiApplication, library: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    base_slug = PREFIX + "base"

    def script(name: str, slug: str, version: str, **extra: object) -> dict[str, object]:
        return {
            "name": name,
            "game_slug": slug,
            "slug": f"{slug}-{version.lower()}",
            "version": version,
            "runner": "linux",
            "description": f"{version} description",
            "notes": "",
            "credits": "",
            "script": {
                "game": {"exe": "$GAMEDIR/game.sh"},
                "files": [{"setup": "N/A:Select the setup"}],
                "installer": [{"extract": {"file": "setup", "dst": "$GAMEDIR"}}],
                **extra,
            },
        }

    catalogs = {
        PREFIX + "uninstalled": [
            script(PREFIX + "Uninstalled", PREFIX + "uninstalled", "Native"),
            script(PREFIX + "Uninstalled", PREFIX + "uninstalled", "Expansion", requires=base_slug),
        ],
        base_slug: [script(PREFIX + "Base", base_slug, "Base")],
    }
    monkeypatch.setattr(installers, "get_installers", lambda game_slug: catalogs[game_slug])

    async def run() -> None:
        window = MainWindow()
        window.show()
        controller = window.controller
        dialog_controller = controller._installers
        try:
            controller.set_installed_only(False)
            await settle(window)
            controller.select_game(controller.model.find_row(library[0]))
            assert not controller.property("canInstall")
            await open_game_action(window, qt_application, library[1], "installGame")

            dialog = window.window.findChild(QObject, "installerDialog")
            choices = window.window.findChild(QQuickItem, "installerChoices")
            assert dialog is not None and choices is not None
            await wait_for_qml(qt_application, lambda: len(dialog_controller.property("choices")) == 2)
            assert dialog.property("title") == "Install " + PREFIX + "Uninstalled"

            async def choose(choice_id: str) -> None:
                await wait_for_qml(
                    qt_application, lambda: find_item(choices, "chooseInstaller" + choice_id) is not None
                )
                button = find_item(choices, "chooseInstaller" + choice_id)
                assert button is not None and QMetaObject.invokeMethod(button, "clicked")
                await wait_for_qml(qt_application, lambda: bool(dialog_controller.property("selected")))

            await choose("0")
            directory = window.window.findChild(QObject, "installerDirectory")
            assert directory is not None
            target = str(directory.property("text"))
            assert target.endswith("/" + PREFIX + "uninstalled") and not Path(target).exists()
            assert dialog_controller.property("requiredGame") == ""

            back = window.window.findChild(QObject, "installerBack")
            assert back is not None and QMetaObject.invokeMethod(back, "clicked")
            await wait_for_qml(qt_application, lambda: not dialog_controller.property("selected"))

            await choose("1")
            assert dialog_controller.property("requiredGame") == base_slug
            required = window.window.findChild(QObject, "showRequiredGameInstallers")
            assert required is not None and QMetaObject.invokeMethod(required, "clicked")
            await wait_for_qml(qt_application, lambda: dialog_controller.property("gameName") == PREFIX + "Base")
            assert [choice["version"] for choice in dialog_controller.property("choices")] == ["Base"]

            catalog = dialog_controller._catalog
            assert catalog is not None and catalog.id in installers._catalogs
            assert QMetaObject.invokeMethod(dialog, "close")
            await wait_for_qml(qt_application, lambda: catalog.id not in installers._catalogs)
            assert dialog_controller.property("choices") == []
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_runs_an_install_script_to_the_end(
    qt_application: QGuiApplication,
    library: list[str],
    fake_main_loop: FakeMainLoop,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "config" / "games").mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(settings, "INSTALLER_CACHE_DIR", str(tmp_path / "installer-cache"))
    monkeypatch.setattr(settings, "write_setting", lambda *_args: None)
    monkeypatch.setattr(interpreter, "fetch_game_artwork", lambda slug: 0)
    monkeypatch.setattr(LutrisInstaller, "_get_discord_id_from_api", lambda self: None)
    setup = tmp_path / "setup.txt"
    setup.write_text("game data", encoding="utf-8")
    target = tmp_path / "Games" / "qt-installed"
    script = {
        "name": PREFIX + "Uninstalled",
        "game_slug": PREFIX + "uninstalled",
        "slug": PREFIX + "uninstalled-local",
        "version": "Local",
        "runner": "linux",
        "script": {
            "game": {"exe": "$GAMEDIR/setup.txt"},
            "files": [{"setup": "N/A:Select the game data"}],
            "installer": [
                {"input_menu": {"id": "LANG", "options": [{"en": "English"}, {"fr": "French"}], "preselect": "fr"}},
                {"copy": {"src": "setup", "dst": "$GAMEDIR"}},
                {"write_file": {"file": "$GAMEDIR/lang.txt", "content": "$INPUT_LANG"}},
            ],
        },
    }
    monkeypatch.setattr(installers, "get_installers", lambda game_slug: [script])

    async def run() -> None:
        window = MainWindow()
        window.show()
        controller = window.controller
        progress = controller._installers.installation_controller
        try:
            controller.set_installed_only(False)
            await settle(window)
            await open_game_action(window, qt_application, library[1], "installGame")
            choices = window.window.findChild(QQuickItem, "installerChoices")
            assert choices is not None
            await wait_for_qml(qt_application, lambda: find_item(choices, "chooseInstaller0") is not None)
            choose = find_item(choices, "chooseInstaller0")
            assert choose is not None and QMetaObject.invokeMethod(choose, "clicked")
            await wait_for_qml(qt_application, lambda: bool(controller._installers.property("selected")))
            controller._installers.set_directory(str(target))

            def reached(stage: str) -> Callable[[], bool]:
                def check() -> bool:
                    fake_main_loop.run_pending()
                    assert progress.property("stage") != "failed", progress.property("status")
                    return progress.property("stage") == stage

                return check

            start = window.window.findChild(QObject, "installerStart")
            assert start is not None and start.property("enabled") and QMetaObject.invokeMethod(start, "clicked")
            await wait_for_qml(qt_application, reached("files"))

            page = window.window.findChild(QQuickItem, "installationPage")
            assert page is not None
            await wait_for_qml(qt_application, lambda: find_item(page, "filePath_setup") is not None)
            path = find_item(page, "filePath_setup")
            assert path is not None
            path.setProperty("text", str(setup))
            assert QMetaObject.invokeMethod(path, "editingFinished")
            await wait_for_qml(qt_application, lambda: fake_main_loop.run_pending() or progress.property("filesReady"))
            files = window.window.findChild(QObject, "startInstallationFiles")
            assert files is not None and QMetaObject.invokeMethod(files, "clicked")

            await wait_for_qml(qt_application, reached("menu"))
            menu = window.window.findChild(QObject, "installationMenu")
            assert menu is not None and menu.property("currentValue") == "fr"
            confirm = window.window.findChild(QObject, "confirmInstallationMenu")
            assert confirm is not None and QMetaObject.invokeMethod(confirm, "clicked")

            await wait_for_qml(qt_application, reached("finished"))
            launch = window.window.findChild(QObject, "installerLaunch")
            assert launch is not None and launch.property("visible")

            def installed_in_library() -> bool:
                fake_main_loop.run_pending()
                model = controller.model
                game = model.game_at(model.find_row(library[1]))
                return bool(game and game.installed)

            await wait_for_qml(qt_application, installed_in_library)
            close = window.window.findChild(QObject, "installerClose")
            assert close is not None and QMetaObject.invokeMethod(close, "clicked")
            await wait_for_qml(qt_application, lambda: not progress.property("active"))
            await wait_for_qml(qt_application, lambda: not installations._installations)
        finally:
            window.shutdown()

    asyncio.run(run())
    assert (target / "setup.txt").read_text(encoding="utf-8") == "game data"
    assert (target / "lang.txt").read_text(encoding="utf-8") == "fr"


def test_qml_configures_a_game_and_the_global_options(
    qt_application: QGuiApplication,
    library: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "games").mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(settings, "write_setting", lambda *_args: None)
    monkeypatch.setattr(configuration, "fetch_game_artwork", lambda slug: 0)
    write_yaml_to_file({"game": {"exe": "/games/run.sh"}}, str(config_dir / "games" / "qt-config.yml"))
    sql.db_update(settings.DB_PATH, "games", {"configpath": "qt-config"}, {"id": library[0]})

    async def run() -> None:
        window = MainWindow()
        window.show()
        controller = window.controller
        config = controller._configuration
        try:
            await settle(window)
            await open_game_action(window, qt_application, library[0], "configureGame")
            dialog = window.window.findChild(QObject, "configDialog")
            options = window.window.findChild(QQuickItem, "configOptions")
            assert dialog is not None and options is not None
            await wait_for_qml(qt_application, lambda: bool(config.property("ready")))
            assert config.property("pages") == ["Game info", "Game options", "Runner options", "System options"]
            assert dialog.property("title") == "Configure " + PREFIX + "Installed"
            assert config.property("infoPage") and config.property("game")["runner"] == "linux"
            config.select_page(1)

            await wait_for_qml(qt_application, lambda: find_item(options, "configOption_args") is not None)
            args = find_item(options, "configOption_args")
            assert args is not None
            config.set_value("game", "args", "--fullscreen")
            await wait_for_qml(qt_application, lambda: bool(config.property("modified")) and args.property("setHere"))
            assert args.property("optionValue") == "--fullscreen"

            config.select_page(2)
            choice_name = "optionChoice_steam_linux_runtime"
            await wait_for_qml(qt_application, lambda: find_item(options, choice_name) is not None)
            choice = find_item(options, choice_name)
            assert choice is not None and choice.property("count") == 5
            assert choice.property("currentValue") == "none"
            choice.setProperty("currentIndex", 4)
            assert QMetaObject.invokeMethod(choice, "activated", Q_ARG(int, 4))
            await wait_for_qml(
                qt_application,
                lambda: bool(
                    (reset := find_item(options, "resetOption_steam_linux_runtime")) and reset.property("visible")
                ),
            )
            assert choice.property("currentValue") == "steamrt4"

            save = window.window.findChild(QObject, "configSave")
            assert save is not None and save.property("enabled") and QMetaObject.invokeMethod(save, "clicked")
            await wait_for_qml(qt_application, lambda: not config.property("ready"))
            row = games_db.get_game_by_field(library[0], "id")
            assert row is not None
            saved = read_yaml_from_file(str(config_dir / "games" / f"{row['configpath']}.yml"))
            assert saved["game"] == {"exe": "/games/run.sh", "args": "--fullscreen"}
            assert saved["linux"] == {"steam_linux_runtime": "steamrt4"}

            action = window.window.findChild(QObject, "globalOptions")
            assert action is not None and QMetaObject.invokeMethod(action, "triggered")
            await wait_for_qml(qt_application, lambda: config.property("pages") == ["System options"])
            config.set_search("no option has this text")
            assert config.property("emptyText") == "No options match 'no option has this text'"

            runner = find_item(window.window.contentItem(), "sidebarRunner_linux")
            assert runner is not None
            config.open_runner("linux", "Linux")
            await wait_for_qml(qt_application, lambda: config.property("pages") == ["Runner options", "System options"])
            assert config.property("title") == "Configure Linux"

            add = window.window.findChild(QObject, "addGame")
            assert add is not None and QMetaObject.invokeMethod(add, "triggered")
            await wait_for_qml(qt_application, lambda: bool(config.property("isNewGame")))
            assert config.property("pages") == ["Game info", "System options"]
            # The earlier dialogs' fields linger until their deferred deletion
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            name = window.window.findChild(QObject, "gameInfoName")
            assert name is not None
            name.setProperty("text", PREFIX + "Hand Added")
            assert QMetaObject.invokeMethod(name, "editingFinished")
            config.set_runner("linux")
            await wait_for_qml(qt_application, lambda: len(config.property("pages")) == 4)
            config.set_value("game", "exe", "/games/hand.sh")
            await wait_for_qml(qt_application, lambda: config.property("game")["name"] == PREFIX + "Hand Added")
            save = window.window.findChild(QObject, "configSave")
            assert save is not None and QMetaObject.invokeMethod(save, "clicked")
            await wait_for_qml(qt_application, lambda: not config.property("ready"))
            added = games_db.get_game_by_field(PREFIX + "Hand Added", "name")
            assert added is not None and added["runner"] == "linux"
            games_db.delete_game(added["id"])
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_saves_a_steamgriddb_key_then_fetches_artwork(
    qt_application: QGuiApplication, library: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    saved: list[str] = []

    async def get_artwork_settings() -> ArtworkSettings:
        return ArtworkSettings(bool(saved), False, "https://example.com/key")

    async def set_steamgriddb_api_key(api_key: str) -> ArtworkSettings:
        saved.append(api_key)
        return await get_artwork_settings()

    async def update_artwork() -> int:
        return 2

    monkeypatch.setattr(media, "get_artwork_settings", get_artwork_settings)
    monkeypatch.setattr(media, "set_steamgriddb_api_key", set_steamgriddb_api_key)
    monkeypatch.setattr(media, "update_artwork", update_artwork)

    async def run() -> None:
        window = MainWindow()
        window.show()
        try:
            await settle(window)
            action = window.window.findChild(QObject, "artworkSources")
            assert action is not None and QMetaObject.invokeMethod(action, "triggered")
            await wait_for_qml(qt_application, lambda: window.window.findChild(QObject, "steamGridDbKey") is not None)
            key = window.window.findChild(QObject, "steamGridDbKey")
            save = window.window.findChild(QObject, "saveSteamGridDbKey")
            assert key is not None and save is not None and not save.property("enabled")
            key.setProperty("text", "my-key")
            assert save.property("enabled") and QMetaObject.invokeMethod(save, "clicked")
            await wait_for_qml(
                qt_application, lambda: window.controller.property("statusText") == "Downloaded 2 images"
            )
            assert saved == ["my-key"]
            dialog = window.window.findChild(QObject, "artworkSettingsDialog")
            assert dialog is None or not dialog.property("visible")
        finally:
            window.shutdown()

    asyncio.run(run())


def test_qml_preferences_change_sources_storage_and_check_the_runtime(
    qt_application: QGuiApplication, library: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = {"gog": SourceSetting("gog", "GOG", "", False, True)}
    game_paths: list[str] = []

    async def list_sources() -> tuple[SourceSetting, ...]:
        return tuple(sources.values())

    async def set_source_enabled(source_id: str, enabled: bool) -> None:
        sources[source_id] = SourceSetting(source_id, "GOG", "", enabled, True)

    async def get_storage_paths() -> StoragePaths:
        return StoragePaths(game_paths[-1] if game_paths else "/games", "", "", True, "", "")

    async def set_game_path(path: str) -> StoragePaths:
        game_paths.append(path)
        return await get_storage_paths()

    async def update_runtime(force: bool = False) -> tuple[str, ...]:
        return ("dxvk",) if force else ()

    async def nothing() -> tuple[()]:
        return ()

    monkeypatch.setattr(preferences, "list_sources", list_sources)
    monkeypatch.setattr(preferences, "set_source_enabled", set_source_enabled)
    monkeypatch.setattr(preferences, "get_storage_paths", get_storage_paths)
    monkeypatch.setattr(preferences, "set_game_path", set_game_path)
    monkeypatch.setattr(preferences, "list_steam_accounts", nothing)
    monkeypatch.setattr(preferences, "get_system_info", nothing)
    monkeypatch.setattr(runtime_updates, "update_runtime", update_runtime)

    async def run() -> None:
        window = MainWindow()
        window.show()
        prefs = window.controller._preferences
        refreshed: list[bool] = []
        prefs.sourcesChanged.connect(lambda: refreshed.append(True))
        try:
            await settle(window)
            action = window.window.findChild(QObject, "openPreferences")
            assert action is not None and QMetaObject.invokeMethod(action, "triggered")
            await wait_for_qml(qt_application, lambda: len(prefs.property("sources")) == 1)

            dialog = window.window.findChild(QObject, "preferencesDialog")
            assert dialog is not None
            content = dialog.property("contentItem")
            await wait_for_qml(qt_application, lambda: find_item(content, "sourceSwitch_gog") is not None)
            switch = find_item(content, "sourceSwitch_gog")
            assert switch is not None and not switch.property("checked")
            switch.setProperty("checked", True)
            assert QMetaObject.invokeMethod(switch, "toggled")
            await wait_for_qml(qt_application, lambda: prefs.property("sources")[0]["enabled"] and bool(refreshed))

            await wait_for_qml(qt_application, lambda: find_item(content, "storagePath_game") is not None)
            path = find_item(content, "storagePath_game")
            assert path is not None and path.property("text") == "/games"
            path.setProperty("text", "/mnt/games")
            assert QMetaObject.invokeMethod(path, "editingFinished")
            await wait_for_qml(qt_application, lambda: prefs.property("storage")["gamePath"] == "/mnt/games")

            check = window.window.findChild(QObject, "checkRuntimeUpdates")
            assert check is not None and QMetaObject.invokeMethod(check, "clicked")
            runtime = window.controller.runtime_updates_controller
            await wait_for_qml(qt_application, lambda: runtime.property("statusText") == "Updated dxvk.")
        finally:
            window.shutdown()

    asyncio.run(run())


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
