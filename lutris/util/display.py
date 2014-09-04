import os
import subprocess

from lutris.util.log import logger


def get_vidmodes():
    xrandr_output = subprocess.Popen("xrandr",
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE).communicate()[0]
    return list([line for line in xrandr_output.split("\n")])


def get_outputs():
    """ Return list of tuples containing output name and geometry """
    outputs = list()
    for line in get_vidmodes():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[1] == 'connected':
            geom = parts[2] if parts[2] != 'primary' else parts[3]
            outputs.append((parts[0], geom))
    return outputs


def get_output_names():
    return [output[0] for output in get_outputs()]


def turn_off_except(display):
    for output in get_outputs():
        if output[0] != display:
            subprocess.Popen("xrandr --output %s --off" % output[0], shell=True)


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
    """ Change display resolution.
        Takes a string for single monitors or a list of displays as returned
        by get_outputs()
    """
    if isinstance(resolution, basestring):
        logger.debug("Switching resolution to %s", resolution)

        if resolution not in get_resolutions():
            logger.warning("Resolution %s doesn't exist." % resolution)
        else:
            subprocess.Popen("xrandr -s %s" % resolution, shell=True)
    else:
        print resolution
        for display in resolution:
            display_name = display[0]
            display_geom = display[1]
            logger.debug("Switching to %s on %s", display[1], display[0])
            display_resolution = display_geom.split('+')[0]

            cmd = "xrandr --output %s --mode %s" % (display_name,
                                                    display_resolution)

            subprocess.Popen(cmd, shell=True).communicate()
            cmd = "xrandr --output %s --panning %s" % (display_name,
                                                       display_geom)
            logger.debug(cmd)
            subprocess.Popen(cmd, shell=True)


def reset_desktop():
    """Restore the desktop to its original state."""
    # Restore resolution
    resolution = get_resolutions()[0]
    change_resolution(resolution)
    # Restore gamma
    os.popen("xgamma -gamma 1.0")
