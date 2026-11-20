"""Exercise native game registration with real files and library data."""

import asyncio
import subprocess
from pathlib import Path

import pytest

from lutris import settings
from lutris.backend import events, game_actions, game_maintenance, local_games
from lutris.backend.models import GameInfo
from lutris.database import categories
from lutris.database import games as games_db
from lutris.delegates import CommandLineUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import Game
from lutris.util.test_config import setup_test_environment
from tests.conftest import FakeMainLoop

setup_test_environment()


@pytest.fixture
def executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path / "config"))
    game = tmp_path / "Game folder" / "play game"
    game.parent.mkdir()
    game.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\n', encoding="utf-8")
    game.chmod(0o700)
    return game


def test_add_game_saves_launch_options_without_owning_files(executable: Path, fake_main_loop: FakeMainLoop) -> None:
    installed: list[GameInfo] = []
    registration = events.GAME_INSTALLED.register(installed.append)
    game_ids: list[str] = []

    async def run() -> None:
        game = await local_games.register_linux_game(str(executable), " Example Game ", '"two words" --flag')
        game_ids.append(game.id)
        duplicate = await local_games.register_linux_game(str(executable), game.name)
        game_ids.append(duplicate.id)
        assert game.id != duplicate.id
        assert (game.name, game.installed, game.runner, game.directory) == ("Example Game", True, "linux", None)
        launchable = Game(game.id)
        assert launchable.game_config_id != Game(duplicate.id).game_config_id
        gameplay = launchable.get_gameplay_info(CommandLineUIDelegate(None))
        result = subprocess.run(
            gameplay["command"], cwd=gameplay["working_dir"], check=True, capture_output=True, text=True, timeout=5
        )
        assert result.stdout.splitlines() == [str(executable.parent), "two words", "--flag"]
        assert await game_actions.get_installation_directory(game.id) == str(executable.parent)
        maintenance = await game_maintenance.get_maintenance_info(game.id)
        assert maintenance.installed and maintenance.files_unavailable_reason
        fake_main_loop.run_pending()
        assert installed == [game, duplicate]

    try:
        asyncio.run(run())
    finally:
        registration.unregister()
        for game_id in game_ids:
            games_db.delete_game(game_id)


def test_link_preserves_library_identity_and_categories(executable: Path) -> None:
    game_id = games_db.add_game(name="Existing Game", installed=0, playtime=2.5, directory="/old/game/directory")
    category_id = categories.add_category("local-game-registration-test")
    try:
        categories.add_game_to_category(game_id, category_id)
        game = asyncio.run(local_games.register_linux_game(str(executable), "", game_id=game_id))
        assert (game.id, game.name, game.playtime, game.directory) == (game_id, "Existing Game", 2.5, None)
        assert game.installed
        assert categories.get_categories_in_game(game_id) == ["local-game-registration-test"]
        with pytest.raises(LutrisError, match="cannot be linked"):
            asyncio.run(local_games.register_linux_game(str(executable), "", game_id=game_id))
    finally:
        categories.remove_category_from_game(game_id, category_id)
        categories.remove_category(category_id)
        games_db.delete_game(game_id)


def test_reject_invalid_executables_and_store_entries(executable: Path, tmp_path: Path) -> None:
    executable.chmod(0o600)
    with pytest.raises(LutrisError, match="not executable"):
        asyncio.run(local_games.register_linux_game(str(executable), "Invalid Game"))
    with pytest.raises(LutrisError, match="absolute path"):
        asyncio.run(local_games.register_linux_game("./relative-launcher", "Invalid Game"))

    executable.chmod(0o700)
    game_id = games_db.add_game(name="Store Game", installed=0, service="steam", runner="steam")
    try:
        with pytest.raises(LutrisError, match="cannot be linked"):
            asyncio.run(local_games.register_linux_game(str(executable), "", game_id=game_id))
        assert not Game(game_id).is_installed
        assert not (tmp_path / "config" / "games").exists()
    finally:
        games_db.delete_game(game_id)


def test_database_failure_removes_new_config(executable: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_to_add(**_fields: object) -> str:
        raise OSError("database failure")

    monkeypatch.setattr(games_db, "add_game", fail_to_add)
    with pytest.raises(OSError, match="database failure"):
        asyncio.run(local_games.register_linux_game(str(executable), "Test Game"))
    assert not list((Path(settings.CONFIG_DIR) / "games").iterdir())
    assert executable.exists()
