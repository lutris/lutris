from lutris.util import linux
from lutris.util.log import logger


def get_game_launcher(script):
    """Return the key and value of the launcher
    exe64 can be provided to specify an executable for 64bit systems
    This should be deprecated when support for multiple binaries has been
    added.
    """
    key = None
    launcher_value = None
    exe = "exe64" if "exe64" in script and linux.LINUX_SYSTEM.is_64_bit else "exe"
    if exe == "exe64":
        logger.warning("Stop using exe64, use launch configs to add support for 32 bit. Please update the script.")
    for launcher in (exe, "iso", "rom", "disk", "main_file"):
        if launcher not in script:
            continue
        launcher_value = script[launcher]
        if launcher == "exe64":
            key = "exe"  # If exe64 is used, rename it to exe
        break
    if not launcher_value and "game" in script:
        return get_game_launcher(script["game"])
    return key, launcher_value
