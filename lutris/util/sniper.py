"""Valve Sniper runtime (Steam Linux Runtime 3.0) discovery utilities."""

import os
from functools import lru_cache
from typing import List, Optional

from lutris.util.log import logger

_SNIPER_SEARCH_PATHS = [
    os.path.expanduser("~/.local/share/umu/run-in-sniper"),
    os.path.expanduser("~/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/run-in-sniper"),
]

# Host library base directories. Inside the Sniper container, the host
# filesystem is mounted at /run/host/.
_HOST_LIB_DIRS = ["/usr/lib64", "/usr/lib", "/lib64", "/lib"]

# Sniper runtime library directories inside the container. These must come
# BEFORE host fallback paths in LD_LIBRARY_PATH so that libraries present
# in Sniper (e.g. gdk-pixbuf with its module loaders) are preferred over
# the host's versions, which would have wrong module paths inside the container.
_SNIPER_RUNTIME_LIB_DIRS = [
    "/usr/lib/x86_64-linux-gnu",
    "/lib/x86_64-linux-gnu",
    "/usr/lib/i386-linux-gnu",
    "/lib/i386-linux-gnu",
]


def get_sniper_run_command() -> Optional[str]:
    """Return the path to the run-in-sniper script, or None if not found.

    Searches in order:
      1. umu-launcher installation (~/.local/share/umu/)
      2. Steam installation (~/.local/share/Steam/)
    """
    for path in _SNIPER_SEARCH_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            logger.debug("Found Sniper runtime at %s", path)
            return path

    logger.debug("Sniper runtime not found")
    return None


@lru_cache(maxsize=1)
def get_sniper_host_lib_paths() -> List[str]:
    """Discover host library directories and return them as /run/host/ paths
    for use inside the Sniper container.

    Scans base library dirs and their immediate subdirectories for directories
    that contain shared libraries (.so files). This catches private library
    directories like /usr/lib64/pulseaudio/ that use RUNPATH and would otherwise
    resolve to the Sniper runtime's version instead of the host's.
    """
    seen = set()
    paths = []

    for host_dir in _HOST_LIB_DIRS:
        real_dir = os.path.realpath(host_dir)
        if real_dir in seen or not os.path.isdir(real_dir):
            continue
        seen.add(real_dir)

        container_dir = "/run/host" + host_dir
        paths.append(container_dir)

        try:
            entries = os.listdir(real_dir)
        except OSError:
            continue

        for entry in entries:
            subdir = os.path.join(real_dir, entry)
            if not os.path.isdir(subdir):
                continue
            try:
                if any(f.endswith(".so") or ".so." in f for f in os.listdir(subdir)):
                    paths.append("/run/host" + os.path.join(host_dir, entry))
            except OSError:
                continue

    return paths


def get_sniper_ld_library_path() -> str:
    """Build the LD_LIBRARY_PATH for use inside the Sniper container.

    The order ensures:
      1. Sniper runtime libs (preferred — modules like gdk-pixbuf loaders work correctly)
      2. Host libs via /run/host/ (fallback — for libraries missing from Sniper like libgtkmm)
    """
    return os.pathsep.join(_SNIPER_RUNTIME_LIB_DIRS + get_sniper_host_lib_paths())
