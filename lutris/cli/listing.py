"""Commands that list games, Steam libraries, runners and Wine versions."""

import json
from datetime import datetime, timedelta

from gi.repository import GLib

from lutris.backend import games, runners, services, steam
from lutris.backend.models import GameInfo, ServiceGameInfo
from lutris.cli.output import CommandOutput


async def list_games(options: GLib.VariantDict, output: CommandOutput) -> None:
    """List the games in the library (--list-games)."""
    game_list = await games.list_games(installed_only=options.contains("installed"))
    if options.contains("json"):
        print_game_json(output, game_list)
    else:
        print_game_list(output, game_list)


async def list_service_games(options: GLib.VariantDict, output: CommandOutput, service: str | None = None) -> None:
    """List the games of one service (--list-service-games), or of all of them
    (--list-all-service-games), with whether each is installed."""
    game_list = await services.list_service_games(service, installed_only=options.contains("installed"))
    if options.contains("json"):
        print_service_game_json(output, game_list)
    else:
        print_service_game_list(output, game_list)


def print_game_list(output: CommandOutput, game_list: list[GameInfo]) -> None:
    for game in game_list:
        output.print(
            "{:4} | {:<40} | {:<40} | {:<15} | {:<64}".format(
                game.id,
                game.name[:40],
                game.slug[:40],
                game.runner or "-",
                game.directory or "-",
            )
        )


def print_game_json(output: CommandOutput, game_list: list[GameInfo]) -> None:
    games_json = []

    for game in game_list:
        playtime = timedelta(hours=game.playtime) if game.playtime else None
        games_json.append(
            {
                "id": game.id,
                "slug": game.slug,
                "name": game.name,
                "runner": game.runner,
                "platform": game.platform,
                "year": game.year,
                "directory": game.directory,
                "playtime": str(playtime) if playtime else None,
                "playtimeSeconds": playtime.total_seconds() if playtime else None,
                "lastplayed": (str(datetime.fromtimestamp(game.lastplayed)) if game.lastplayed else None),
                "coverPath": game.cover_path,
            }
        )

    output.print(json.dumps(games_json, indent=2))


def print_service_game_list(output: CommandOutput, game_list: list[ServiceGameInfo]) -> None:
    for game in game_list:
        output.print(
            "{:4} | {:<40} | {:<40} | {:<15} | {:<15}".format(
                game.id,
                game.name[:40],
                game.slug[:40],
                game.service[:15],
                "true" if game.installed else "false",
            )
        )


def print_service_game_json(output: CommandOutput, game_list: list[ServiceGameInfo]) -> None:
    games_json = [
        {
            "id": int(game.id),
            "slug": game.slug,
            "name": game.name,
            "service": game.service,
            "appid": game.appid,
            "installed": game.installed,
            "details": game.details,
        }
        for game in game_list
    ]
    output.print(json.dumps(games_json, indent=2))


async def print_steam_list(output: CommandOutput) -> None:
    for game in await steam.list_steam_games():
        output.print(" {:8} | {:<60} | {}".format(game.appid, game.name or "-", ", ".join(game.states)))


async def print_steam_folders(output: CommandOutput) -> None:
    for path in await steam.list_steam_folders():
        output.print(path)


async def print_runners(output: CommandOutput) -> None:
    for name in await runners.list_runners():
        output.print(name)


async def print_wine_runners(output: CommandOutput) -> None:
    for version in await runners.list_wine_versions():
        output.print(str(version))
