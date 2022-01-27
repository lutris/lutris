
import os

from lutris.util.log import logger
from lutris.util.ubisoft.consts import UBISOFT_REGISTRY_LAUNCHER_INSTALLS
from lutris.util.wine.registry import WineRegistry

NOT_INSTALLED = "NOT_INSTALLED"
INSTALLED = "INSTALLED"


def _get_registry_value_from_path(registry_path, key):
    registry = WineRegistry()
    return registry.query(registry_path, key)


def _return_local_game_path_from_special_registry(special_registry_path):
    if not special_registry_path:
        return NOT_INSTALLED
    return _get_registry_value_from_path("HKEY_LOCAL_MACHINE" + special_registry_path, "InstallLocation")


def _return_local_game_path(launch_id):
    installs_path = UBISOFT_REGISTRY_LAUNCHER_INSTALLS
    registry = WineRegistry()
    game_path = registry.query("HKEY_LOCAL_MACHINE" + installs_path + f'\\{launch_id}', 'InstallDir')
    return os.path.normcase(os.path.normpath(game_path))


def get_local_game_path(special_registry_path, launch_id):
    local_game_path = _return_local_game_path(launch_id)
    if not local_game_path and special_registry_path:
        local_game_path = _return_local_game_path_from_special_registry(special_registry_path)
    return local_game_path


async def get_size_at_path(start_path):
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def _is_file_at_path(path, file):
    if os.path.isdir(path):
        return os.path.isfile(os.path.join(path, file))
    return False


def _read_status_from_state_file(game_path):
    try:
        if os.path.exists(os.path.join(game_path, 'uplay_install.state')):
            with open(os.path.join(game_path, 'uplay_install.state'), 'rb') as f:
                if f.read()[0] == 0x0A:
                    return INSTALLED
                return NOT_INSTALLED
        return NOT_INSTALLED
    except Exception as e:
        logger.warning("Issue reading install state file for %s: %s", game_path, repr(e))
        return NOT_INSTALLED


def get_game_installed_status(path, exe=None, special_registry_path=None):
    status = NOT_INSTALLED
    try:
        if path and os.access(path, os.F_OK):
            status = _read_status_from_state_file(path)
            # Fallback for old games
            if status == NOT_INSTALLED and exe and special_registry_path:
                if _is_file_at_path(path, exe):
                    status = INSTALLED
    except Exception as e:
        logger.error("Error reading game installed status at %s, %s", path, repr(e))
    return status


def get_ubisoft_registry(prefix, fullpath):
    """Get a value from the registry in a Ubisoft Connect prefix"""
    if not fullpath:
        return ""
    if fullpath.startswith("HKEY"):
        path, key = fullpath.rsplit('\\', maxsplit=1)
        path = convert_ubisoft_key(path)
        return prefix.get_registry_key(path, key)
    return fullpath


def convert_ubisoft_key(key_path):
    """Convert Ubisoft registry keys for Wine compatibility"""
    if 'LOCAL_MACHINE' in key_path:
        key_path = key_path.replace("SOFTWARE\\", "Software\\Wow6432Node\\")
    key_path = key_path.replace("\\UBISOFT", "\\Ubisoft")
    key_path = key_path.replace("\\", "/")
    return key_path
