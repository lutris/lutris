"""Calls about syncing game saves; experimental, and they print their results."""

import asyncio

from lutris.game import Game
from lutris.util import savesync


async def show_save_stats(game_id: str, output_format: str = "text") -> None:
    """Print which save files a game has, as text or JSON."""
    await asyncio.to_thread(savesync.show_save_stats, Game(game_id), output_format)


async def upload_saves(game_id: str) -> None:
    """Upload a game's save files."""
    await asyncio.to_thread(savesync.upload_save, Game(game_id))


async def check_saves(game_id: str) -> None:
    """Print whether a game's save files are in sync."""
    await asyncio.to_thread(savesync.save_check, Game(game_id))
