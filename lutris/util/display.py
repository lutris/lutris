"""Module to deal with various aspects of displays"""
import os
import re
import subprocess
from collections import namedtuple

from gi.repository import Gdk, GnomeDesktop, GLib

from lutris.util import system
from lutris.util.log import logger


def _get_vidmodes():
    """Return video modes from XrandR"""
    logger.debug("Retrieving video modes from XrandR")
    xrandr_output = subprocess.check_output(["xrandr"])
    return xrandr_output.decode().split("\n")


Output = namedtuple(
    "Output", ("name", "mode", "position", "rotation", "primary", "rate")
)


class NoScreenDetected(Exception):
    """Raise this when unable to detect screens"""


def get_outputs():
    """Return list of namedtuples containing output 'name', 'geometry',
    'rotation' and whether it is the 'primary' display."""
    outputs = []
    vid_modes = _get_vidmodes()
    position = None
    rotate = None
    primary = None
    name = None
    if not vid_modes:
        logger.error("xrandr didn't return anything")
        return []
    for line in vid_modes:
        if "connected" in line:
            primary = "primary" in line
            try:
                if primary:
                    name, _, _, geometry, rotate, *_ = line.split()
                else:
                    name, _, geometry, rotate, *_ = line.split()
            except ValueError as ex:
                logger.error("Unhandled xrandr line %s, error: %s. "
                             "Please send your xrandr output to the dev team",
                             line, ex)
                continue
            if geometry.startswith("("):  # Screen turned off, no geometry
                continue
            if rotate.startswith("("):  # Screen not rotated, no need to include
                rotate = "normal"
            _, x_pos, y_pos = geometry.split("+")
            position = "{x_pos}x{y_pos}".format(x_pos=x_pos, y_pos=y_pos)
        elif "*" in line:
            mode, *framerates = line.split()
            for number in framerates:
                if "*" in number:
                    hertz = number[:-2]
                    outputs.append(
                        Output(
                            name=name,
                            mode=mode,
                            position=position,
                            rotation=rotate,
                            primary=primary,
                            rate=hertz,
                        )
                    )
                    break
    return outputs


def turn_off_except(display):
    """Use XrandR to turn off displays except the one referenced by `display`"""
    if not display:
        logger.error("No active display given, no turning off every display")
        return
    for output in get_outputs():
        if output.name != display:
            logger.info("Turning off %s", output[0])
            subprocess.Popen(["xrandr", "--output", output.name, "--off"])


def get_resolutions():
    """Return the list of supported screen resolutions."""
    resolution_list = []
    for line in _get_vidmodes():
        if line.startswith("  "):
            resolution_match = re.match(r".*?(\d+x\d+).*", line)
            if resolution_match:
                resolution_list.append(resolution_match.groups()[0])
    return resolution_list


def get_unique_resolutions():
    """Return available resolutions, without duplicates and ordered with highest resolution first"""
    return sorted(
        set(get_resolutions()), key=lambda x: int(x.split("x")[0]), reverse=True
    )


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
            logger.debug("Switching to %s on %s", display.mode, display.name)

            if display.rotation is not None and display.rotation in (
                    "normal",
                    "left",
                    "right",
                    "inverted",
            ):
                rotation = display.rotation
            else:
                rotation = "normal"
            logger.info("Switching resolution of %s to %s", display.name, display.mode)
            subprocess.Popen(
                [
                    "xrandr",
                    "--output",
                    display.name,
                    "--mode",
                    display.mode,
                    "--pos",
                    display.position,
                    "--rotate",
                    rotation,
                    "--rate",
                    display.rate,
                ]
            ).communicate()


def restore_gamma():
    """Restores gamma to a normal level."""
    xgamma_path = system.find_executable("xgamma")
    try:
        subprocess.Popen([xgamma_path, "-gamma", "1.0"])
    except (FileNotFoundError, TypeError):
        logger.warning("xgamma is not available on your system")
    except PermissionError:
        logger.warning("you do not have permission to call xgamma")


def get_xrandr_version():
    """Return the major and minor version of XRandR utility"""
    pattern = "version"
    xrandr_output = (
        subprocess.Popen(["xrandr", "--version"], stdout=subprocess.PIPE)
        .communicate()[0]
        .decode()
    )
    position = xrandr_output.find(pattern) + len(pattern)
    version_str = xrandr_output[position:].strip().split(".")
    logger.debug("Found XrandR version %s", version_str)
    try:
        return {"major": int(version_str[0]), "minor": int(version_str[1])}
    except ValueError:
        logger.error("Can't find version in: %s", xrandr_output)
        return {"major": 0, "minor": 0}


def _get_graphics_adapters():
    """Return the list of graphics cards available on a system

    Returns:
        list: list of tuples containing PCI ID and description of the display controller
    """
    lspci_path = system.find_executable("lspci")
    dev_subclasses = ["VGA", "XGA", "3D controller", "Display controller"]
    if not lspci_path:
        logger.warning("lspci is not available. List of graphics cards not available")
        return []
    return [
        (pci_id, device_desc.split(": ")[1])
        for pci_id, device_desc in [
            line.split(maxsplit=1)
            for line in system.execute(lspci_path).split("\n")
            if any(subclass in line for subclass in dev_subclasses)
        ]
    ]


class LegacyDisplayManager:  # pylint: disable=too-few-public-methods
    """Legacy XrandR based display manager.
    Does not work on Wayland.
    """
    @staticmethod
    def get_display_names():
        """Return output names from XrandR"""
        return [output.name for output in get_outputs()]

    @staticmethod
    def get_resolutions():
        return get_resolutions()

    @staticmethod
    def get_current_resolution():
        """Return the current resolution for the desktop"""
        for line in _get_vidmodes():
            if line.startswith("  ") and "*" in line:
                resolution_match = re.match(r".*?(\d+x\d+).*", line)
                if resolution_match:
                    return resolution_match.groups()[0].split("x")
        return ("", "")


class DisplayManager:
    """Get display and resolution using GnomeDesktop"""
    def __init__(self):
        screen = Gdk.Screen.get_default()
        if not screen:
            raise NoScreenDetected
        self.rr_screen = GnomeDesktop.RRScreen.new(screen)
        self.rr_config = GnomeDesktop.RRConfig.new_current(self.rr_screen)
        self.rr_config.load_current()

    def get_display_names(self):
        """Return names of connected displays"""
        return [
            output_info.get_display_name()
            for output_info in self.rr_config.get_outputs()
        ]

    def get_resolutions(self):
        """Return available resolutions"""
        resolutions = []
        for mode in self.rr_screen.list_modes():
            resolutions.append("%sx%s" % (mode.get_width(), mode.get_height()))
        return sorted(
            set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True
        )

    def get_primary_output(self):
        """Return the RROutput used as a primary display"""
        for output in self.rr_screen.list_outputs():
            if output.get_is_primary():
                return output

    def get_current_resolution(self):
        """Return the current resolution for the primary display"""
        output = self.get_primary_output()
        if not output:
            logger.error("Failed to get a default output")
            return ("", "")
        current_mode = output.get_current_mode()
        return str(current_mode.get_width()), str(current_mode.get_height())


try:
    DISPLAY_MANAGER = DisplayManager()
except (GLib.Error, NoScreenDetected):
    DISPLAY_MANAGER = LegacyDisplayManager()

USE_DRI_PRIME = len(_get_graphics_adapters()) > 1


def get_resolution_choices():
    """Return list of available resolutions as label, value tuples
    suitable for inclusion in drop-downs.
    """
    resolutions = DISPLAY_MANAGER.get_resolutions()
    resolution_choices = list(zip(resolutions, resolutions))
    resolution_choices.insert(0, ("Keep current", "off"))
    return resolution_choices


def get_output_choices():
    """Return list of outputs for drop-downs"""
    displays = DISPLAY_MANAGER.get_display_names()
    output_choices = list(zip(displays, displays))
    output_choices.insert(0, ("Off", "off"))
    output_choices.insert(1, ("Primary", "primary"))
    return output_choices


def get_output_list():
    """Return a list of output with their index.
    This is used to indicate to SDL 1.2 which monitor to use.
    """
    choices = [("Off", "off")]
    displays = DISPLAY_MANAGER.get_display_names()
    for index, output in enumerate(displays):
        # Display name can't be used because they might not be in the right order
        # Using DISPLAYS to get the number of connected monitors
        choices.append((output, str(index)))
    return choices


def get_compositor_commands():
    """Nominated for the worst function in lutris"""
    start_compositor = None
    stop_compositor = None
    desktop_session = os.environ.get("DESKTOP_SESSION")
    if desktop_session == "plasma":
        stop_compositor = (
            "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.suspend"
        )
        start_compositor = (
            "qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.resume"
        )
    elif (
            desktop_session == "mate"
            and system.execute(
                "gsettings get org.mate.Marco.general compositing-manager", shell=True
            )
            == "true"
    ):
        stop_compositor = (
            "gsettings set org.mate.Marco.general compositing-manager false"
        )
        start_compositor = (
            "gsettings set org.mate.Marco.general compositing-manager true"
        )
    elif (
            desktop_session == "xfce"
            and system.execute(
                "xfconf-query --channel=xfwm4 --property=/general/use_compositing",
                shell=True,
            )
            == "true"
    ):
        stop_compositor = (
            "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=false"
        )
        start_compositor = (
            "xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=true"
        )
    elif (
            desktop_session == "deepin"
            and system.execute(
                "dbus-send --session --dest=com.deepin.WMSwitcher --type=method_call "
                "--print-reply=literal /com/deepin/WMSwitcher com.deepin.WMSwitcher.CurrentWM",
                shell=True,
            )
            == "deepin wm"
    ):
        start_compositor, stop_compositor = (
            "dbus-send --session --dest=com.deepin.WMSwitcher --type=method_call "
            "/com/deepin/WMSwitcher com.deepin.WMSwitcher.RequestSwitchWM",
        ) * 2
    return start_compositor, stop_compositor
