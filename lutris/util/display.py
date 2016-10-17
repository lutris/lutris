import subprocess
from gi.repository import Gdk

from lutris.util.log import logger


def set_cursor(name, window, display=None):
    """Set a named mouse cursor for the given window."""

    if not display:
        display = Gdk.Display.get_default()
    if not window:
        logger.error('No window provided in set_cursor')
        return
    cursor = Gdk.Cursor.new_from_name(display, name)
    window.set_cursor(cursor)


def get_vidmodes():
    xrandr_output = subprocess.Popen(["xrandr"],
                                     stdout=subprocess.PIPE).communicate()[0]
    return list([line for line in xrandr_output.decode().split("\n")])


def get_outputs():
    """Return list of tuples containing output name and geometry."""
    outputs = []
    vid_modes = get_vidmodes()
    if not vid_modes:
        logger.error("xrandr didn't return anything")
        return []
    for line in vid_modes:
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[1] == 'connected':
            if len(parts) == 2:
                continue
            geom = parts[2] if parts[2] != 'primary' else parts[3]
            if geom.startswith('('):  # Screen turned off, no geometry
                continue
            outputs.append((parts[0], geom))
    return outputs


def get_output_names():
    return [output[0] for output in get_outputs()]


def turn_off_except(display):
    for output in get_outputs():
        if output[0] != display:
            subprocess.Popen(["xrandr", "--output", output[0], "--off"])


def get_resolutions():
    """Return the list of supported screen resolutions."""
    resolution_list = []
    for line in get_vidmodes():
        if line.startswith("  "):
            resolution_list.append(line.split()[0])
    return resolution_list


def get_current_resolution(monitor=0):
    """Return the current resolution for the desktop."""
    resolution = list()
    for line in get_vidmodes():
        if line.startswith("  ") and "*" in line:
            resolution.append(line.split()[0])
    if monitor == 'all':
        return resolution
    else:
        return resolution[monitor]


def change_resolution(resolution):
    """Change display resolution.

    Takes a string for single monitors or a list of displays as returned
    by get_outputs().
    """
    if not resolution:
        logger.warning("No resolution provided")
        return
    if isinstance(resolution, str):
        logger.debug("Switching resolution to %s", resolution)

        if resolution not in get_resolutions():
            logger.warning("Resolution %s doesn't exist." % resolution)
        else:
            subprocess.Popen(["xrandr", "-s", resolution])
    else:
        for display in resolution:
            display_name = display[0]
            logger.debug("Switching to %s on %s", display[1], display[0])
            display_geom = display[1].split('+')
            display_resolution = display_geom[0]
            position = (display_geom[1], display_geom[2])

            subprocess.Popen([
                "xrandr",
                "--output", display_name,
                "--mode", display_resolution,
                "--pos", "{}x{}".format(position[0], position[1])
            ]).communicate()


def restore_gamma():
    """Restores gamma to a normal level."""
    subprocess.Popen(["xgamma", "-gamma", "1.0"])
