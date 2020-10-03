from lutris.util import system


def get_game_launcher(script):
    """Return the key and value of the launcher
    exe64 can be provided to specify an executable for 64bit systems
    This should be deprecated when support for multiple binaries has been
    added.
    """
    launcher_value = None
    exe = "exe64" if "exe64" in script and system.LINUX_SYSTEM.is_64_bit else "exe"
    for launcher in (exe, "iso", "rom", "disk", "main_file"):
        if launcher not in script:
            continue
        launcher_value = script[launcher]
        if launcher == "exe64":
            launcher = "exe"  # If exe64 is used, rename it to exe
        break
    if not launcher_value:
        launcher = None
    return launcher, launcher_value
