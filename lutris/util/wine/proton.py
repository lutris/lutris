"""Utility module to deal with Proton and umu"""
import json
import os
from gettext import gettext as _
from typing import Generator, List

from lutris import settings
from lutris.util import system
from lutris.util.steam.config import get_steamapps_dirs

GE_PROTON_LATEST = _("GE-Proton (Latest)")
DEFAULT_GAMEID = "umu-default"

def is_proton_path(wine_path):
    return "Proton" in wine_path and "lutris" not in wine_path


def get_umu_path():
    custom_path = settings.read_setting("umu_path")
    if custom_path:
        script_path = os.path.join(custom_path, "umu_run.py")
        if system.path_exists(script_path):
            return script_path
    if system.can_find_executable("umu-run"):
        return system.find_executable("umu-run")
    path_candidates = (
        "/app/share",  # prioritize flatpak due to non-rolling release distros
        "/usr/local/share",
        "/usr/share",
        "/opt",
        settings.RUNTIME_DIR,
    )
    for path_candidate in path_candidates:
        script_path = os.path.join(path_candidate, "umu", "umu_run.py")
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
    umu_path = get_umu_path()
    if not umu_path:
        return []
    versions = [GE_PROTON_LATEST]
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
    games_path = os.path.join(settings.RUNTIME_DIR, "umu-games/umu-games.json")
    if not os.path.exists(games_path):
        return DEFAULT_GAMEID
    with open(games_path, "r", encoding="utf-8") as games_file:
        umu_games = json.load(games_file)
    for umu_game in umu_games:
        if (
            umu_game["store"]
            and (
                umu_game["store"] == game.service
                or (umu_game["store"] == "humble" and game.service == "humblebundle")
            )
            and umu_game["appid"] == game.appid
        ):
            return umu_game["umu_id"]
    return DEFAULT_GAMEID
