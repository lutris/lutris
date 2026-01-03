"""Utility module to deal with Proton and umu"""

import json
import os
from gettext import gettext as _
from typing import Dict, Generator, List, Optional

from lutris import settings
from lutris.exceptions import MissingExecutableError
from lutris.monitored_command import RUNNING_COMMANDS
from lutris.util import cache_single, system
from lutris.util.steam.config import get_steamapps_dirs
from lutris.util.strings import get_natural_sort_key

DEFAULT_GAMEID = "umu-default"


def is_proton_version(version: Optional[str]) -> bool:
    """True if the version indicated specifies a Proton version of Wine; these
    require special handling."""
    return version in get_proton_versions()


def is_umu_path(path: Optional[str]) -> bool:
    """True if the path given actually runs Umu; this will run Proton-Wine in turn,
    but can be directed to particular Proton implementation by setting the env-var
    PROTONPATH, but if this is omitted it will default to the latest Proton it
    downloads."""
    return bool(path and (path.endswith("/umu_run.py") or path.endswith("/umu-run")))


def is_proton_path(wine_path: Optional[str]) -> bool:
    """True if the path given actually runs Umu; this will run Proton-Wine in turn,
    but can be directed to particular Proton implementation by setting the env-var
    PROTONPATH, but if this is omitted it will default to the latest Proton it
    downloads.

    This function may be given the wine root directory or a file within such as
    the wine executable and will return true for either."""
    if not wine_path:
        return True
    for candidate_wine_path in get_proton_versions().values():
        if system.path_contains(candidate_wine_path, wine_path):
            return True
    return False


@cache_single
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


def get_proton_wine_path(version: str) -> str:
    """Get the wine path for the specified proton version"""
    wine_path = get_proton_versions().get(version)
    if wine_path:
        wine_path_dist = os.path.join(wine_path, "dist/bin/wine")
        if os.path.exists(wine_path_dist):
            return wine_path_dist

        wine_path_files = os.path.join(wine_path, "files/bin/wine")
        if os.path.exists(wine_path_files):
            return wine_path_files

    raise MissingExecutableError(_("Proton version '%s' is missing its wine executable and can't be used.") % version)


def get_proton_path_by_path(wine_path: str) -> str:
    # Split the path to get the directory containing the file
    directory_path = os.path.dirname(wine_path)

    # Navigate up two levels to reach the version directory
    version_directory = os.path.dirname(os.path.dirname(directory_path))

    return version_directory


def list_proton_versions() -> List[str]:
    """Return the list of Proton versions installed in Steam, in sorted order."""
    return sorted(get_proton_versions().keys(), key=get_natural_sort_key, reverse=True)


@cache_single
def get_proton_versions() -> Dict[str, str]:
    """Return the dict of Proton versions installed in Steam, which is cached.
    The keys are the versions, and the values are the paths to those versions,
    which are their wine-paths."""
    try:
        # We can only use a Proton install via the Umu launcher script.
        _ = get_umu_path()
    except MissingExecutableError:
        return {}

    versions = dict()
    for proton_path in _iter_proton_locations():
        if os.path.isdir(proton_path):
            for version in os.listdir(proton_path):
                if version not in versions:
                    wine_path = os.path.join(proton_path, version)
                    if os.path.isfile(os.path.join(wine_path, "proton")):
                        versions[version] = wine_path
    return versions


def _iter_proton_locations() -> Generator[str, None, None]:
    """Iterate through all potential Proton locations"""
    yield settings.WINE_DIR

    try:
        steamapp_dirs = get_steamapps_dirs()
    except:
        return  # in case of corrupt or unreadable Steam configuration files!

    for path in [os.path.join(p, "common") for p in steamapp_dirs]:
        yield path

    for path in [os.path.join(p, "") for p in steamapp_dirs]:
        yield path


def update_proton_env(wine_path: str, env: Dict[str, str], game_id: str = DEFAULT_GAMEID, umu_log: str = "") -> None:
    """Add various env-vars to an 'env' dict for use by Proton and Umu; this won't replace env-vars, so they can still
    be pre-set before we get here. This sets the PROTONPATH so the Umu launcher will know what Proton to use,
    and the WINEARCH to win64, which is what we expect Proton to always be. GAMEID is required, but we'll use a default
    GAMEID if you don't pass one in.

    This also propagates LC_ALL to HOST_LC_ALL, if LC_ALL is set."""

    if "PROTONPATH" not in env and not is_umu_path(wine_path):
        env["PROTONPATH"] = get_proton_path_by_path(wine_path)

    if "GAMEID" not in env:
        env["GAMEID"] = game_id

    if "UMU_LOG" not in env and umu_log:
        env["UMU_LOG"] = umu_log

    if "WINEARCH" not in env:
        env["WINEARCH"] = "win64"

    if "PROTON_VERB" not in env:
        # Proton fixes are only applied with waitforexitandrun, so we want to use that
        # but only if we're the first process start - the next concurrent process should
        # use run so it does not wait.
        prefix = env.get("WINEPREFIX")
        if prefix and prefix in (c.env.get("WINEPREFIX") for c in RUNNING_COMMANDS):
            env["PROTON_VERB"] = "runinprefix"  # do *not* re-initialize a running prefix!
        else:
            env["PROTON_VERB"] = "waitforexitandrun"  # does full initialization with proton-fixes

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
