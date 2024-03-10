"""Utility module to deal with Proton and ULWGL"""
import json
import os
from typing import Generator, List

from lutris import settings
from lutris.util import system
from lutris.util.steam.config import get_steamapps_dirs


def is_proton_path(wine_path):
    return "Proton" in wine_path and "lutris" not in wine_path


def get_ulwgl_path():
    custom_path = settings.read_setting("ulwgl_path")
    if custom_path:
        script_path = os.path.join(custom_path, "ulwgl_run.py")
        if system.path_exists(script_path):
            return script_path
    if system.can_find_executable("ulwgl-run"):
        return system.find_executable("ulwgl-run")
    path_candidates = (
        os.path.expanduser("~/.local/share"),
        "/usr/local/share",
        "/usr/share",
        "/opt",
        settings.RUNTIME_DIR,
    )
    for path_candidate in path_candidates:
        script_path = os.path.join(path_candidate, "ULWGL", "ulwgl_run.py")
        if system.path_exists(script_path):
            return script_path


def _iter_proton_locations() -> Generator[str, None, None]:
    """Iterate through all existing Proton locations"""
    try:
        steamapp_dirs = get_steamapps_dirs()
    except:
        return  # in case of corrupt or unreadable Steam configuration files!

    for path in [os.path.join(p, "common") for p in steamapp_dirs]:
        if os.path.isdir(path):
            yield path
    for path in [os.path.join(p, "") for p in steamapp_dirs]:
        if os.path.isdir(path):
            yield path


def get_proton_paths() -> List[str]:
    """Get the Folder that contains all the Proton versions. Can probably be improved"""
    paths = set()
    for proton_path in _iter_proton_locations():
        for version in [p for p in os.listdir(proton_path) if "Proton" in p]:
            if system.path_exists(os.path.join(proton_path, version, "dist/bin/wine")):
                paths.add(proton_path)
            if system.path_exists(os.path.join(proton_path, version, "files/bin/wine")):
                paths.add(proton_path)
    return list(paths)


def list_proton_versions() -> List[str]:
    """Return the list of Proton versions installed in Steam"""
    ulwgl_path = get_ulwgl_path()
    if not ulwgl_path:
        return []
    versions = ["GE-Proton (Latest)"]
    for proton_path in get_proton_paths():
        for version in [p for p in os.listdir(proton_path) if "Proton" in p]:
            path = os.path.join(proton_path, version, "dist/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
            path = os.path.join(proton_path, version, "files/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
    return versions


def get_proton_bin_for_version(version):
    for proton_path in get_proton_paths():
        path = os.path.join(proton_path, version, "dist/bin/wine")
        if os.path.isfile(path):
            return path
        path = os.path.join(proton_path, version, "files/bin/wine")
        if os.path.isfile(path):
            return path


def get_proton_path_from_bin(wine_path):
    """Return a location suitable for PROTONPATH from the wine executable"""
    return os.path.abspath(os.path.join(os.path.dirname(wine_path), "../../"))


def get_game_id(game):
    default_id = "ULWGL-default"
    games_path = os.path.join(settings.RUNTIME_DIR, "ulwgl-games/ulwgl-games.json")
    if not os.path.exists(games_path):
        return default_id
    with open(games_path, "r", encoding="utf-8") as games_file:
        ulwgl_games = json.load(games_file)
    for ulwgl_game in ulwgl_games:
        if (
            ulwgl_game["store"]
            and (
                ulwgl_game["store"] == game.service
                or (ulwgl_game["store"] == "humble" and game.service == "humblebundle")
            )
            and ulwgl_game["appid"] == game.appid
        ):
            return ulwgl_game["ulwgl_id"]
    return default_id
