import re
import subprocess
import time

import gi
gi.require_version('GnomeDesktop', '3.0')

from gi.repository import Gdk, GnomeDesktop, GLib

from lutris.util import system
from lutris.util.log import logger

XRANDR_CACHE = None
XRANDR_CACHE_SET_AT = None
XGAMMA_PATH = system.find_executable('xgamma')

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
    """Return video modes from XrandR"""
    logger.debug("Retrieving video modes from XrandR")
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
    """Return output names from XrandR"""
    return [output[0] for output in get_outputs()]


def turn_off_except(display):
    """Use XrandR to turn off displays except the one referenced by `display`"""
    if not display:
        logger.error("No active display given, no turning off every display")
        return
    for output in get_outputs():
        if output[0] != display:
            logger.info("Turning off %s", output[0])
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
            logger.info("Changing resolution to %s", resolution)
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
            logger.info("Switching resolution of %s to %s", display_name, display_resolution)
            subprocess.Popen([
                "xrandr",
                "--output", display_name,
                "--mode", display_resolution,
                "--pos", "{}x{}".format(position[0], position[1]),
                "--rotate", rotation
            ]).communicate()


def restore_gamma():
    """Restores gamma to a normal level."""
    if XGAMMA_PATH is not None:
        subprocess.Popen([XGAMMA_PATH, "-gamma", "1.0"])
    else:
        logger.warning('xgamma is not available on your system')


def get_xrandr_version():
    """Return the major and minor version of XRandR utility"""
    pattern = "version"
    xrandr_output = subprocess.Popen(["xrandr", "--version"],
                                     stdout=subprocess.PIPE).communicate()[0].decode()
    position = xrandr_output.find(pattern) + len(pattern)
    version_str = xrandr_output[position:].strip().split(".")
    logger.debug("Found XrandR version %s", version_str)
    try:
        return {"major": int(version_str[0]), "minor": int(version_str[1])}
    except ValueError:
        logger.error("Can't find version in: %s", xrandr_output)
        return {"major": 0, "minor": 0}


def get_graphics_adapaters():
    """Return the list of graphics cards available on a system

    Returns:
        list: list of tuples containing PCI ID and description of the VGA adapter
    """

    if not system.find_executable('lspci'):
        logger.warning('lspci is not available. List of graphics cards not available')
        return []
    return [
        (pci_id, vga_desc.split(': ')[1]) for pci_id, vga_desc in [
            line.split(maxsplit=1)
            for line in system.execute('lspci').split('\n')
            if 'VGA' in line
        ]
    ]


def get_providers():
    """Return the list of available graphic cards"""
    pattern = "name:"
    providers = []
    version = get_xrandr_version()

    if version["major"] == 1 and version["minor"] >= 4:
        logger.debug("Retrieving providers from XrandR")
        xrandr_output = subprocess.Popen(["xrandr", "--listproviders"],
                                         stdout=subprocess.PIPE).communicate()[0].decode()
        for line in xrandr_output.split("\n"):
            if line.find("Provider ") != 0:
                continue
            position = line.find(pattern) + len(pattern)
            providers.append(line[position:].strip())

    return providers


class LegacyDisplayManager:
    @staticmethod
    def get_resolutions():
        return get_resolutions()

    @staticmethod
    def get_display_names():
        return get_output_names()


class DisplayManager(object):
    def __init__(self):
        self.screen = Gdk.Screen.get_default()
        self.rr_screen = GnomeDesktop.RRScreen.new(self.screen)
        self.rr_config = GnomeDesktop.RRConfig.new_current(self.rr_screen)
        self.rr_config.load_current()

    @property
    def outputs(self):
        return self.rr_screen.list_outputs()

    def get_display_names(self):
        return [output_info.get_display_name() for output_info in self.rr_config.get_outputs()]

    def get_output_modes(self, output):
        logger.debug("Retrieving modes for %s", output)
        resolutions = []
        for mode in output.list_modes():
            resolution = "%sx%s" % (mode.get_width(), mode.get_height())
            if resolution not in resolutions:
                resolutions.append(resolution)
        return resolutions

    def get_resolutions(self):
        resolutions = []
        for mode in self.rr_screen.list_modes():
            resolutions.append("%sx%s" % (mode.get_width(), mode.get_height()))
        return sorted(set(resolutions), key=lambda x: int(x.split('x')[0]), reverse=True)


try:
    DISPLAY_MANAGER = DisplayManager()
except GLib.Error:
    DISPLAY_MANAGER = LegacyDisplayManager()

USE_DRI_PRIME = len(get_graphics_adapaters()) > 1


def get_resolution_choices():
    """Return list of available resolutions as label, value tuples
    suitable for inclusion in drop-downs.
    """
    resolutions = DISPLAY_MANAGER.get_resolutions()
    resolution_choices = list(zip(resolutions, resolutions))
    resolution_choices.insert(0, ("Keep current", 'off'))
    return resolution_choices


def get_output_choices():
    """Return list of outputs for drop-downs"""
    displays = DISPLAY_MANAGER.get_display_names()
    output_choices = list(zip(displays, displays))
    output_choices.insert(0, ("Off", 'off'))
    return output_choices


def get_output_list():
    """Return a list of output with their index.
    This is used to indicate to SDL 1.2 which monitor to use.
    """
    choices = [
        ('Off', 'off'),
    ]
    displays = DISPLAY_MANAGER.get_display_names()
    for index, output in enumerate(displays):
        # Display name can't be used because they might not be in the right order
        # Using DISPLAYS to get the number of connected monitors
        choices.append((output, str(index)))
    return choices
