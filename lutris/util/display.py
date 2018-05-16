import re
import time
import subprocess

from lutris.util.system import find_executable
from lutris.util.log import logger

XRANDR_CACHE = None
XRANDR_CACHE_SET_AT = None
XGAMMA_FOUND = False


def cached(function):
    def wrapper():
        global XRANDR_CACHE
        global XRANDR_CACHE_SET_AT

        if XRANDR_CACHE and time.time() - XRANDR_CACHE_SET_AT < 60:
            return XRANDR_CACHE
        XRANDR_CACHE = function()
        XRANDR_CACHE_SET_AT = time.time()
        return XRANDR_CACHE
    return wrapper


@cached
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
            if parts[2] != 'primary':
                geom = parts[2]
                rotate = parts[3]
            else:
                geom = parts[3]
                rotate = parts[4]
            if geom.startswith('('):  # Screen turned off, no geometry
                continue
            if rotate.startswith('('):  # Screen not rotated, no need to include
                outputs.append((parts[0], geom, "normal"))
            else:
                if rotate in ("left", "right"):
                    geom_parts = geom.split('+')
                    x_y = geom_parts[0].split('x')
                    geom = "{}x{}+{}+{}".format(x_y[1], x_y[0], geom_parts[1], geom_parts[2])
                outputs.append((parts[0], geom, rotate))
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
            resolution_match = re.match('.*?(\d+x\d+).*', line)
            if resolution_match:
                resolution_list.append(resolution_match.groups()[0])
    return resolution_list


def get_unique_resolutions():
    """Return available resolutions, without duplicates and ordered with highest resolution first"""
    return sorted(set(get_resolutions()), key=lambda x: int(x.split('x')[0]), reverse=True)


def get_current_resolution(monitor=0):
    """Return the current resolution for the desktop."""
    resolution = list()
    for line in get_vidmodes():
        if line.startswith("  ") and "*" in line:
            resolution_match = re.match('.*?(\d+x\d+).*', line)
            if resolution_match:
                resolution.append(resolution_match.groups()[0])
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

            if (
                len(display) > 2 and
                display[2] in ('normal', 'left', 'right', 'inverted')
            ):
                rotation = display[2]
            else:
                rotation = "normal"

            subprocess.Popen([
                "xrandr",
                "--output", display_name,
                "--mode", display_resolution,
                "--pos", "{}x{}".format(position[0], position[1]),
                "--rotate", rotation
            ]).communicate()


def restore_gamma():
    """Restores gamma to a normal level."""
    global XGAMMA_FOUND
    if XGAMMA_FOUND is None:
        XGAMMA_FOUND = find_executable('xgamma')
    if XGAMMA_FOUND is True:
        subprocess.Popen(["xgamma", "-gamma", "1.0"])
    else:
        logger.warning('xgamma is not available on your system')


def get_xrandr_version():
    """Return the major and minor version of XRandR utility"""
    pattern = "version"
    xrandr_output = subprocess.Popen(["xrandr", "--version"],
                                     stdout=subprocess.PIPE).communicate()[0].decode()
    position = xrandr_output.find(pattern) + len(pattern)
    version_str = xrandr_output[position:].strip().split(".")
    try:
        return {"major": int(version_str[0]), "minor": int(version_str[1])}
    except ValueError:
        logger.error("Can't find version in: %s", xrandr_output)
        return {"major": 0, "minor": 0}


def get_providers():
    """Return the list of available graphic cards"""
    pattern = "name:"
    providers = list()
    version = get_xrandr_version()

    if version["major"] == 1 and version["minor"] >= 4:
        xrandr_output = subprocess.Popen(["xrandr", "--listproviders"],
                                         stdout=subprocess.PIPE).communicate()[0].decode()
        for line in xrandr_output.split("\n"):
            if line.find("Provider ") != 0:
                continue
            position = line.find(pattern) + len(pattern)
            providers.append(line[position:].strip())

    return providers
