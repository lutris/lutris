"""Commands that list games, Steam libraries, runners and Wine versions."""

import json
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from gi.repository import GLib

from lutris.api import get_runners
from lutris.cli.output import CommandOutput
from lutris.database import games as games_db
from lutris.database.services import ServiceGameCollection
from lutris.runners import get_runner_names
from lutris.util import resources
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_dirs

if TYPE_CHECKING:
    from lutris.database.games import DbGameDict
    from lutris.database.services import DBServiceGame


def list_games(options: GLib.VariantDict, output: CommandOutput) -> None:
    """List the games in the library (--list-games)."""
    game_list = games_db.get_games(filters=({"installed": 1} if options.contains("installed") else None))
    if options.contains("json"):
        print_game_json(output, game_list)
    else:
        print_game_list(output, game_list)


def list_service_games(options: GLib.VariantDict, output: CommandOutput, service: str | None = None) -> None:
    """List the games of one service (--list-service-games), or of all of them
    (--list-all-service-games), with whether each is installed."""
    installed_games = games_db.get_games(filters={"installed": 1})
    if service:
        installed_games = [game for game in installed_games if game["service"] == service]
        service_game_list = ServiceGameCollection.get_for_service(service)
    else:
        service_game_list = ServiceGameCollection.get_service_games()
    for db_game in service_game_list:
        db_game["installed"] = any(
            game.get("service_id") == db_game["appid"]
            for game in installed_games
            if game["service"] == db_game["service"]
        )
    if options.contains("installed"):
        service_game_list = [d for d in service_game_list if d["installed"]]
    if options.contains("json"):
        print_service_game_json(output, service_game_list)
    else:
        print_service_game_list(output, service_game_list)


def print_game_list(output: CommandOutput, game_list: list["DbGameDict"]) -> None:
    for game in game_list:
        output.print(
            "{:4} | {:<40} | {:<40} | {:<15} | {:<64}".format(
                game["id"],
                game["name"][:40],
                game["slug"][:40],
                game["runner"] or "-",
                game["directory"] or "-",
            )
        )


def print_game_json(output: CommandOutput, game_list: list["DbGameDict"]) -> None:
    games = []

    for game in game_list:
        playtime = timedelta(hours=game["playtime"]) if game["playtime"] else None
        cover_path = resources.get_cover_path(game["slug"]) if game["slug"] else None

        if cover_path and not os.path.exists(cover_path):
            cover_path = None

        game_obj = {
            "id": game["id"],
            "slug": game["slug"],
            "name": game["name"],
            "runner": game["runner"],
            "platform": game["platform"] or None,
            "year": game["year"] or None,
            "directory": game["directory"] or None,
            "playtime": str(playtime) if playtime else None,
            "playtimeSeconds": playtime.total_seconds() if playtime else None,
            "lastplayed": (str(datetime.fromtimestamp(game["lastplayed"])) if game["lastplayed"] else None),
            "coverPath": cover_path,
        }

        games.append(game_obj)

    output.print(json.dumps(games, indent=2))


def print_service_game_list(output: CommandOutput, game_list: list["DBServiceGame"]) -> None:
    for game in game_list:
        output.print(
            "{:4} | {:<40} | {:<40} | {:<15} | {:<15}".format(
                game["id"],
                str(game["name"])[:40],
                str(game["slug"])[:40],
                str(game["service"])[:15],
                "true" if game["installed"] else "false"[:15],
            )
        )


def print_service_game_json(output: CommandOutput, game_list: list["DBServiceGame"]) -> None:
    games = [
        {
            "id": game["id"],
            "slug": game["slug"],
            "name": game["name"],
            "service": game["service"],
            "appid": game["appid"],
            "installed": game["installed"],
            "details": game["details"],
        }
        for game in game_list
    ]
    output.print(json.dumps(games, indent=2))


def print_steam_list(output: CommandOutput) -> None:
    for path in get_steamapps_dirs():
        appmanifest_files = get_appmanifests(path)
        for appmanifest_file in appmanifest_files:
            appmanifest = AppManifest(os.path.join(path, appmanifest_file))
            output.print(
                " {:8} | {:<60} | {}".format(
                    appmanifest.steamid,
                    appmanifest.name or "-",
                    ", ".join(appmanifest.states),
                )
            )


def print_steam_folders(output: CommandOutput) -> None:
    for path in get_steamapps_dirs():
        output.print(path)


def print_runners(output: CommandOutput) -> None:
    for name in sorted(get_runner_names(), key=lambda x: x.lower()):
        output.print(name)


def print_wine_runners(output: CommandOutput) -> None:
    for version in get_runners("wine")["versions"]:
        if version["version"]:
            output.print(str(version))
