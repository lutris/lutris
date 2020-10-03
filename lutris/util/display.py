"""Module to deal with various aspects of displays"""
# isort:skip_file
import enum
import os
import subprocess
import gi

gi.require_version("GnomeDesktop", "3.0")

try:
    from dbus.exceptions import DBusException
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False

from gi.repository import Gdk, GLib, GnomeDesktop, Gio

from lutris.util import system
from lutris.util.graphics.displayconfig import MutterDisplayManager
from lutris.util.graphics.xrandr import LegacyDisplayManager, change_resolution, get_outputs
from lutris.util.log import logger


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
        (pci_id, device_desc.split(": ")[1]) for pci_id, device_desc in [
            line.split(maxsplit=1) for line in system.execute(lspci_path, timeout=3).split("\n")
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
        return [output_info.get_display_name() for output_info in self.rr_config.get_outputs()]

    def get_resolutions(self):
        """Return available resolutions"""
        resolutions = ["%sx%s" % (mode.get_width(), mode.get_height()) for mode in self.rr_screen.list_modes()]
        return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

    def _get_primary_output(self):
        """Return the RROutput used as a primary display"""
        for output in self.rr_screen.list_outputs():
            if output.get_is_primary():
                return output
        return

    def get_current_resolution(self):
        """Return the current resolution for the primary display"""
        output = self._get_primary_output()
        if not output:
            logger.error("Failed to get a default output")
            return "", ""
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
    if DBUS_AVAILABLE:
        try:
            return MutterDisplayManager()
        except DBusException as ex:
            logger.debug("Mutter DBus service not reachable: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception("Failed to instanciate MutterDisplayConfig. Please report with exception: %s", ex)
    else:
        logger.error("DBus is not available, lutris was not properly installed.")
    try:
        return DisplayManager()
    except (GLib.Error, NoScreenDetected):
        return LegacyDisplayManager()


DISPLAY_MANAGER = get_display_manager()
USE_DRI_PRIME = len(_get_graphics_adapters()) > 1


class DesktopEnvironment(enum.Enum):

    """Enum of desktop environments."""

    PLASMA = 0
    MATE = 1
    XFCE = 2
    DEEPIN = 3
    UNKNOWN = 999


def get_desktop_environment():
    """Converts the value of the DESKTOP_SESSION environment variable
    to one of the constants in the DesktopEnvironment class.
    Returns None if DESKTOP_SESSION is empty or unset.
    """
    desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()
    if not desktop_session:
        return None
    if desktop_session.endswith("plasma"):
        return DesktopEnvironment.PLASMA
    if desktop_session.endswith("mate"):
        return DesktopEnvironment.MATE
    if desktop_session.endswith("xfce"):
        return DesktopEnvironment.XFCE
    if desktop_session.endswith("deepin"):
        return DesktopEnvironment.DEEPIN
    return DesktopEnvironment.UNKNOWN


def _get_command_output(*command):
    """Some rogue function that gives no shit about residing in the correct module"""
    try:
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            close_fds=True
        ).communicate()[0]
    except FileNotFoundError:
        logger.error("Unable to run command, %s not found", command[0])


def is_compositing_enabled():
    """Checks whether compositing is currently disabled or enabled.
    Returns True for enabled, False for disabled, and None if unknown.
    """
    desktop_environment = get_desktop_environment()
    if desktop_environment is DesktopEnvironment.PLASMA:
        return _get_command_output(
            "qdbus", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.active"
        ) == b"true\n"
    if desktop_environment is DesktopEnvironment.MATE:
        return _get_command_output("gsettings", "get org.mate.Marco.general", "compositing-manager") == b"true\n"
    if desktop_environment is DesktopEnvironment.XFCE:
        return _get_command_output(
            "xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing"
        ) == b"true\n"
    if desktop_environment is DesktopEnvironment.DEEPIN:
        return _get_command_output(
            "dbus-send", "--session", "--dest=com.deepin.WMSwitcher", "--type=method_call",
            "--print-reply=literal", "/com/deepin/WMSwitcher", "com.deepin.WMSwitcher.CurrentWM"
        ) == b"deepin wm\n"
    return None


# One element is appended to this for every invocation of disable_compositing:
# True if compositing has been disabled, False if not. enable_compositing
# removes the last element, and only re-enables compositing if that element
# was True.
_COMPOSITING_DISABLED_STACK = []


def _get_compositor_commands():
    """Returns the commands to enable/disable compositing on the current
    desktop environment as a 2-tuple.
    """
    start_compositor = None
    stop_compositor = None
    desktop_environment = get_desktop_environment()
    if desktop_environment is DesktopEnvironment.PLASMA:
        stop_compositor = ("qdbus", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.suspend")
        start_compositor = ("qdbus", "org.kde.KWin", "/Compositor", "org.kde.kwin.Compositing.resume")
    elif desktop_environment is DesktopEnvironment.MATE:
        stop_compositor = ("gsettings", "set org.mate.Marco.general", "compositing-manager", "false")
        start_compositor = ("gsettings", "set org.mate.Marco.general", "compositing-manager", "true")
    elif desktop_environment is DesktopEnvironment.XFCE:
        stop_compositor = ("xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing", "--set=false")
        start_compositor = ("xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing", "--set=true")
    elif desktop_environment is DesktopEnvironment.DEEPIN:
        start_compositor = (
            "dbus-send", "--session", "--dest=com.deepin.WMSwitcher", "--type=method_call",
            "/com/deepin/WMSwitcher", "com.deepin.WMSwitcher.RequestSwitchWM",
        )
        stop_compositor = start_compositor
    return start_compositor, stop_compositor


def _run_command(*command):
    """Random _run_command lost in the middle of the project,
    are you lost little _run_command?
    """
    try:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=True)
    except FileNotFoundError:
        logger.error("Oh no")


def disable_compositing():
    """Disable compositing if not already disabled."""
    compositing_enabled = is_compositing_enabled()
    if compositing_enabled is None:
        compositing_enabled = True
    if any(_COMPOSITING_DISABLED_STACK):
        compositing_enabled = False
    _COMPOSITING_DISABLED_STACK.append(compositing_enabled)
    if not compositing_enabled:
        return
    _, stop_compositor = _get_compositor_commands()
    if stop_compositor:
        _run_command(*stop_compositor)


def enable_compositing():
    """Re-enable compositing if the corresponding call to disable_compositing
    disabled it."""
    compositing_disabled = _COMPOSITING_DISABLED_STACK.pop()
    if not compositing_disabled:
        return
    start_compositor, _ = _get_compositor_commands()
    if start_compositor:
        _run_command(*start_compositor)


class DBusScreenSaverInhibitor:

    """Inhibit and uninhibit the screen saver using DBus.
    Requires the Inhibit() and UnInhibit() methods to be exposed over DBus."""

    def __init__(self, name, path, interface, bus_type=Gio.BusType.SESSION):
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type, Gio.DBusProxyFlags.NONE, None, name, path, interface, None)

    def inhibit(self, game_name):
        """Inhibit the screen saver.
        Returns a cookie that must be passed to the corresponding uninhibit() call.
        If an error occurs, None is returned instead."""
        try:
            return self.proxy.Inhibit("(ss)", "Lutris", "Running game: %s" % game_name)
        except Exception:
            return None

    def uninhibit(self, cookie):
        """Uninhibit the screen saver.
        Takes a cookie as returned by inhibit. If cookie is None, no action is taken."""
        if cookie is not None:
            self.proxy.UnInhibit("(u)", cookie)


def _get_screen_saver_inhibitor():
    """Return the appropriate screen saver inhibitor instance.
    Returns None if the required interface isn't available."""
    desktop_environment = get_desktop_environment()
    if desktop_environment is DesktopEnvironment.MATE:
        name = "org.mate.ScreenSaver"
        path = "/"
    elif desktop_environment is DesktopEnvironment.XFCE:
        name = "org.xfce.ScreenSaver"
        path = "/"
    else:
        name = "org.freedesktop.ScreenSaver"
        path = "/org/freedesktop/ScreenSaver"
    interface = name
    try:
        return DBusScreenSaverInhibitor(name, path, interface)
    except GLib.Error as err:
        logger.error("Error during creation of DBusScreenSaverInhibitor: %s", err.message)  # pylint: disable=no-member
        return None


SCREEN_SAVER_INHIBITOR = _get_screen_saver_inhibitor()
