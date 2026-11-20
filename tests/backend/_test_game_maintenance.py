"""Exercise game maintenance with real files and library records."""

import asyncio
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml

from lutris import settings
from lutris.backend import game_maintenance, games
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exceptions import LutrisError
from lutris.game import Game
from lutris.util import path_cache, system
from lutris.util.test_config import setup_test_environment

setup_test_environment()


@pytest.fixture
def installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, Path, Path]]:
    directory = tmp_path / "Game Data"
    directory.mkdir()
    (directory / "play.sh").touch()
    config = tmp_path / "games" / "maintenance.yml"
    config.parent.mkdir()
    config.write_text(
        yaml.safe_dump(
            {
                "game": {
                    "exe": str(directory / "play.sh"),
                    "args": f'--path="{directory}/profile" --shared="{directory}-backup"',
                    "launch_configs": [{"name": "Windowed", "exe": str(directory / "play.sh")}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(path_cache, "GAME_PATH_CACHE_PATH", str(tmp_path / "path-cache.json"))
    monkeypatch.setattr(settings, "read_bool_setting", lambda *_args: False)
    game_id = str(
        games_db.add_game(
            name="Maintenance Test",
            slug="maintenance-test",
            installed=1,
            runner="linux",
            directory=str(directory),
            configpath="maintenance",
            playtime=4.5,
        )
    )
    try:
        yield game_id, directory, config
    finally:
        games_db.delete_game(game_id)


def test_move_updates_paths_and_preserves_library_metadata(
    installation: tuple[str, Path, Path], tmp_path: Path
) -> None:
    game_id, source, config = installation
    parent = tmp_path / "Destination's Folder"
    parent.mkdir()
    target = parent / source.name

    assert asyncio.run(game_maintenance.move_game(game_id, str(source), str(parent))) == str(target)
    assert not source.exists()
    assert (target / "play.sh").is_file()
    game = asyncio.run(games.get_game(game_id))
    assert game and game.directory == str(target) and game.playtime == 4.5
    updated = yaml.safe_load(config.read_text(encoding="utf-8"))["game"]
    assert updated["exe"] == str(target / "play.sh")
    assert updated["launch_configs"][0]["exe"] == str(target / "play.sh")
    assert updated["args"] == f'--path="{target}/profile" --shared="{source}-backup"'


def test_move_failure_does_not_change_the_installation(
    installation: tuple[str, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, source, config = installation
    parent = tmp_path / "Destination"
    parent.mkdir()
    original_config = config.read_bytes()

    def fail_to_move(_source: Path, _target: Path) -> None:
        raise PermissionError("test move failed")

    with monkeypatch.context() as patch:
        patch.setattr(game_maintenance.shutil, "move", fail_to_move)
        with pytest.raises(PermissionError, match="test move failed"):
            asyncio.run(game_maintenance.move_game(game_id, str(source), str(parent)))
    assert Game(game_id).directory == str(source)
    assert config.read_bytes() == original_config

    def fail_to_record_move(*_args: object) -> None:
        raise OSError("test database write failed")

    monkeypatch.setattr(game_maintenance.sql, "db_update", fail_to_record_move)
    with pytest.raises(OSError, match="test database write failed"):
        asyncio.run(game_maintenance.move_game(game_id, str(source), str(parent)))
    assert (source / "play.sh").is_file() and not (parent / source.name).exists()
    assert Game(game_id).directory == str(source)
    assert config.read_bytes() == original_config


def test_move_rejects_an_existing_target_and_running_game(installation: tuple[str, Path, Path], tmp_path: Path) -> None:
    game_id, source, _config = installation
    parent = tmp_path / "Destination"
    parent.mkdir()
    (parent / source.name).mkdir()
    with pytest.raises(LutrisError, match="already contains"):
        asyncio.run(game_maintenance.move_game(game_id, str(source), str(parent)))
    other_folder = tmp_path / "Other Game"
    other_folder.mkdir()
    other_game = str(
        games_db.add_game(name="Other Game", slug="other-maintenance", installed=1, directory=str(other_folder))
    )
    try:
        with pytest.raises(LutrisError, match="destination overlaps"):
            asyncio.run(game_maintenance.move_game(game_id, str(source), str(other_folder)))
    finally:
        games_db.delete_game(other_game)
    games._running_games[game_id] = Game(game_id)
    try:
        with pytest.raises(LutrisError, match="Stop the game"):
            asyncio.run(game_maintenance.move_game(game_id, str(source), str(parent)))
    finally:
        del games._running_games[game_id]
    assert (source / "play.sh").exists()


def test_trash_rechecks_shared_folders_and_changed_paths(
    installation: tuple[str, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, source, _config = installation
    info = asyncio.run(game_maintenance.get_maintenance_info(game_id))
    assert not info.files_unavailable_reason

    def unexpected_trash(*_args: object) -> None:
        pytest.fail("Trashing must be refused")

    monkeypatch.setattr(system, "remove_folder", unexpected_trash)
    other = str(games_db.add_game(name="Shared", slug="shared-maintenance", installed=1, directory=str(source / "mod")))
    try:
        with pytest.raises(LutrisError, match="overlaps another installed game"):
            asyncio.run(game_maintenance.uninstall_game(game_id, info, trash_files=True))
    finally:
        games_db.delete_game(other)

    alias = tmp_path / "Game Alias"
    alias.symlink_to(source, target_is_directory=True)
    sql.db_update(settings.DB_PATH, "games", {"directory": str(alias)}, {"id": game_id})
    with pytest.raises(LutrisError, match="installation changed"):
        asyncio.run(game_maintenance.uninstall_game(game_id, info, trash_files=True))
    info = asyncio.run(game_maintenance.get_maintenance_info(game_id))
    assert "protected" in info.files_unavailable_reason
    assert Game(game_id).is_installed and source.is_dir()


def test_uninstall_waits_for_trash_and_retains_the_entry(
    installation: tuple[str, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, source, config = installation
    info = asyncio.run(game_maintenance.get_maintenance_info(game_id))

    def refused(_path: str, _done: Callable[[], None], failed: Callable[[Exception], None]) -> None:
        failed(OSError("Trash is unavailable"))

    monkeypatch.setattr(system, "remove_folder", refused)
    with pytest.raises(OSError, match="Trash is unavailable"):
        asyncio.run(game_maintenance.uninstall_game(game_id, info, trash_files=True, remove_from_library=True))
    assert Game(game_id).is_installed and config.exists() and source.exists()

    def trash(path: str, done: Callable[[], None], _failed: Callable[[Exception], None]) -> None:
        def complete() -> None:
            assert Game(game_id).is_installed
            shutil.rmtree(path)
            done()

        asyncio.get_running_loop().call_soon(complete)

    monkeypatch.setattr(system, "remove_folder", trash)
    asyncio.run(game_maintenance.uninstall_game(game_id, info, trash_files=True))
    assert not source.exists() and not config.exists()
    game = asyncio.run(games.get_game(game_id))
    assert game and not game.installed and game.playtime == 4.5

    current = asyncio.run(game_maintenance.get_maintenance_info(game_id))
    asyncio.run(game_maintenance.uninstall_game(game_id, current, remove_from_library=True))
    assert asyncio.run(games.get_game(game_id)) is None
