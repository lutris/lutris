"""Steam service"""
import os
import re

from lutris import pga
from lutris.util.log import logger
from lutris.config import make_game_config_id, LutrisConfig
from lutris.util.steam.appmanifest import AppManifest, get_appmanifests
from lutris.util.steam.config import get_steamapps_paths

NAME = "Steam"
ICON = "steam"


def mark_as_installed(steamid, runner_name, game_info):
    """Sets a Steam game as installed"""
    for key in ["name", "slug"]:
        if key not in game_info:
            raise ValueError("Missing %s field in %s" % (key, game_info))
    logger.info("Setting %s as installed", game_info["name"])
    config_id = game_info.get("config_path") or make_game_config_id(game_info["slug"])
    game_id = pga.add_or_update(
        id=game_info.get("id"),
        steamid=int(steamid),
        name=game_info["name"],
        runner=runner_name,
        slug=game_info["slug"],
        installed=1,
        configpath=config_id,
    )

    game_config = LutrisConfig(runner_slug=runner_name, game_config_id=config_id)
    game_config.raw_game_config.update({"appid": steamid})
    game_config.save()
    return game_id


def mark_as_uninstalled(game_info):
    for key in ("id", "name"):
        if key not in game_info:
            raise ValueError("Missing %s field in %s" % (key, game_info))
    logger.info("Setting %s as uninstalled", game_info["name"])
    game_id = pga.add_or_update(id=game_info["id"], runner="", installed=0)
    return game_id


def sync_appmanifest_state(appmanifest_path, update=None):
    """Given a Steam appmanifest reflect it's state in a Lutris game

    Params:
        appmanifest_path (str): Path to the Steam AppManifest file
        update (dict, optional): Existing lutris game to update
    """

    try:
        appmanifest = AppManifest(appmanifest_path)
    except Exception:
        logger.error("Unable to parse file %s", appmanifest_path)
        return
    if appmanifest.is_installed():
        if update:
            game_info = update
        else:
            game_info = {"name": appmanifest.name, "slug": appmanifest.slug}
        runner_name = appmanifest.get_runner_name()
        mark_as_installed(appmanifest.steamid, runner_name, game_info)


def sync_with_lutris(games, platform="linux"):
    logger.debug("Syncing Steam for %s games to Lutris", platform.capitalize())
    steamapps_paths = get_steamapps_paths()
    steam_games_in_lutris = pga.get_games_where(steamid__isnull=False, steamid__not="")
    proton_ids = ["858280", "930400", "961940", "228980"]
    steamids_in_lutris = {str(game["steamid"]) for game in steam_games_in_lutris}
    seen_ids = set()  # Set of Steam appids seen while browsing AppManifests

    for steamapps_path in steamapps_paths[platform]:
        appmanifests = get_appmanifests(steamapps_path)
        for appmanifest_file in appmanifests:
            steamid = re.findall(r"(\d+)", appmanifest_file)[0]
            seen_ids.add(steamid)
            appmanifest_path = os.path.join(steamapps_path, appmanifest_file)
            if steamid not in steamids_in_lutris and steamid not in proton_ids:
                # New Steam game, not seen before in Lutris,
                if platform != "linux":
                    # Windows games might require additional steps.
                    # TODO: Find a way to mark games as "Not fully configured"
                    # as the status.
                    logger.warning(
                        "Importing Steam game %s but game might require additional configuration"
                    )
                sync_appmanifest_state(appmanifest_path)
            else:
                # Lookup previously installed Steam games
                pga_entry = None
                for game in steam_games_in_lutris:
                    if str(game["steamid"]) == steamid and not game["installed"]:
                        logger.debug(
                            "Matched previously installed game %s", game["name"]
                        )
                        pga_entry = game
                        break
                if pga_entry:
                    sync_appmanifest_state(appmanifest_path, update=pga_entry)

    unavailable_ids = steamids_in_lutris.difference(seen_ids)
    for steamid in unavailable_ids:
        for game in steam_games_in_lutris:
            runner = "steam" if platform == "linux" else "winesteam"
            if (
                    str(game["steamid"]) == steamid
                    and game["installed"]
                    and game["runner"] == runner
            ):
                mark_as_uninstalled(game)
