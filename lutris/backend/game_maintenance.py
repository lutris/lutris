"""Move and uninstall library games without a frontend dependency."""

import asyncio
import re
import shutil
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path
from typing import Any

import yaml

from lutris import settings
from lutris.backend import events, games
from lutris.database import games as games_db
from lutris.database import sql
from lutris.exceptions import LutrisError
from lutris.game import GAME_UPDATED, Game
from lutris.util import system
from lutris.util.library_sync import LibrarySyncer
from lutris.util.log import logger
from lutris.util.path_cache import remove_from_path_cache
from lutris.util.yaml import write_yaml_to_file

_EXTERNALLY_MANAGED_RUNNERS = {"steam", "flatpak", "web"}


@dataclass(frozen=True)
class GameMaintenanceInfo:
    installed: bool
    directory: str
    files_unavailable_reason: str


def _load_game(game_id: str) -> Game:
    if games_db.get_game_by_field(game_id, "id") is None:
        raise LutrisError(_("This game is no longer in the library."))
    return Game(game_id)


def _overlaps_installation(game_id: str, directory: Path) -> bool:
    for row in games_db.get_games(filters={"installed": 1}):
        if str(row["id"]) != game_id and (other := row.get("directory")):
            other_path = Path(other).expanduser().resolve()
            if other_path.is_relative_to(directory) or (
                len(other_path.parts) >= 3 and directory.is_relative_to(other_path)
            ):
                return True
    return False


def _files_unavailable_reason(game: Game, directory: Path) -> str:
    if game.runner_name in _EXTERNALLY_MANAGED_RUNNERS:
        return _("This installation is managed outside Lutris.")
    if not directory.is_absolute() or not directory.is_dir():
        return _("This game has no existing installation folder.")
    resolved = directory.resolve()
    config = game.config
    default_folder = config.system_config.get("game_path") if config else None
    if (
        directory.is_symlink()
        or len(resolved.parts) < 3
        or resolved.is_mount()
        or Path.home().resolve().is_relative_to(resolved)
        or (default_folder and Path(default_folder).expanduser().resolve().is_relative_to(resolved))
        or not system.is_removeable(str(directory), {})
        or not system.is_removeable(str(resolved), {})
    ):
        return _("This installation folder is protected.")
    if _overlaps_installation(game.id, resolved):
        return _("This installation folder overlaps another installed game.")
    return ""


def _describe_game(game: Game) -> GameMaintenanceInfo:
    directory = str(Path(game.directory).expanduser()) if game.directory else ""
    reason = _files_unavailable_reason(game, Path(directory)) if game.is_installed else ""
    return GameMaintenanceInfo(game.is_installed, directory, reason)


async def get_maintenance_info(game_id: str) -> GameMaintenanceInfo:
    """Describe the installation and whether Lutris can move or trash its files."""
    return await asyncio.to_thread(lambda: _describe_game(_load_game(game_id)))


def _checked_directory(game: Game, expected_directory: str) -> Path:
    info = _describe_game(game)
    if not info.installed or info.directory != expected_directory:
        raise LutrisError(_("The installation changed. Reopen this dialog before trying again."))
    if info.files_unavailable_reason:
        raise LutrisError(info.files_unavailable_reason)
    return Path(info.directory)


async def _run_maintenance[Result](game_id: str, operation: Callable[[], Coroutine[Any, Any, Result]]) -> Result:
    with games._reserve_game_for_maintenance(game_id):
        task = asyncio.create_task(operation())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise


async def move_game(game_id: str, expected_directory: str, destination_parent: str) -> str:
    """Move the installation under an existing folder and return its new path."""
    return await _run_maintenance(
        game_id, lambda: _move_game_and_notify(game_id, expected_directory, destination_parent)
    )


async def _move_game_and_notify(game_id: str, expected_directory: str, destination_parent: str) -> str:
    directory = await asyncio.to_thread(_move_game, game_id, expected_directory, destination_parent)
    game = _load_game(game_id)
    _forget_cached_path(game)
    GAME_UPDATED.fire(game)
    return str(directory)


def _replace_path(value: object, source: re.Pattern[str], target: str) -> object:
    if isinstance(value, str):
        return source.sub(lambda _match: target, value)
    if isinstance(value, dict):
        return {key: _replace_path(item, source, target) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_path(item, source, target) for item in value]
    return value


def _move_game(game_id: str, expected_directory: str, destination_parent: str) -> Path:
    game = _load_game(game_id)
    source = _checked_directory(game, expected_directory)
    parent = Path(destination_parent)
    if not parent.is_absolute() or not parent.is_dir():
        raise LutrisError(_("Choose an existing destination folder."))
    if parent.resolve().is_relative_to(source.resolve()):
        raise LutrisError(_("Choose a destination outside the installation folder."))
    target = parent / source.name
    if target.exists() or target.is_symlink():
        raise LutrisError(_("The destination already contains %s.") % source.name)
    if _overlaps_installation(game_id, target.resolve()):
        raise LutrisError(_("The destination overlaps another installed game."))

    config = game.config
    config_path = config.game_config_path if config else None
    if not config_path or not Path(config_path).is_file():
        raise LutrisError(_("This game has no configuration file to update after moving it."))
    previous_config_bytes = Path(config_path).read_bytes()
    previous_config = yaml.safe_load(previous_config_bytes) or {}
    if not isinstance(previous_config, dict):
        raise LutrisError(_("This game's configuration file is invalid."))
    source_paths = "|".join(map(re.escape, dict.fromkeys((str(source), game.directory))))
    pattern = re.compile(rf"(?<![^=\s'\";:])(?:{source_paths})(?=$|[/\s'\";:])")
    updated_config = {key: _replace_path(value, pattern, str(target)) for key, value in previous_config.items()}

    shutil.move(source, parent)
    config_updated = False
    try:
        if updated_config != previous_config:
            write_yaml_to_file(updated_config, config_path)
            config_updated = True
        updated = sql.db_update(
            settings.DB_PATH,
            "games",
            {"directory": str(target)},
            {"id": game_id, "directory": game.directory, "installed": 1},
        )
        if updated.rowcount != 1:
            raise LutrisError(_("The installation changed during the move."))
    except Exception:
        try:
            shutil.move(target, source.parent)
            if config_updated:
                Path(config_path).write_bytes(previous_config_bytes)
        except OSError as rollback_error:
            raise LutrisError(
                _("Could not restore the installation after a failed move. Check %s and %s.") % (source, target)
            ) from rollback_error
        raise
    return target


async def uninstall_game(
    game_id: str, expected: GameMaintenanceInfo, *, trash_files: bool = False, remove_from_library: bool = False
) -> None:
    """Clear the installation and optionally trash its folder or remove the library entry."""
    await _run_maintenance(game_id, lambda: _uninstall_game(game_id, expected, trash_files, remove_from_library))


async def _uninstall_game(
    game_id: str, expected: GameMaintenanceInfo, trash_files: bool, remove_from_library: bool
) -> None:
    game = _load_game(game_id)
    current = await asyncio.to_thread(_describe_game, game)
    if (current.installed, current.directory) != (expected.installed, expected.directory):
        raise LutrisError(_("The installation changed. Reopen this dialog before trying again."))
    if trash_files:
        if not current.installed:
            raise LutrisError(_("This game is not installed."))
        if current.files_unavailable_reason:
            raise LutrisError(current.files_unavailable_reason)
        await _trash_directory(current.directory)
    if not current.installed and not remove_from_library:
        return
    record = games_db.get_game_by_field(game_id, "id") if remove_from_library else None
    try:
        if game.is_installed:
            await asyncio.to_thread(game.uninstall)
            _forget_cached_path(game)
        if remove_from_library:
            await asyncio.to_thread(game.delete)
    finally:
        if remove_from_library and games_db.get_game_by_field(game_id, "id") is None:
            events.GAME_REMOVED.fire(game_id)
        else:
            GAME_UPDATED.fire(_load_game(game_id))
    if record and settings.read_bool_setting("library_sync_enabled", True):
        try:
            await asyncio.to_thread(lambda: LibrarySyncer().delete_from_remote_library([record]))
        except Exception:
            logger.exception("Could not remove game %s from the remote library", game_id)


def _forget_cached_path(game: Game) -> None:
    try:
        remove_from_path_cache(game)
    except OSError:
        logger.exception("Could not clear the cached path for %s", game)


async def _trash_directory(directory: str) -> None:
    done = asyncio.get_running_loop().create_future()
    system.remove_folder(directory, lambda: done.set_result(None), done.set_exception)
    await done
