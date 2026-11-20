"""The GTK frontend's DisplayBackend (lutris.util.display_backend): what GDK and
GnomeDesktop know about the displays."""

# isort:skip_file
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

import gi

try:
    gi.require_version("GnomeDesktop", "3.0")
    from gi.repository import GnomeDesktop  # type: ignore

    # check for AttributeError on newer systems on which the
    # deprecated attributes have been removed
    GnomeDesktop.RRScreen  # noqa: B018

    LIB_GNOME_DESKTOP_AVAILABLE = True
except ValueError, AttributeError:
    LIB_GNOME_DESKTOP_AVAILABLE = False
    GnomeDesktop = None

from gi.repository import Gdk, GLib, Gio, Gtk

from lutris.settings import DEFAULT_RESOLUTION_HEIGHT, DEFAULT_RESOLUTION_WIDTH
from lutris.util.display_backend import DisplayManager
from lutris.util.graphics.xrandr import Output, change_resolution, get_outputs
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication


class GnomeDesktopDisplayManager:
    """Get display and resolution using GnomeDesktop"""

    def __init__(self, screen: Gdk.Screen):
        if GnomeDesktop:
            self.rr_screen = GnomeDesktop.RRScreen.new(screen)
            self.rr_config = GnomeDesktop.RRConfig.new_current(self.rr_screen)
            self.rr_config.load_current()

    def get_display_names(self) -> list[str]:
        """Return names of connected displays"""
        return [output_info.get_display_name() for output_info in self.rr_config.get_outputs()]

    def get_resolutions(self) -> list[str]:
        """Return available resolutions"""
        resolutions = ["%sx%s" % (mode.get_width(), mode.get_height()) for mode in self.rr_screen.list_modes()]
        if not resolutions:
            logger.error("Failed to generate resolution list from default GdkScreen")
            return ["%sx%s" % (DEFAULT_RESOLUTION_WIDTH, DEFAULT_RESOLUTION_HEIGHT)]
        return sorted(set(resolutions), key=lambda x: int(x.split("x")[0]), reverse=True)

    def _get_primary_output(self) -> Any:
        """Return the RROutput used as a primary display"""
        for output in self.rr_screen.list_outputs():
            if output.get_is_primary():
                return output
        return None

    def get_current_resolution(self) -> tuple[str, str]:
        """Return the current resolution for the primary display"""
        output = self._get_primary_output()
        if not output:
            logger.error("Failed to get a default output")
            return str(DEFAULT_RESOLUTION_WIDTH), str(DEFAULT_RESOLUTION_HEIGHT)
        current_mode = output.get_current_mode()
        return str(current_mode.get_width()), str(current_mode.get_height())

    @staticmethod
    def set_resolution(resolution: str | Iterable[Output]) -> None:
        """Set the resolution of one or more displays.
        The resolution can either be a string, which will be applied to the
        primary display or a list of configurations as returned by `get_config`.
        This method uses XrandR and will not work on Wayland.
        """
        return change_resolution(resolution)

    @staticmethod
    def get_config() -> list[Output]:
        """Return the current display resolution
        This method uses XrandR and will not work on wayland
        The output can be fed in `set_resolution`
        """
        return get_outputs()


class GtkDisplayBackend:
    """Answers from GDK, reads display modes with GnomeDesktop where it's installed,
    and keeps the computer awake through the Gtk.Application."""

    def is_x11(self) -> bool:
        display = Gdk.Display.get_default()
        return "x11" in type(display).__name__.casefold()

    def get_scale_factor(self) -> int:
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        return monitor.get_scale_factor() if monitor else 1

    def get_display_manager(self) -> DisplayManager | None:
        if LIB_GNOME_DESKTOP_AVAILABLE:
            try:
                screen = Gdk.Screen.get_default()
                if screen:
                    return GnomeDesktopDisplayManager(screen)
            except GLib.Error:
                pass
        return None

    def inhibit_suspend(self, reason: str) -> int | None:
        app = cast("LutrisApplication | None", Gio.Application.get_default())
        if not app:
            return None
        flags = Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.IDLE
        cookie = app.inhibit(app.window, flags, reason)
        # Gtk.Application.inhibit returns 0 if there was an error.
        return cookie or None

    def uninhibit_suspend(self, cookie: int) -> None:
        app = Gio.Application.get_default()
        if app:
            cast(Gtk.Application, app).uninhibit(cookie)
