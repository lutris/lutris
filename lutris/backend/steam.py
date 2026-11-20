"""Calls about the local Steam libraries."""

import asyncio
import os

from lutris.backend.models import SteamGameInfo
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_dirs


async def list_steam_folders() -> list[str]:
    """Return the Steam library folders found on this computer."""
    return list(await asyncio.to_thread(get_steamapps_dirs))


def _read_steam_games() -> list[SteamGameInfo]:
    games = []
    for path in get_steamapps_dirs():
        for appmanifest_file in get_appmanifests(path):
            appmanifest = AppManifest(os.path.join(path, appmanifest_file))
            games.append(SteamGameInfo(appmanifest.steamid, appmanifest.name or None, tuple(appmanifest.states)))
    return games


async def list_steam_games() -> list[SteamGameInfo]:
    """Return the games installed in the local Steam libraries."""
    return await asyncio.to_thread(_read_steam_games)
