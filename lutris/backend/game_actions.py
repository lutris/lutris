"""Library game actions that are independent of a frontend."""

import asyncio
import os
from dataclasses import dataclass
from gettext import gettext as _

from lutris import settings
from lutris.database import categories, sql
from lutris.exceptions import LutrisError
from lutris.game import Game


@dataclass(frozen=True)
class CategoryMembership:
    name: str
    included: bool


@dataclass(frozen=True)
class GameOrganization:
    favorite: bool
    hidden: bool
    categories: tuple[CategoryMembership, ...]


async def get_organization(game_id: str) -> GameOrganization:
    """Return a game's memberships and the categories it can be added to."""
    return await asyncio.to_thread(_get_organization, game_id)


def _get_organization(game_id: str) -> GameOrganization:
    memberships = set(categories.get_categories_in_game(game_id))
    names = sorted(
        (
            str(row["name"])
            for row in categories.get_categories()
            if not categories.is_reserved_category(str(row["name"]))
        ),
        key=str.casefold,
    )
    return GameOrganization(
        favorite="favorite" in memberships,
        hidden=".hidden" in memberships,
        categories=tuple(CategoryMembership(name, name in memberships) for name in names),
    )


async def set_favorite(game_id: str, favorite: bool) -> None:
    """Set the game's Favorites membership."""
    await asyncio.to_thread(_set_membership, game_id, "favorite", favorite)


async def set_hidden(game_id: str, hidden: bool) -> None:
    """Set whether the game is hidden from the regular library."""
    await asyncio.to_thread(_set_membership, game_id, ".hidden", hidden)


async def set_category(game_id: str, name: str, included: bool) -> None:
    """Add or remove a game from a user category, creating the category when needed."""
    name = categories.strip_category_name(name)
    if categories.is_reserved_category(name):
        raise LutrisError(_("Enter a category name that Lutris does not reserve."))
    await asyncio.to_thread(_set_membership, game_id, name, included)


def _set_membership(game_id: str, name: str, included: bool) -> None:
    with sql.db_cursor(settings.DB_PATH) as cursor:
        cursor.execute("BEGIN IMMEDIATE")
        if not cursor.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone():
            raise LutrisError(_("This game is no longer in the library."))
        if included:
            cursor.execute(
                "INSERT INTO categories (name) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = ?)",
                (name, name),
            )
            cursor.execute(
                "INSERT INTO games_categories (game_id, category_id) SELECT ?, id FROM categories WHERE name = ? "
                "AND NOT EXISTS (SELECT 1 FROM games_categories WHERE game_id = ? AND category_id = categories.id)",
                (game_id, name, game_id),
            )
        else:
            cursor.execute(
                "DELETE FROM games_categories WHERE game_id = ? "
                "AND category_id IN (SELECT id FROM categories WHERE name = ?)",
                (game_id, name),
            )
        changed = cursor.rowcount > 0
    if changed:
        categories.CATEGORIES_UPDATED.fire()


async def get_installation_directory(game_id: str) -> str:
    """Return the existing directory that the frontend can open in the file manager."""
    path = await asyncio.to_thread(lambda: Game(game_id).get_browse_dir())
    if not path or not os.path.isdir(path):
        raise LutrisError(_("This game has no existing installation directory."))
    return os.path.abspath(path)
