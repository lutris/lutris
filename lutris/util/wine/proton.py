"""Utility module to deal with Proton and umu"""

import json
import os
from typing import Dict, Generator, List

from lutris import settings
from lutris.exceptions import MissingExecutableError
from lutris.util import system
from lutris.util.steam.config import get_steamapps_dirs

DEFAULT_GAMEID = "umu-default"


def is_proton_version(version: str) -> bool:
    """True if the version indicated specifies a Proton version of Wine; these
    require special handling."""
    return "proton" in version.lower() and "lutris" not in version and version in list_proton_versions()


def is_umu_path(path: str) -> bool:
    """True if the path given actually runs Umu; this will run Proton-Wine in turn,
    but can be directed to particular Proton implementation by setting the env-var
    PROTONPATH, but if this is omitted it will default to the latest Proton it
    downloads."""
    return bool(path and (path.endswith("/umu_run.py") or path.endswith("/umu-run")))


def is_proton_path(wine_path: str) -> bool:
    """True if the path given actually runs Umu; this will run Proton-Wine in turn,
    but can be directed to particular Proton implementation by setting the env-var
    PROTONPATH, but if this is omitted it will default to the latest Proton it
    downloads."""
    for proton_path in _iter_proton_locations():
        for p in os.listdir(proton_path):
            if "proton" in p.lower():
                if p in wine_path:
                    return True
    return False


def get_umu_path() -> str:
    """Returns the path to the Umu launch script, which can be run to execute
    a Proton version. It can supply a default Proton, but if the env-var PROTONPATH
    is set this will direct it to a specific Proton installation.

    The path that this returns will be considered an Umu path by is_umu_path().

    If this script can't be found this will raise MissingExecutableError."""

    # 'umu-run' is normally the entry point, and is a zipapp full of Python code. But
    # We used to ship a directory of loose files, and the entry point then is 'umu_run.py'
    entry_points = ["umu-run", "umu_run.py"]

    custom_path = settings.read_setting("umu_path")
    if custom_path:
        for entry_point in entry_points:
            entry_path = os.path.join(custom_path, entry_point)
            if system.path_exists(entry_path):
                return entry_path

    # We only use 'umu-run' when searching the path since that's the command
    # line entry point.
    if system.can_find_executable("umu-run"):
        return system.find_required_executable("umu-run")
    path_candidates = (
        "/app/share",  # prioritize flatpak due to non-rolling release distros
        "/usr/local/share",
        "/usr/share",
        "/opt",
        settings.RUNTIME_DIR,
    )
    for path_candidate in path_candidates:
        for entry_point in entry_points:
            entry_path = os.path.join(path_candidate, "umu", entry_point)
            if system.path_exists(entry_path):
                return entry_path
    raise MissingExecutableError("Install umu to use Proton")


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


def get_proton_wine_path(version: str) -> str:
    """Get the wine path for the specified proton version"""
    for proton_path in _iter_proton_locations():
        for dir_name in os.listdir(proton_path):
            if "proton" in dir_name.lower() and version.lower() in dir_name.lower():
                wine_path_dist = os.path.join(proton_path, dir_name, "dist/bin/wine")
                wine_path_files = os.path.join(proton_path, dir_name, "files/bin/wine")
                if os.path.exists(wine_path_dist):
                    return wine_path_dist
                if os.path.exists(wine_path_files):
                    return wine_path_files
    raise MissingExecutableError("Selected Proton version is missing wine executable. Unable to use.")


def get_proton_path_by_path(wine_path: str) -> str:
    # Split the path to get the directory containing the file
    directory_path = os.path.dirname(wine_path)

    # Navigate up two levels to reach the version directory
    version_directory = os.path.dirname(os.path.dirname(directory_path))

    return version_directory


def get_proton_paths() -> List[str]:
    """Get the Folder that contains all the Proton versions. Can probably be improved"""
    paths = set()
    for proton_path in _iter_proton_locations():
        for version in [p for p in os.listdir(proton_path) if "proton" in p.lower()]:
            if system.path_exists(os.path.join(proton_path, version, "proton")):
                paths.add(proton_path)
    return list(paths)


def list_proton_versions() -> List[str]:
    """Return the list of Proton versions installed in Steam"""
    try:
        # We can only use a Proton install via the Umu launcher script.
        _ = get_umu_path()
    except MissingExecutableError:
        return []

    versions = []
    for proton_path in get_proton_paths():
        for version in [p for p in os.listdir(proton_path) if "proton" in p.lower()]:
            path = os.path.join(proton_path, version, "proton")
            if os.path.isfile(path):
                versions.append(version)
    return versions


def update_proton_env(wine_path: str, env: Dict[str, str], game_id: str = DEFAULT_GAMEID, umu_log: str = None) -> None:
    """Add various env-vars to an 'env' dict for use by Proton and Umu; this won't replace env-vars, so they can still
    be pre-set before we get here. This sets the PROTONPATH so the Umu launcher will know what Proton to use,
    and the WINEARCH to win64, which is what we expect Proton to always be. GAMEID is required, but we'll use a default
    GAMEID if you don't pass one in.

    This also propagates LC_ALL to HOST_LC_ALL, if LC_ALL is set."""

    if "PROTONPATH" not in env:
        env["PROTONPATH"] = get_proton_path_by_path(wine_path)

    if "GAMEID" not in env:
        env["GAMEID"] = game_id

    if "UMU_LOG" not in env and umu_log:
        env["UMU_LOG"] = umu_log

    if "WINEARCH" not in env:
        env["WINEARCH"] = "win64"

    if "PROTON_VERB" not in env:
        env["PROTON_VERB"] = "waitforexitandrun"

    locale = env.get("LC_ALL")
    host_locale = env.get("HOST_LC_ALL")
    if locale and not host_locale:
        env["HOST_LC_ALL"] = locale


def get_game_id(game, env) -> str:
    if not game:
        return DEFAULT_GAMEID

    game_id = env.get("UMU_ID")
    if game_id:
        return game_id

    games_path = os.path.join(settings.RUNTIME_DIR, "umu-games/umu-games.json")

    if not os.path.exists(games_path):
        return DEFAULT_GAMEID

    with open(games_path, "r", encoding="utf-8") as games_file:
        umu_games = json.load(games_file)

    for umu_game in umu_games:
        if (
            umu_game["store"]
            and (
                umu_game["store"] == game.service or (umu_game["store"] == "humble" and game.service == "humblebundle")
            )
            and umu_game["appid"] == game.appid
        ):
            return umu_game["umu_id"]
    return DEFAULT_GAMEID
