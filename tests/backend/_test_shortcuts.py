"""Exercise shortcut files and launch targets through the backend API."""

import asyncio
import subprocess
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


@pytest.fixture
def steam_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "Steam config"
    config.mkdir()
    monkeypatch.setattr(steam_shortcut, "get_config_path", lambda: str(config))
    monkeypatch.setattr(steam_shortcut, "set_artwork", lambda _game, **_kwargs: None)
    return config


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


def test_steam_shortcut_mutations_are_idempotent(shortcut_game: str, steam_config: Path) -> None:
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


def test_standalone_shortcut_runs_selected_configuration(
    shortcut_game: str, steam_config: Path, tmp_path: Path
) -> None:
    executable = tmp_path / "fixture game"
    executable.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    executable.chmod(0o700)
    (tmp_path / "games" / "shortcut.yml").write_text(
        f'game:\n  exe: "{executable}"\n  args: --primary\n  launch_configs:\n'
        f'    - name: Safe / Windowed\n      exe: "{executable}"\n      args: --windowed\n'
        "system:\n  gamemode: false\n",
        encoding="utf-8",
    )

    async def run() -> None:
        await shortcuts.set_shortcut(shortcut_game, "steam", True)
        state = await shortcuts.set_shortcut(shortcut_game, "steam_big_picture", True, "Safe / Windowed")
        assert {target.kind: target.exists for target in state.targets if target.kind.startswith("steam")} == {
            "steam": True,
            "steam_big_picture": True,
        }
        regular, standalone = steam_shortcut.get_shortcuts().values()
        assert regular["appid"] != standalone["appid"]
        script = Path(standalone["Exe"].strip('"'))
        assert script == steam_config / "lutris-shortcuts" / f"lutris-{shortcut_game}.sh"
        result = subprocess.run(
            [script], cwd=standalone["StartDir"].strip('"'), check=True, capture_output=True, text=True, timeout=10
        )
        assert result.stdout == "--windowed\n"

        await shortcuts.set_shortcut(shortcut_game, "steam", False)
        assert list(steam_shortcut.get_shortcuts().values()) == [standalone]
        assert script.is_file()
        await shortcuts.set_shortcut(shortcut_game, "steam", True)
        state = await shortcuts.set_shortcut(shortcut_game, "steam_big_picture", False)
        assert {target.kind: target.exists for target in state.targets if target.kind.startswith("steam")} == {
            "steam": True,
            "steam_big_picture": False,
        }
        assert list(steam_shortcut.get_shortcuts().values()) == [regular]
        assert not script.exists()

    asyncio.run(run())


def test_failed_standalone_export_preserves_existing_entries(
    shortcut_game: str, steam_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed_export(_game: Game, filename: str, delegate: LaunchUIDelegate) -> None:
        assert isinstance(delegate, CommandLineUIDelegate)
        assert delegate.launch_config_name == "Safe / Windowed"
        Path(filename).write_text("Unfinished script", encoding="utf-8")
        raise OSError("write failed")

    monkeypatch.setattr(Game, "write_script", failed_export)

    async def run() -> None:
        await shortcuts.set_shortcut(shortcut_game, "steam", True)
        vdf_path = steam_config / "shortcuts.vdf"
        original = vdf_path.read_bytes()
        with pytest.raises(LutrisError, match="Could not update"):
            await shortcuts.set_shortcut(shortcut_game, "steam_big_picture", True, "Safe / Windowed")
        assert vdf_path.read_bytes() == original
        assert not list((steam_config / "lutris-shortcuts").iterdir())

    asyncio.run(run())


def test_flatpak_only_offers_removal_of_legacy_standalone_shortcut(
    shortcut_game: str, steam_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(shortcuts.LINUX_SYSTEM, "is_flatpak", lambda: True)
    script = tmp_path / ".local/share/applications/lutris-shortcut-game.sh"
    script.parent.mkdir(parents=True)
    script.touch()
    steam_shortcut.create_shortcut(Game(shortcut_game), standalone=True)

    async def run() -> None:
        state = await shortcuts.get_shortcuts(shortcut_game)
        assert {target.kind: target.exists for target in state.targets if target.kind.startswith("steam")} == {
            "steam": False,
            "steam_big_picture": True,
        }
        state = await shortcuts.set_shortcut(shortcut_game, "steam_big_picture", False)
        assert all(target.kind != "steam_big_picture" for target in state.targets)
        assert not (steam_config / "lutris-shortcuts").exists()
        assert not steam_shortcut.get_shortcuts()
        assert script.is_file()
        with pytest.raises(LutrisError, match="destination is unavailable"):
            await shortcuts.set_shortcut(shortcut_game, "steam_big_picture", True)

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
