"""Install script interpreter package."""

import enum

AUTO_EXE_PREFIX = "_xXx_AUTO_"
AUTO_ELF_EXE = AUTO_EXE_PREFIX + "ELF_xXx_"
AUTO_WIN32_EXE = AUTO_EXE_PREFIX + "WIN32_xXx_"

# Keys in the game config that identify the game's main entry point,
# checked in order of priority.
ENTRY_POINT_KEYS = ("exe", "main_file", "iso", "rom", "disk-a", "path")


def get_entry_point_path(game_config: dict) -> str:
    """Return the path of the main entry point from a game config dict.

    Checks each entry point key in priority order and returns the first
    non-empty string value found. Also checks the 'files' key, extracting the
    first element if it's a list. Returns an empty string if no entry point
    is found.
    """
    for key in ENTRY_POINT_KEYS:
        if key in game_config:
            path = game_config[key]
            if isinstance(path, str) and path:
                return path

    files = game_config.get("files")
    if isinstance(files, list) and files:
        path = files[0]
        if isinstance(path, str) and path:
            return path

    return ""


class InstallationKind(enum.Enum):
    INSTALL = 0
    UPDATE = 1
    DLC = 2
