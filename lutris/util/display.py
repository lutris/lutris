"""Module to deal with various aspects of displays"""
import os
import re
import time
import subprocess

from lutris.util import system
from lutris.util.log import logger

XRANDR_CACHE = None
XRANDR_CACHE_SET_AT = None
XGAMMA_FOUND = None


def cached(func):
    """Something that does not belong here"""
    def wrapper():
        """What does it feel being WRONG"""
        global XRANDR_CACHE  # Fucked up shit
        global XRANDR_CACHE_SET_AT  # Moar fucked up globals

        if XRANDR_CACHE and time.time() - XRANDR_CACHE_SET_AT < 60:
            return XRANDR_CACHE
        XRANDR_CACHE = func()
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
    display = None
    position = None
    rotate = None
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
                rotate = "normal"
            geo_split = geom.split('+')
            position = geo_split[1] + "x" + geo_split[2]
            display = parts[0]
        elif '*' in line:
            mode = parts[0]
            for number in parts:
                if '*' in number:
                    refresh_rate = number[:5]
                    outputs.append((display, mode, position, rotate, refresh_rate))
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
            resolution_match = re.match(r'.*?(\d+x\d+).*', line)
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
            resolution_match = re.match(r'.*?(\d+x\d+).*', line)
            if resolution_match:
                resolution.append(resolution_match.groups()[0])
    if monitor == 'all':
        return resolution
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
            logger.warning("Resolution %s doesn't exist.", resolution)
        else:
            subprocess.Popen(["xrandr", "-s", resolution])
    else:
        for display in resolution:
            display_name = display[0]
            display_mode = display[1]
            logger.debug("Switching to %s on %s", display_mode, display_name)
            position = display[2]
            refresh_rate = display[4]

            if len(display) > 2 and display[3] in ('normal', 'left', 'right', 'inverted'):
                rotation = display[3]
            else:
                rotation = "normal"

            subprocess.Popen([
                "xrandr",
                "--output", display_name,
                "--mode", display_mode,
                "--pos", position,
                "--rotate", rotation,
                "--rate", refresh_rate
            ]).communicate()


def restore_gamma():
    """Restores gamma to a normal level."""
    global XGAMMA_FOUND
    if XGAMMA_FOUND is None:
        XGAMMA_FOUND = bool(system.find_executable('xgamma'))
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
    providers = []
    lspci_cmd = system.find_executable('lspci')
    if not lspci_cmd:
        logger.warning("lspci is not installed, unable to list graphics providers")
        return providers
    providers_cmd = subprocess.Popen([lspci_cmd], stdout=subprocess.PIPE).communicate()[0].decode()
    for provider in providers_cmd.strip().split("\n"):
        if "VGA" in provider:
            providers.append(provider)
    return providers


def get_compositor_commands():
    """Nominated for the worst function in lutris"""
    start_compositor = None
    stop_compositor = None
    desktop_session = os.environ.get('DESKTOP_SESSION')
    if desktop_session == "plasma":
        stop_compositor = "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.suspend"
        start_compositor = "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.resume"
    elif desktop_session == "mate" and system.execute("gsettings get org.mate.Marco.general compositing-manager", shell=True) == 'true':
        stop_compositor = "gsettings set org.mate.Marco.general compositing-manager false"
        start_compositor = "gsettings set org.mate.Marco.general compositing-manager true"
    elif desktop_session == "xfce" and system.execute("xfconf-query --channel=xfwm4 --property=/general/use_compositing", shell=True) == 'true':
        stop_compositor = "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=false"
        start_compositor = "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=true"
    return start_compositor, stop_compositor
