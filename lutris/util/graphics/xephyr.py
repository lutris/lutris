"""Xephyr utilities"""


def get_xephyr_command(display, config):
    """Return a configured Xephyr command"""
    xephyr_depth = "8" if config.get("xephyr") == "8bpp" else "16"
    xephyr_resolution = config.get("xephyr_resolution") or "640x480"
    xephyr_command = [
        "Xephyr",
        display,
        "-ac",
        "-screen",
        xephyr_resolution + "x" + xephyr_depth,
        "-glamor",
        "-reset",
        "-terminate",
    ]
    if config.get("xephyr_fullscreen"):
        xephyr_command.append("-fullscreen")
    return xephyr_command
