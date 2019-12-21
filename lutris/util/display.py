"""Module to deal with various aspects of displays"""
import os
import subprocess
from dbus.exceptions import DBusException

from gi.repository import Gdk, GnomeDesktop, GLib

from lutris.util import system
from lutris.util.log import logger
from lutris.util.graphics.xrandr import LegacyDisplayManager, change_resolution, get_outputs
from lutris.util.graphics.displayconfig import MutterDisplayManager


class NoScreenDetected(Exception):
    """Raise this when unable to detect screens"""


def restore_gamma():
    """Restores gamma to a normal level."""
    xgamma_path = system.find_executable("xgamma")
    try:
        subprocess.Popen([xgamma_path, "-gamma", "1.0"])
    except (FileNotFoundError, TypeError):
        logger.warning("xgamma is not available on your system")
    except PermissionError:
        logger.warning("you do not have permission to call xgamma")


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
        resolutions = [
            "%sx%s" % (mode.get_width(), mode.get_height())
            for mode in self.rr_screen.list_modes()
        ]
        return sorted(
            set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True
        )

    def _get_primary_output(self):
        """Return the RROutput used as a primary display"""
        for output in self.rr_screen.list_outputs():
            if output.get_is_primary():
                return output

    def get_current_resolution(self):
        """Return the current resolution for the primary display"""
        output = self._get_primary_output()
        if not output:
            logger.error("Failed to get a default output")
            return ("", "")
        current_mode = output.get_current_mode()
        return str(current_mode.get_width()), str(current_mode.get_height())

    @staticmethod
    def set_resolution(resolution):
        """Set the resolution of one or more displays.
        The resolution can either be a string, which will be applied to the
        primary display or a list of configurations as returned by `get_config`.
        This method uses XrandR and will not work on Wayland.
        """
        return change_resolution(resolution)

    @staticmethod
    def get_config():
        """Return the current display resolution
        This method uses XrandR and will not work on wayland
        The output can be fed in `set_resolution`
        """
        return get_outputs()


def get_display_manager():
    """Return the appropriate display manager instance.
    Defaults to Mutter if available. This is the only one to support Wayland.
    """
    try:
        return MutterDisplayManager()
    except DBusException as ex:
        logger.debug("Mutter DBus service not reachable: %s", ex)
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception(
            "Failed to instanciate MutterDisplayConfig. Please report with exception: %s", ex
        )
    try:
        return DisplayManager()
    except (GLib.Error, NoScreenDetected):
        return LegacyDisplayManager()


DISPLAY_MANAGER = get_display_manager()
USE_DRI_PRIME = len(_get_graphics_adapters()) > 1


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
