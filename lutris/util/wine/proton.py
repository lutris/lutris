"""Utility module to deal with Proton and ULWGL"""
import os
from typing import Generator, List

from lutris.util import system
from lutris.util.steam.config import get_steamapps_dirs


def is_proton_path(wine_path):
    return "Proton" in wine_path and "lutris" not in wine_path


def get_ulwgl_path():
    return system.find_executable("ulwgl-run")


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
    for path in _iter_proton_locations():
        proton_versions = [p for p in os.listdir(path) if "Proton" in p]
        for version in proton_versions:
            if system.path_exists(os.path.join(path, version, "dist/bin/wine")):
                paths.add(path)
            if system.path_exists(os.path.join(path, version, "files/bin/wine")):
                paths.add(path)
    return list(paths)


def list_proton_versions() -> List[str]:
    """Return the list of Proton versions installed in Steam"""
    versions = []
    for proton_path in get_proton_paths():
        proton_versions = [p for p in os.listdir(proton_path) if "Proton" in p]
        for version in proton_versions:
            path = os.path.join(proton_path, version, "dist/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
            # Support Proton Experimental
            path = os.path.join(proton_path, version, "files/bin/wine")
            if os.path.isfile(path):
                versions.append(version)
    return versions
