"""The Qt frontend's DisplayBackend (lutris.util.display_backend): what Qt knows
about the screen."""

from gi.repository import Gio, GLib
from PySide6.QtGui import QGuiApplication

from lutris.util.display_backend import DisplayManager
from lutris.util.log import logger

_SESSION = "org.gnome.SessionManager"
_SESSION_PATH = "/org/gnome/SessionManager"
_SCREENSAVER = "org.freedesktop.ScreenSaver"
_SCREENSAVER_PATH = "/org/freedesktop/ScreenSaver"


class QtDisplayBackend:
    """Use Qt for screen information and desktop services for display management."""

    def __init__(self) -> None:
        self._inhibitors: dict[int, tuple[str, str, str, int]] = {}
        self._next_cookie = 0

    def is_x11(self) -> bool:
        return QGuiApplication.platformName() == "xcb"

    def get_scale_factor(self) -> int:
        screen = QGuiApplication.primaryScreen()
        return max(1, round(screen.devicePixelRatio())) if screen else 1

    def get_display_manager(self) -> DisplayManager | None:
        return None

    def inhibit_suspend(self, reason: str) -> int | None:
        window = QGuiApplication.focusWindow()
        window_id = int(window.winId()) if self.is_x11() and window else 0
        for name, path, method, args in (
            (_SESSION, _SESSION_PATH, "Uninhibit", GLib.Variant("(susu)", ("Lutris", window_id, reason, 12))),
            (_SCREENSAVER, _SCREENSAVER_PATH, "UnInhibit", GLib.Variant("(ss)", ("Lutris", reason))),
        ):
            try:
                response = self._call(name, path, "Inhibit", args)
            except GLib.Error as error:
                logger.debug("Could not inhibit via %s: %s", name, error)
                continue
            self._next_cookie += 1
            self._inhibitors[self._next_cookie] = (name, path, method, response.get_child_value(0).get_uint32())
            return self._next_cookie
        return None

    def uninhibit_suspend(self, cookie: int) -> None:
        if inhibitor := self._inhibitors.pop(cookie, None):
            name, path, method, remote_cookie = inhibitor
            try:
                self._call(name, path, method, GLib.Variant("(u)", (remote_cookie,)))
            except GLib.Error as error:
                logger.warning("Could not release %s inhibitor: %s", name, error)

    @staticmethod
    def _call(name: str, path: str, method: str, args: GLib.Variant) -> GLib.Variant:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return bus.call_sync(name, path, name, method, args, None, Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
