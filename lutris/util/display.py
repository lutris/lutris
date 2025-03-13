"""Module to deal with various aspects of displays"""

# isort:skip_file
import enum
import os
import json
import subprocess
from typing import Any, Dict

import gi

try:
    gi.require_version("GnomeDesktop", "3.0")
    from gi.repository import GnomeDesktop

    LIB_GNOME_DESKTOP_AVAILABLE = True
except ValueError:
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
from lutris.util.graphics.xrandr import LegacyDisplayManager, change_resolution, get_outputs
from lutris.util.log import logger


def get_default_dpi():
    """Computes the DPI to use for the primary monitor
    which we pass to WINE."""
    display = Gdk.Display.get_default()
    if display:
        monitor = display.get_primary_monitor()
        if monitor:
            scale = monitor.get_scale_factor()
            dpi = 96 * scale
            return int(dpi)
    return 96


@cache_single
def is_display_x11():
    """True if"""
    display = Gdk.Display.get_default()
    return "x11" in type(display).__name__.casefold()


@cache_single
def is_display_wayland():
    """True if the current display is Wayland"""
    display = Gdk.Display.get_default()
    return "wayland" in type(display).__name__.casefold()


class DisplayManager:
    """Get display and resolution using various backends based on the current environment"""

    def __init__(self, screen=None):
        self.display = Gdk.Display.get_default()
        self.screen = screen
        self.hyprctl_path = None
        self.rr_screen = None
        self.rr_config = None

        # Determine which backend to use
        self.backend = self._determine_backend()

        # Initialize the appropriate backend
        if self.backend == "hyprland":
            self._init_hyprland()
        elif self.backend == "gnome" and screen:
            self._init_gnome(screen)

    def _determine_backend(self):
        """Determine which backend to use based on the environment"""
        # Check for Hyprland
        if "HYPRLAND_INSTANCE_SIGNATURE" in os.environ:
            for path in os.environ.get("PATH", "").split(os.pathsep):
                hyprctl_path = os.path.join(path, "hyprctl")
                if os.path.isfile(hyprctl_path) and os.access(hyprctl_path, os.X_OK):
                    self.hyprctl_path = hyprctl_path
                    return "hyprland"

        # Check for GNOME Desktop
        if LIB_GNOME_DESKTOP_AVAILABLE and self.screen:
            return "gnome"
        # Generic Wayland
        if is_display_wayland():
            return "wayland"
        # X11
        if is_display_x11():
            return "x11"
        return "fallback"

    def _init_gnome(self, screen):
        """Initialize GNOME Desktop backend"""
        self.rr_screen = GnomeDesktop.RRScreen.new(screen)
        self.rr_config = GnomeDesktop.RRConfig.new_current(self.rr_screen)
        self.rr_config.load_current()

    def _init_hyprland(self):
        """Initialize Hyprland backend"""
        # Already have hyprctl_path from _determine_backend
        pass

    def _run_hyprctl(self, *args):
        """Run hyprctl with given arguments and return the output"""
        if not self.hyprctl_path:
            return {}

        try:
            cmd = [self.hyprctl_path, *args, "-j"]  # Use JSON output
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError) as ex:
            logger.error(f"Error running hyprctl: {ex}")
            return {}

    def get_display_names(self):
        """Return names of connected displays"""
        if self.backend == "hyprland":
            monitors = self._run_hyprctl("monitors")
            if not monitors:
                return []
            return [monitor.get("name") for monitor in monitors]

        elif self.backend == "gnome" and self.rr_config:
            return [output_info.get_display_name() for output_info in self.rr_config.get_outputs()]

        elif self.backend == "wayland":
            names = []
            n_monitors = self.display.get_n_monitors()
            for i in range(n_monitors):
                monitor = self.display.get_monitor(i)
                model = monitor.get_model()
                names.append(model if model else f"Monitor-{i}")
            return names

        else:
            # Fallback to XRandR
            return LegacyDisplayManager().get_display_names()

    def get_resolutions(self):
        """Return available resolutions"""
        if self.backend == "hyprland":
            modes = []
            monitors = self._run_hyprctl("monitors")

            # If no monitors, return default
            if not monitors:
                return [f"{DEFAULT_RESOLUTION_WIDTH}x{DEFAULT_RESOLUTION_HEIGHT}"]

            # Get modes from monitors
            for monitor in monitors:
                if monitor.get("reserved"):  # Skip special monitors
                    continue

                width = monitor.get("width")
                height = monitor.get("height")
                if width and height:
                    modes.append(f"{width}x{height}")

            if not modes:
                return [f"{DEFAULT_RESOLUTION_WIDTH}x{DEFAULT_RESOLUTION_HEIGHT}"]

            return sorted(set(modes), key=lambda x: int(x.split("x")[0]), reverse=True)

        elif self.backend == "gnome" and self.rr_screen:
            resolutions = ["%sx%s" % (mode.get_width(), mode.get_height()) for mode in self.rr_screen.list_modes()]
            if not resolutions:
                logger.error("Failed to generate resolution list from default GdkScreen")
                return ["%sx%s" % (DEFAULT_RESOLUTION_WIDTH, DEFAULT_RESOLUTION_HEIGHT)]
            return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

        elif self.backend == "wayland":
            # For generic Wayland, we can only report current resolutions
            resolutions = []
            n_monitors = self.display.get_n_monitors()
            for i in range(n_monitors):
                monitor = self.display.get_monitor(i)
                geometry = monitor.get_geometry()
                resolution = f"{geometry.width}x{geometry.height}"
                resolutions.append(resolution)

            if not resolutions:
                return [f"{DEFAULT_RESOLUTION_WIDTH}x{DEFAULT_RESOLUTION_HEIGHT}"]

            return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

        else:
            # Fallback to XRandR
            return LegacyDisplayManager().get_resolutions()

    def _get_primary_output_gnome(self):
        """Return the RROutput used as a primary display (GNOME backend)"""
        if not self.rr_screen:
            return None

        for output in self.rr_screen.list_outputs():
            if output.get_is_primary():
                return output
        return None

    def get_current_resolution(self):
        """Return the current resolution for the primary display"""
        if self.backend == "hyprland":
            monitors = self._run_hyprctl("monitors")

            # Find primary/focused monitor
            primary_monitor = None
            for monitor in monitors:
                if monitor.get("focused", False):
                    primary_monitor = monitor
                    break

            if not primary_monitor:
                # If no primary found, use the first non-reserved one
                for monitor in monitors:
                    if not monitor.get("reserved"):
                        primary_monitor = monitor
                        break

            if not primary_monitor:
                logger.error("Failed to get a primary monitor from Hyprland")
                return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)

            width = primary_monitor.get("width", DEFAULT_RESOLUTION_WIDTH)
            height = primary_monitor.get("height", DEFAULT_RESOLUTION_HEIGHT)
            return str(width), str(height)

        elif self.backend == "gnome":
            output = self._get_primary_output_gnome()
            if not output:
                logger.error("Failed to get a default output")
                return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)
            current_mode = output.get_current_mode()
            return str(current_mode.get_width()), str(current_mode.get_height())

        elif self.backend == "wayland":
            monitor = self.display.get_primary_monitor()
            if not monitor:
                # Fall back to first monitor if no primary
                if self.display.get_n_monitors() > 0:
                    monitor = self.display.get_monitor(0)

            if not monitor:
                logger.error("Failed to get a monitor from Wayland display")
                return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)

            geometry = monitor.get_geometry()
            return str(geometry.width), str(geometry.height)

        else:
            # Fallback to XRandR
            return LegacyDisplayManager().get_current_resolution()

    def set_resolution(self, resolution):
        """Set the resolution of one or more displays"""
        if self.backend == "hyprland":
            if isinstance(resolution, list):
                # We don't support multi-monitor configuration yet
                logger.warning("Multi-monitor configuration not supported for Hyprland")
                return False

            try:
                width, height = resolution.split("x")
                monitor = self._get_focused_monitor_name_hyprland()
                if not monitor:
                    logger.error("Failed to get focused monitor")
                    return False

                # Format: keyword arg=value
                cmd = [self.hyprctl_path, "keyword", f"monitor,{monitor},preferred,auto,{float(width)/float(height)}"]
                subprocess.run(cmd, check=True)
                return True
            except (ValueError, subprocess.SubprocessError) as ex:
                logger.error(f"Failed to set resolution in Hyprland: {ex}")
                return False

        elif self.backend in ("x11", "gnome"):
            # Both use XRandR underneath
            return change_resolution(resolution)

        elif self.backend == "wayland":
            logger.warning("Cannot set resolution directly in generic Wayland mode")
            return False

        else:
            return LegacyDisplayManager().set_resolution(resolution)

    def _get_focused_monitor_name_hyprland(self):
        """Get the name of the focused monitor (Hyprland backend)"""
        monitors = self._run_hyprctl("monitors")
        for monitor in monitors:
            if monitor.get("focused", False):
                return monitor.get("name")
        return None

    def get_config(self):
        """Return the current display configuration"""
        if self.backend == "hyprland":
            # For Hyprland, we'll just return the current resolutions as strings
            monitors = self._run_hyprctl("monitors")
            configs = []

            for monitor in monitors:
                if monitor.get("reserved"):
                    continue
                width = monitor.get("width")
                height = monitor.get("height")
                if width and height:
                    configs.append(f"{width}x{height}")

            return configs

        elif self.backend == "wayland":
            # For generic Wayland, return current resolutions
            return self.get_resolutions()

        else:
            # Use XRandR for X11 and GNOME
            return get_outputs()


def get_display_manager():
    """Return the appropriate display manager instance."""
    # Try Mutter (which supports Wayland) if DBus is available
    if DBUS_AVAILABLE:
        try:
            return MutterDisplayManager()
        except DBusException as ex:
            logger.debug("Mutter DBus service not reachable: %s", ex)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception("Failed to instantiate MutterDisplayConfig. Please report with exception: %s", ex)
    else:
        logger.error("DBus is not available, Lutris was not properly installed.")

    # For GNOME Desktop or other backends
    try:
        screen = Gdk.Screen.get_default()
        return DisplayManager(screen)
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception("Failed to instantiate DisplayManager: %s", ex)
        return LegacyDisplayManager()


DISPLAY_MANAGER = get_display_manager()


class DesktopEnvironment(enum.Enum):
    """Enum of desktop environments."""

    PLASMA = 0
    MATE = 1
    XFCE = 2
    DEEPIN = 3
    HYPRLAND = 4
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
    DesktopEnvironment.HYPRLAND: {
        "check": ["echo", "$HYPRLAND_CMD"],
        "active_result": b"Hyprland\n",
        "stop_compositor": ["Hyprland"],
        "start_compositor": ["hyprctl", "dispatch", "exit"],
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


def get_desktop_environment():
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
    if os.environ.get("XDG_SESSION_DESKTOP", "") == "Hyprland":
        return DesktopEnvironment.HYPRLAND
    return DesktopEnvironment.UNKNOWN


def _get_command_output(command):
    """Some rogue function that gives no shit about residing in the correct module"""
    try:
        return subprocess.Popen(  # pylint: disable=consider-using-with
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, close_fds=True
        ).communicate()[0]
    except FileNotFoundError:
        logger.error("Unable to run command, %s not found", command[0])


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


def _check_compositor_active(command_set: Dict[str, Any]) -> bool:
    """Applies the 'check' command; and returns whether the result
    was the desired 'active_result'; if that is omitted, we check for
    any result at all."""
    command = command_set["check"]
    result = _get_command_output(command)

    if "active_result" in command_set:
        return result == command_set["active_result"]

    return result != b""


# One element is appended to this for every invocation of disable_compositing:
# True if compositing has been disabled, False if not. enable_compositing
# removes the last element, and only re-enables compositing if that element
# was True.
_COMPOSITING_DISABLED_STACK = []


@cache_single
def _get_compositor_commands():
    """Returns the commands to enable/disable compositing on the current
    desktop environment as a 3-tuple: start command, stop-command and
    a flag to indicate if we need to run the commands in the background.
    """
    desktop_environment = get_desktop_environment()
    command_set = _compositor_commands_by_de.get(desktop_environment)

    if not command_set:
        for c in _non_de_compositor_commands:
            if _check_compositor_active(c):
                command_set = c
                break

    if command_set:
        start_compositor = command_set["start_compositor"]
        stop_compositor = command_set["stop_compositor"]
        run_in_background = bool(command_set.get("run_in_background"))
        return start_compositor, stop_compositor, run_in_background

    return None, None, False


def _run_command(*command, run_in_background=False):
    """Random _run_command lost in the middle of the project,
    are you lost little _run_command?
    """
    try:
        if not command:
            raise ValueError("No command provided")
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


def disable_compositing():
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


def enable_compositing():
    """Re-enable compositing if the corresponding call to disable_compositing
    disabled it."""

    compositing_disabled = _COMPOSITING_DISABLED_STACK.pop()
    if not compositing_disabled:
        return
    start_compositor, _, background = _get_compositor_commands()
    if start_compositor:
        _run_command(*start_compositor, run_in_background=background)


class DBusScreenSaverInhibitor:
    """Inhibit and uninhibit the screen saver using DBus.

    It will use the Gtk.Application's inhibit and uninhibit methods to inhibit
    the screen saver.

    For enviroments which don't support either org.freedesktop.ScreenSaver or
    org.gnome.ScreenSaver interfaces one can declare a DBus interface which
    requires the Inhibit() and UnInhibit() methods to be exposed."""

    def __init__(self):
        self.proxy = None

    def set_dbus_iface(self, name, path, interface, bus_type=Gio.BusType.SESSION):
        """Sets a dbus proxy to be used instead of Gtk.Application methods, this
        method can raise an exception."""
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type, Gio.DBusProxyFlags.NONE, None, name, path, interface, None
        )

    def inhibit(self, game_name):
        """Inhibit the screen saver.
        Returns a cookie that must be passed to the corresponding uninhibit() call.
        If an error occurs, None is returned instead."""
        reason = "Running game: %s" % game_name

        if self.proxy:
            try:
                return self.proxy.Inhibit("(ss)", "Lutris", reason)
            except Exception:
                return None
        else:
            app = Gio.Application.get_default()
            window = app.window
            flags = Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.IDLE
            cookie = app.inhibit(window, flags, reason)

            # Gtk.Application.inhibit returns 0 if there was an error.
            if cookie == 0:
                return None

            return cookie

    def uninhibit(self, cookie):
        """Uninhibit the screen saver.
        Takes a cookie as returned by inhibit. If cookie is None, no action is taken."""
        if not cookie:
            return

        if self.proxy:
            self.proxy.UnInhibit("(u)", cookie)
        else:
            app = Gio.Application.get_default()
            app.uninhibit(cookie)


def _get_screen_saver_inhibitor():
    """Return the appropriate screen saver inhibitor instance.
    If the required interface isn't available, it will default to GTK's
    implementation."""
    desktop_environment = get_desktop_environment()

    name = None
    inhibitor = DBusScreenSaverInhibitor()

    if desktop_environment is DesktopEnvironment.MATE:
        name = "org.mate.ScreenSaver"
        path = "/"
        interface = "org.mate.ScreenSaver"
    elif desktop_environment is DesktopEnvironment.XFCE:
        # According to
        # https://github.com/xfce-mirror/xfce4-session/blob/master/xfce4-session/xfce-screensaver.c#L240
        # The XFCE enviroment does support the org.freedesktop.ScreenSaver interface
        # but this might be not present in older releases.
        name = "org.xfce.ScreenSaver"
        path = "/"
        interface = "org.xfce.ScreenSaver"

    if name:
        try:
            inhibitor.set_dbus_iface(name, path, interface)
        except GLib.Error as err:
            logger.warning(
                "Failed to set up a DBus proxy for name %s, path %s, " "interface %s: %s", name, path, interface, err
            )

    return inhibitor


SCREEN_SAVER_INHIBITOR = _get_screen_saver_inhibitor()
