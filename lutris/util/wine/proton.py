"""Utility module to deal with Proton and umu"""

import json
import os
from gettext import gettext as _
from typing import Dict, Generator, List, Optional

from lutris import settings
from lutris.exceptions import MissingExecutableError
from lutris.util import system
from lutris.util.steam.config import get_steamapps_dirs

GE_PROTON_LATEST = _("GE-Proton (Latest)")
DEFAULT_GAMEID = "umu-default"


def is_proton_version(version: str) -> bool:
    """True if the version indicated specifies a Proton version of Wine; these
    require special handling. GE_PROTON_LATEST is considered a Proton version, but
    is even more special- it refers to the Umu installation itself, and whichever
    Proton it downloads and installs."""
    return "Proton" in version and "lutris" not in version


def is_proton_path(wine_path: Optional[str]) -> bool:
    """True if the wine-path refers to a Proton Wine installation; these require
    special handling. The Umu path is considered a Proton-path too."""
    if not wine_path:
        return False

    if is_umu_path(wine_path):
        return True

    return "Proton" in wine_path and "lutris" not in wine_path


def is_umu_path(wine_path: Optional[str]) -> bool:
    """True if the path given actually runs Umu; this will run Proton-Wine in turn,
    but can be directed to particular Proton implementation by setting the env-var
    PROTONPATH, but if this is omitted it will default to the latest Proton it
    downloads."""
    if wine_path:
        return wine_path.endswith("/umu_run.py") or wine_path.endswith("/umu-run")
    return False


def get_umu_path() -> str:
    """Returns the path to the Umu launch script, which can be run to execute
    a Proton version. It can supply a default Proton, but if the env-var PROTONPATH
    is set this will direct it to a specific Proton installation.

    The path that this returns will be considered an Umu path by is_umu_path().

    If this script can't be found this will raise MissingExecutableError."""
    custom_path = settings.read_setting("umu_path")
    if custom_path:
        script_path = os.path.join(custom_path, "umu_run.py")
        if system.path_exists(script_path):
            return script_path
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
        script_path = os.path.join(path_candidate, "umu", "umu_run.py")
        if system.path_exists(script_path):
            return script_path
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
    try:
        # We can only use a Proton install via the Umu launcher script.
        _ = get_umu_path()
    except MissingExecutableError:
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


def get_proton_bin_for_version(version: str) -> str:
    if version == GE_PROTON_LATEST:
        return get_umu_path()

    for proton_path in get_proton_paths():
        path = os.path.join(proton_path, version, "dist/bin/wine")
        if os.path.isfile(path):
            return path
        path = os.path.join(proton_path, version, "files/bin/wine")
        if os.path.isfile(path):
            return path

    raise MissingExecutableError("The Proton bin for Wine version '%s' could not be found." % version)


def update_proton_env(wine_path: str, env: Dict[str, str], game_id: str = DEFAULT_GAMEID, umu_log: str = None) -> None:
    """Add various env-vars to an 'env' dict for use by Proton and Umu; this won't replace env-vars, so they can still
    be pre-set before we get here. This sets the PROTONPATH so the Umu launcher will know what Proton to use,
    and the WINEARCH to win64, which is what we expect Proton to always be. GAMEID is required, but we'll use a default
    GAMEID if you don't pass one in.

    This also propagates LC_ALL to HOST_LC_ALL, if LC_ALL is set."""
    if "PROTONPATH" not in env:
        protonpath = _get_proton_path_from_bin(wine_path)
        if protonpath:
            env["PROTONPATH"] = protonpath

    if "GAMEID" not in env:
        env["GAMEID"] = game_id

    if "UMU_LOG" not in env and umu_log:
        env["UMU_LOG"] = umu_log

    if "WINEARCH" not in env:
        env["WINEARCH"] = "win64"

    locale = env.get("LC_ALL")
    host_locale = env.get("HOST_LC_ALL")
    if locale and not host_locale:
        env["HOST_LC_ALL"] = locale


def _get_proton_path_from_bin(wine_path: str) -> Optional[str]:
    """Return a location suitable for PROTONPATH from the wine executable; if
    None, we leave PROTONPATH unset."""
    if is_umu_path(wine_path):
        return "GE-Proton"  # Download the latest Glorious Proton build

    # In stable versions of proton this can be dist/bin instead of files/bin
    if "/files/bin/" in wine_path:
        return wine_path[: wine_path.index("/files/bin/")]
    else:
        try:
            return wine_path[: wine_path.index("/dist/bin/")]
        except ValueError:
            pass

    return os.path.abspath(os.path.join(os.path.dirname(wine_path), "../../"))


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
