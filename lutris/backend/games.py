"""Calls about the games in the library."""

import asyncio
import os
from typing import TYPE_CHECKING, Any

from lutris.backend.models import GameInfo
from lutris.database import games as games_db
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


async def list_games(installed_only: bool = False) -> list[GameInfo]:
    """Return the games in the library, or only the installed ones."""
    db_games = games_db.get_games(filters=({"installed": 1} if installed_only else None))
    return [to_game_info(db_game) for db_game in db_games]


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
