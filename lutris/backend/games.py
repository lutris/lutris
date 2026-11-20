"""Calls about the games in the library."""

import asyncio
import os
from collections.abc import Generator
from contextlib import contextmanager
from gettext import gettext as _
from typing import TYPE_CHECKING, Any

from lutris.api import parse_installer_url
from lutris.backend.models import GameInfo
from lutris.database import games as games_db
from lutris.delegates import CommandLineUIDelegate
from lutris.exceptions import LutrisError
from lutris.game import GAME_START, GAME_STOPPED, LOG_BUFFERS, Game
from lutris.game import export_game as _export_game
from lutris.game import import_game as _import_game
from lutris.util import resources
from lutris.util.log import logger
from lutris.util.standalone_scripts import generate_script

if TYPE_CHECKING:
    from lutris.delegates import LaunchUIDelegate


def to_game_info(db_game: dict[str, Any]) -> GameInfo:
    """Return the GameInfo for a game's database row."""
    slug = db_game.get("slug") or ""
    cover_path = resources.get_cover_path(slug) if slug else None
    return GameInfo(
        id=str(db_game["id"]),
        name=db_game.get("name") or "",
        slug=slug,
        runner=db_game.get("runner") or None,
        platform=db_game.get("platform") or None,
        year=db_game.get("year") or None,
        directory=db_game.get("directory") or None,
        installed=bool(db_game.get("installed")),
        playtime=db_game.get("playtime") or None,
        lastplayed=db_game.get("lastplayed") or None,
        service=db_game.get("service") or None,
        service_id=db_game.get("service_id") or None,
        installer_slug=db_game.get("installer_slug") or None,
        cover_path=cover_path if cover_path and os.path.exists(cover_path) else None,
    )


def game_info_from(game: "Game") -> GameInfo:
    """Return the GameInfo for a Game object: what the library records about it, as
    list_games() does, or if it isn't in the library (yet), what the object says,
    with an empty id."""
    db_game = games_db.get_game_by_field(game.id, "id") if game.id else None
    if db_game:
        return to_game_info(db_game)
    return to_game_info(
        {
            "id": game.id or "",
            "name": game.name,
            "slug": game.slug,
            "runner": game.runner_name,
            "platform": game.platform,
            "year": int(game.year) if str(game.year).isdigit() else None,
            "directory": game.directory,
            "installed": game.is_installed,
            "playtime": game.playtime,
            "lastplayed": game.lastplayed,
            "service": game.service,
            "service_id": game.appid,
        }
    )


# The games launched in this process and not stopped yet, by id
_running_games: dict[str, Game] = {}
_games_in_maintenance: set[str] = set()


@contextmanager
def _reserve_game_for_maintenance(game_id: str) -> Generator[None]:
    if game_id in _running_games:
        raise LutrisError(_("Stop the game before moving or removing it."))
    if _games_in_maintenance:
        raise LutrisError(_("Wait for the current game operation to finish."))
    _games_in_maintenance.add(game_id)
    try:
        yield
    finally:
        _games_in_maintenance.remove(game_id)


def _on_game_launching(game: Game) -> None:
    if game.id:
        _running_games.setdefault(game.id, game)


def _on_game_stopped(game: Game) -> None:
    if game.id and _running_games.get(game.id) is game:
        del _running_games[game.id]


GAME_START.register(_on_game_launching)
GAME_STOPPED.register(_on_game_stopped)


async def launch_game(game_id: str, launch_ui_delegate: "LaunchUIDelegate") -> bool:
    """Launch a game; the events in lutris.backend.events follow how it goes. Returns
    False if it can't be launched (it isn't installed, say), with nothing to follow."""
    if game_id in _running_games or game_id in _games_in_maintenance:
        return False
    game = Game(game_id)
    _running_games[game_id] = game
    if not game.launch(launch_ui_delegate):
        _running_games.pop(game_id, None)
        return False
    return True


async def launch_from_uri(uri: str) -> str:
    """Request a launch from a Lutris URI and return the target game's id."""
    try:
        request = parse_installer_url(uri)
    except ValueError as error:
        raise LutrisError(_("Invalid Lutris URI: %s") % uri) from error
    action = request.get("action")
    identifier = request.get("game_slug")
    if not identifier or action not in {None, "rungame", "rungameid"} or request.get("service"):
        raise LutrisError(_("This version of Lutris supports launch URIs for installed library games."))
    if action is None:
        game = await get_game(identifier) or await find_game(identifier)
    elif action == "rungameid":
        game = await get_game(identifier)
    else:
        matches = games_db.get_games_by_slug(identifier)
        if len(matches) > 1:
            raise LutrisError(_("Multiple games match %s. Use a game ID instead.") % identifier)
        game = to_game_info(matches[0]) if matches else None
    if not game or not game.installed:
        raise LutrisError(_("No installed game matches %s.") % identifier)
    if not await launch_game(game.id, CommandLineUIDelegate(request.get("launch_config_name"))):
        raise LutrisError(_("Could not launch %s.") % game.name)
    return game.id


async def stop_game(game_id: str) -> None:
    """Stop a running game, killing its processes if they don't quit."""
    game = _running_games.get(game_id)
    if game:
        game.force_stop()


async def list_running_game_ids() -> list[str]:
    """Return the ids of the games launched and not stopped yet."""
    return list(_running_games)


async def list_games(installed_only: bool = False) -> list[GameInfo]:
    """Return the games in the library, or only the installed ones."""
    db_games = games_db.get_games(filters=({"installed": 1} if installed_only else None))
    return [to_game_info(db_game) for db_game in db_games]


async def get_game_log(game_id: str) -> str:
    """Return the output collected for a game's most recent launch."""
    buffer = LOG_BUFFERS.get(game_id)
    return buffer.text if buffer else ""


async def get_game(game_id: str) -> GameInfo | None:
    """Return a game by its id, or None if the library has no such game."""
    db_game = games_db.get_game_by_field(game_id, "id")
    return to_game_info(db_game) if db_game else None


async def find_game(search: str) -> GameInfo | None:
    """Return the game whose id, slug or installer slug is search, in that order of
    preference, or None if there's none."""
    db_game = (
        games_db.get_game_by_field(search, "id")
        or games_db.get_game_by_field(search, "slug")
        or games_db.get_game_by_field(search, "installer_slug")
    )
    return to_game_info(db_game) if db_game and db_game["id"] else None


async def find_games_by_slug(slug: str) -> list[GameInfo]:
    """Return the games whose slug is slug or, if there are none, contains it."""
    db_games = games_db.get_games_by_slug(slug) or games_db.get_games(searches={"slug": slug})
    return [to_game_info(db_game) for db_game in db_games]


async def export_game(slug: str, dest_dir: str) -> None:
    """Archive a game's folder, with its Lutris configuration, into dest_dir."""
    await asyncio.to_thread(_export_game, slug, dest_dir)


async def import_game(file_path: str, dest_dir: str) -> None:
    """Add a game exported with export_game() to the library, unpacking it into dest_dir."""
    await asyncio.to_thread(_import_game, file_path, dest_dir)


async def write_game_script(game_id: str, script_path: str, launch_ui_delegate: "LaunchUIDelegate") -> None:
    """Write a shell script that runs a game without the client; launch_ui_delegate
    answers what its launch would ask, such as which configuration to use."""
    db_game = games_db.get_game_by_field(game_id, "id")
    if not db_game:
        raise ValueError("No game with id %s" % game_id)
    generate_script(logger, launch_ui_delegate, db_game, script_path)
