import os
import subprocess

from lutris.util.log import logger


def iter_xrandr_output():
    xrandr_output = subprocess.Popen("xrandr",
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE).communicate()[0]
    for line in xrandr_output.split("\n"):
        yield line


def get_outputs():
    outputs = list()
    for line in iter_xrandr_output():
        parts = line.split()
        if parts[1] == 'connected':
            outputs.append(parts[0])
    return outputs


def get_resolutions():
    """Return the list of supported screen resolutions."""
    resolution_list = []
    for line in iter_xrandr_output():
        if line.startswith("  "):
            resolution_list.append(line.split()[0])
    return resolution_list


def get_current_resolution(monitor=0):
    """Return the current resolution for the desktop."""
    resolution = list()
    for line in iter_xrandr_output():
        if line.startswith("  ") and "*" in line:
            resolution.append(line.split()[0])
    if monitor == 'all':
        return resolution
    else:
        return resolution[monitor]


def change_resolution(resolution):
    """change desktop resolution"""
    logger.debug("Switching resolution to %s", resolution)
    if resolution not in get_resolutions():
        logger.warning("Resolution %s doesn't exist.")
    else:
        subprocess.Popen("xrandr -s %s" % resolution, shell=True)


def reset_desktop():
    """Restore the desktop to its original state."""
    #Restore resolution
    resolution = get_resolutions()[0]
    change_resolution(resolution)
    #Restore gamma
    os.popen("xgamma -gamma 1.0")
