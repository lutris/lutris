"""Exercise shortcut files and launch targets through the backend API."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from lutris import settings
from lutris.api import parse_installer_url
from lutris.backend import games, shortcuts
from lutris.backend.launch_configurations import BackendLaunchUIDelegate, LaunchChoice
from lutris.backend.models import GameInfo
from lutris.database import games as games_db
from lutris.delegates import CommandLineUIDelegate, LaunchUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import Game
from lutris.util import xdgshortcuts
from lutris.util.steam import shortcut as steam_shortcut
from lutris.util.test_config import setup_test_environment

setup_test_environment()


@pytest.fixture
def shortcut_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "shortcut.yml").write_text(
        "game:\n  launch_configs:\n    - name: Safe / Windowed\n      args: --windowed\n", encoding="utf-8"
    )
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    game_id = str(
        games_db.add_game(
            name="Shortcut Game", slug="shortcut-game", installed=1, runner="linux", configpath="shortcut"
        )
    )
    try:
        yield game_id
    finally:
        games_db.delete_game(game_id)


def test_application_shortcut_without_desktop_folder(
    shortcut_game: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(xdgshortcuts, "get_xdg_entry", lambda _key: None)
    monkeypatch.setattr(xdgshortcuts, "get_menu_launcher_directory", lambda: str(tmp_path / "applications"))
    monkeypatch.setattr(xdgshortcuts, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(steam_shortcut, "get_shortcuts_vdf_path", lambda: "")

    async def run() -> None:
        state = await shortcuts.get_shortcuts(shortcut_game)
        assert state.configuration_names == ("", "Safe / Windowed")
        assert [(target.kind, target.exists) for target in state.targets] == [("menu", False)]
        with pytest.raises(LutrisError):
            await shortcuts.set_shortcut(shortcut_game, "menu", True, "unknown")
        state = await shortcuts.set_shortcut(shortcut_game, "menu", True, "Safe / Windowed")
        assert state.targets[0].exists
        launcher = Path(xdgshortcuts.get_menu_launcher_path("shortcut-game", shortcut_game))
        assert f"lutris:rungameid/{shortcut_game}/Safe%%20%%2F%%20Windowed" in launcher.read_text(encoding="utf-8")
        state = await shortcuts.set_shortcut(shortcut_game, "menu", False)
        assert not state.targets[0].exists
        assert not launcher.exists()

    asyncio.run(run())


def test_steam_shortcut_mutations_are_idempotent(
    shortcut_game: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(steam_shortcut, "get_shortcuts_vdf_path", lambda: str(tmp_path / "shortcuts.vdf"))
    monkeypatch.setattr(steam_shortcut, "set_artwork", lambda _game: None)
    monkeypatch.setattr(steam_shortcut.shutil, "which", lambda _program: "/usr/bin/lutris")

    async def run() -> None:
        await asyncio.gather(
            shortcuts.set_shortcut(shortcut_game, "steam", True, "Safe / Windowed"),
            shortcuts.set_shortcut(shortcut_game, "steam", True, "Safe / Windowed"),
        )
        (shortcut,) = steam_shortcut.get_shortcuts().values()
        request = parse_installer_url(shortcut["LaunchOptions"].strip("'"))
        assert request["launch_config_name"] == "Safe / Windowed"
        await shortcuts.set_shortcut(shortcut_game, "steam", False)
        assert not steam_shortcut.get_shortcuts()

    asyncio.run(run())


def test_launch_uri_forwards_named_configuration(shortcut_game: str, monkeypatch: pytest.MonkeyPatch) -> None:
    args: list[str] = []

    async def launch(game_id: str, delegate: LaunchUIDelegate) -> bool:
        assert game_id == shortcut_game
        assert isinstance(delegate, CommandLineUIDelegate)
        config = delegate.select_game_launch_config(Game(game_id))
        assert config is not None
        args.append(config["args"])
        return True

    monkeypatch.setattr(games, "launch_game", launch)
    asyncio.run(games.launch_from_uri(f"lutris:rungameid/{shortcut_game}/Safe%20%2F%20Windowed"))
    assert args == ["--windowed"]


def test_remembered_launch_configuration_is_read_from_disk(shortcut_game: str) -> None:
    selections: list[int | None] = []

    class ChooseWindowed(BackendLaunchUIDelegate):
        def choose_launch_configuration(
            self, game: GameInfo, names: tuple[str, ...], current_index: int | None
        ) -> LaunchChoice:
            assert game.id == shortcut_game
            assert names[1] == "Safe / Windowed"
            selections.append(current_index)
            return LaunchChoice(1, True)

    delegate = ChooseWindowed()
    assert delegate.select_game_launch_config(Game(shortcut_game)) == {"name": "Safe / Windowed", "args": "--windowed"}
    assert delegate.select_game_launch_config(Game(shortcut_game)) == {"name": "Safe / Windowed", "args": "--windowed"}
    assert ChooseWindowed(choose_again=True).select_game_launch_config(Game(shortcut_game))
    assert selections == [None, 1]
