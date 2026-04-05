"""Module to deal with various aspects of displays"""

from __future__ import annotations

# isort:skip_file
import enum
import os
import subprocess
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

# GnomeDesktop 3.0 requires GTK 3 and cannot coexist with GTK 4.
# The GnomeDesktop-based DisplayManager is no longer available;
# we fall through to MutterDisplayManager or LegacyDisplayManager instead.
LIB_GNOME_DESKTOP_AVAILABLE = False
GnomeDesktop = None

try:
    from dbus.exceptions import DBusException

    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False

from gi.repository import Gdk, GLib, Gio, Gtk

from lutris.util import cache_single
from lutris.settings import DEFAULT_RESOLUTION_HEIGHT, DEFAULT_RESOLUTION_WIDTH
from lutris.util.graphics.displayconfig import MutterDisplayManager
from lutris.util.graphics.xrandr import LegacyDisplayManager, change_resolution, get_outputs, Output
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication


def get_default_dpi() -> int:
    """Computes the DPI to use for the primary monitor
    which we pass to WINE."""
    display = Gdk.Display.get_default()
    if display:
        monitors = display.get_monitors()
        if monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            if not monitor:
                return 96
            scale = monitor.get_scale_factor()
            dpi = 96 * scale
            return int(dpi)
    return 96


@cache_single
def is_display_x11() -> bool:
    """True if"""
    display = Gdk.Display.get_default()
    return "x11" in type(display).__name__.casefold()


class DisplayManager:
    """Get display and resolution using XRandR (GnomeDesktop no longer available with GTK 4)"""

    @staticmethod
    def get_display_names() -> list[str]:
        """Return names of connected displays"""
        return [output.name for output in get_outputs()]

    @staticmethod
    def get_resolutions() -> list[str]:
        """Return available resolutions"""
        resolutions = []
        for output in get_outputs():
            resolutions.append(output.mode)
        if not resolutions:
            logger.error("Failed to generate resolution list")
            return ["%sx%s" % (DEFAULT_RESOLUTION_WIDTH, DEFAULT_RESOLUTION_HEIGHT)]
        return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

    @staticmethod
    def get_current_resolution() -> tuple[str, str]:
        """Return the current resolution for the primary display"""
        outputs = get_outputs()
        primary = next((o for o in outputs if o.primary), None) or (outputs[0] if outputs else None)
        if primary and primary.mode:
            parts = primary.mode.split("x")
            if len(parts) == 2:
                return parts[0], parts[1]
        return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)

    @staticmethod
    def set_resolution(resolution: str | Iterable[Output]) -> None:
        """Set the resolution of one or more displays."""
        return change_resolution(resolution)

    @staticmethod
    def get_config() -> list[Output]:
        """Return the current display configuration."""
        return get_outputs()


def get_display_manager() -> MutterDisplayManager | DisplayManager | LegacyDisplayManager:
    """Return the appropriate display manager instance.
    Defaults to Mutter if available. This is the only one to support Wayland.
    """
    if DBUS_AVAILABLE:
        try:
            return MutterDisplayManager()
        except DBusException as ex:
            logger.debug("Mutter DBus service not reachable: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception("Failed to instantiate MutterDisplayConfig. Please report with exception: %s", ex)
    else:
        logger.error("DBus is not available, Lutris was not properly installed.")

    return LegacyDisplayManager()


DISPLAY_MANAGER = get_display_manager()


class DesktopEnvironment(enum.Enum):
    """Enum of desktop environments."""

    PLASMA = 0
    MATE = 1
    XFCE = 2
    DEEPIN = 3
    UNKNOWN = 999


# These desktop environment use a compositor that can be detected with a specific
# command, and which provide a definite answer; the DE can be asked to start and stop it..
_compositor_commands_by_de = {
    DesktopEnvironment.MATE: {
        "check": ["gsettings", "get", "org.mate.Marco.general", "compositing-manager"],
        "active_result": b"true\n",
        "stop_compositor": ["gsettings", "set", "org.mate.Marco.general", "compositing-manager", "false"],
        "start_compositor": ["gsettings", "set", "org.mate.Marco.general", "compositing-manager", "true"],
    },
    DesktopEnvironment.XFCE: {
        "check": ["xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing"],
        "active_result": b"true\n",
        "stop_compositor": ["xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing", "--set=false"],
        "start_compositor": ["xfconf-query", "--channel=xfwm4", "--property=/general/use_compositing", "--set=true"],
    },
    DesktopEnvironment.DEEPIN: {
        "check": [
            "dbus-send",
            "--session",
            "--dest=com.deepin.WMSwitcher",
            "--type=method_call",
            "--print-reply=literal",
            "/com/deepin/WMSwitcher",
            "com.deepin.WMSwitcher.CurrentWM",
        ],
        "active_result": b"deepin wm\n",
        "stop_compositor": [
            "dbus-send",
            "--session",
            "--dest=com.deepin.WMSwitcher",
            "--type=method_call",
            "/com/deepin/WMSwitcher",
            "com.deepin.WMSwitcher.RequestSwitchWM",
        ],
        "start_compositor": [
            "dbus-send",
            "--session",
            "--dest=com.deepin.WMSwitcher",
            "--type=method_call",
            "/com/deepin/WMSwitcher",
            "com.deepin.WMSwitcher.RequestSwitchWM",
        ],
    },
}

# These additional compositors can be detected by looking for their process,
# and must be started more directly.
_non_de_compositor_commands = [
    {
        "check": ["pgrep", "picom"],
        "stop_compositor": ["pkill", "picom"],
        "start_compositor": ["picom", ""],
        "run_in_background": True,
    },
    {
        "check": ["pgrep", "compton"],
        "stop_compositor": ["pkill", "compton"],
        "start_compositor": ["compton", ""],
        "run_in_background": True,
    },
]


def get_desktop_environment() -> DesktopEnvironment | None:
    """Converts the value of the DESKTOP_SESSION environment variable
    to one of the constants in the DesktopEnvironment class.
    Returns None if DESKTOP_SESSION is empty or unset.
    """
    desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()
    if not desktop_session:
        return None
    if desktop_session.endswith("mate"):
        return DesktopEnvironment.MATE
    if desktop_session.endswith("xfce"):
        return DesktopEnvironment.XFCE
    if desktop_session.endswith("deepin"):
        return DesktopEnvironment.DEEPIN
    if "plasma" in desktop_session:
        return DesktopEnvironment.PLASMA
    return DesktopEnvironment.UNKNOWN


def _get_command_output(command: list[str]) -> bytes | None:
    """Some rogue function that gives no shit about residing in the correct module"""
    try:
        return subprocess.Popen(  # pylint: disable=consider-using-with
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, close_fds=True
        ).communicate()[0]
    except FileNotFoundError:
        logger.error("Unable to run command, %s not found", command[0])

    return None


def is_compositing_enabled() -> bool:
    """Checks whether compositing is currently disabled or enabled.
    Returns True for enabled, False for disabled or if we didn't recognize
    the compositor.
    """

    desktop_environment = get_desktop_environment()
    if desktop_environment in _compositor_commands_by_de:
        command_set = _compositor_commands_by_de[desktop_environment]
        return _check_compositor_active(command_set)

    for command_set in _non_de_compositor_commands:
        if _check_compositor_active(command_set):
            return True

    # No compositor detected
    return False


def _check_compositor_active(command_set: dict[str, Any]) -> bool:
    """Applies the 'check' command; and returns whether the result
    was the desired 'active_result'; if that is omitted, we check for
    any result at all."""
    command = command_set["check"]
    result = _get_command_output(command)

    if "active_result" in command_set:
        return bool(result == command_set["active_result"])

    return result != b""


# One element is appended to this for every invocation of disable_compositing:
# True if compositing has been disabled, False if not. enable_compositing
# removes the last element, and only re-enables compositing if that element
# was True.
_COMPOSITING_DISABLED_STACK = []


@cache_single
def _get_compositor_commands() -> tuple[list[str] | None, list[str] | None, bool]:
    """Returns the commands to enable/disable compositing on the current
    desktop environment as a 3-tuple: start command, stop-command and
    a flag to indicate if we need to run the commands in the background.
    """
    desktop_environment = get_desktop_environment()
    command_set = None
    if desktop_environment is not None:
        command_set = _compositor_commands_by_de.get(desktop_environment)

    if not command_set:
        for c in _non_de_compositor_commands:
            if _check_compositor_active(c):
                command_set = c
                break

    if command_set:
        start_compositor: list[str] = command_set["start_compositor"]
        stop_compositor: list[str] = command_set["stop_compositor"]
        run_in_background = bool(command_set.get("run_in_background"))
        return start_compositor, stop_compositor, run_in_background

    return None, None, False


def _run_command(*command: str, run_in_background: bool = False) -> subprocess.Popen[bytes] | None:
    """Random _run_command lost in the middle of the project,
    are you lost little _run_command?
    """
    try:
        if run_in_background:
            command = " ".join(command)
        return subprocess.Popen(  # pylint: disable=consider-using-with
            command,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            shell=run_in_background,
            start_new_session=run_in_background,
        )
    except FileNotFoundError:
        errorMessage = "FileNotFoundError when running command:", command
        logger.error(errorMessage)

    return None


def disable_compositing() -> None:
    """Disable compositing if not already disabled."""
    compositing_enabled = is_compositing_enabled()
    if any(_COMPOSITING_DISABLED_STACK):
        compositing_enabled = False
    _COMPOSITING_DISABLED_STACK.append(compositing_enabled)
    if not compositing_enabled:
        return
    _, stop_compositor, background = _get_compositor_commands()
    if stop_compositor:
        _run_command(*stop_compositor, run_in_background=background)


def enable_compositing() -> None:
    """Re-enable compositing if the corresponding call to disable_compositing
    disabled it."""

    compositing_disabled = _COMPOSITING_DISABLED_STACK.pop()
    if not compositing_disabled:
        return
    start_compositor, _, background = _get_compositor_commands()
    if start_compositor:
        _run_command(*start_compositor, run_in_background=background)


class DBusScreenSaverInhibitor:
    """Inhibit and uninhibit the suspend using DBus.

    It will use the Gtk.Application's inhibit and uninhibit methods to
    prevent the computer from going to sleep.

    For enviroments which don't support either org.freedesktop.ScreenSaver or
    org.gnome.ScreenSaver interfaces one can declare a DBus interface which
    requires the Inhibit() and UnInhibit() methods to be exposed."""

    def __init__(self) -> None:
        self.proxy = None
        self._used_gtk_fallback = False

    def set_dbus_iface(self, name: str, path: str, interface: str, bus_type: Gio.BusType = Gio.BusType.SESSION) -> None:
        """Sets a dbus proxy to be used instead of Gtk.Application methods, this
        method can raise an exception."""
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type, Gio.DBusProxyFlags.NONE, None, name, path, interface, None
        )

    def inhibit(self, game_name: str) -> int | None:
        """Inhibit suspend.
        Returns a cookie that must be passed to the corresponding uninhibit() call.
        If an error occurs, None is returned instead."""
        reason = "Running game: %s" % game_name
        self._used_gtk_fallback = False

        if self.proxy:
            try:
                cookie = self.proxy.Inhibit("(ss)", "Lutris", reason)
                if cookie:
                    return cookie
                # D-Bus call succeeded but returned no cookie
                logger.warning("D-Bus screensaver inhibit returned no cookie, falling back to GTK")
            except Exception as ex:
                logger.warning("Failed to inhibit screensaver via D-Bus, falling back to GTK: %s", ex)

        # GTK fallback
        app: "LutrisApplication" = Gio.Application.get_default()

        window = app.window
        flags = Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.IDLE
        cookie = app.inhibit(window, flags, reason)

        # Gtk.Application.inhibit returns 0 if there was an error.
        if cookie == 0:
            return None

        self._used_gtk_fallback = True
        return cookie

    def uninhibit(self, cookie: int | None) -> None:
        """Uninhibit suspend.
        Takes a cookie as returned by inhibit. If cookie is None, no action is taken."""
        if not cookie:
            return

        if self.proxy and not self._used_gtk_fallback:
            try:
                self.proxy.UnInhibit("(u)", cookie)
                return
            except Exception as ex:
                logger.warning("Failed to uninhibit screensaver via D-Bus: %s", ex)

        # GTK fallback
        app: "LutrisApplication" = Gio.Application.get_default()
        app.uninhibit(cookie)


def _get_suspend_inhibitor() -> DBusScreenSaverInhibitor:
    """Return the appropriate suspend inhibitor instance.
    If the required interface isn't available, it will default to GTK's
    implementation."""
    desktop_environment = get_desktop_environment()
    inhibitor = DBusScreenSaverInhibitor()

    # Build list of D-Bus interfaces to try in order of preference
    interfaces_to_try = []

    if desktop_environment is DesktopEnvironment.MATE:
        interfaces_to_try.append(("org.mate.ScreenSaver", "/", "org.mate.ScreenSaver"))
    elif desktop_environment is DesktopEnvironment.XFCE:
        # Try XFCE-specific interface first, then fall back to freedesktop.
        # Some XFCE setups use xfce4-screensaver (org.xfce.ScreenSaver),
        # others use light-locker or other lockers (org.freedesktop.ScreenSaver).
        interfaces_to_try.append(("org.xfce.ScreenSaver", "/", "org.xfce.ScreenSaver"))
        interfaces_to_try.append(
            ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver")
        )

    for name, path, interface in interfaces_to_try:
        try:
            inhibitor.set_dbus_iface(name, path, interface)
            logger.debug("Using D-Bus screensaver interface: %s", name)
            return inhibitor
        except GLib.Error as err:
            logger.debug("D-Bus interface %s not available: %s", name, err)

    # No D-Bus interface available, will use GTK fallback
    return inhibitor


SCREEN_SAVER_INHIBITOR = _get_suspend_inhibitor()
