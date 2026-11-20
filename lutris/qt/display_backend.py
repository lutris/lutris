"""The Qt frontend's DisplayBackend (lutris.util.display_backend): what Qt knows
about the screen."""

from PySide6.QtGui import QGuiApplication

from lutris.util.display_backend import DisplayManager


class QtDisplayBackend:
    """Answers from Qt's platform plugin and screens. Qt has no way to keep the computer
    awake, and reads no display modes itself, so those are left to D-Bus and xrandr."""

    def is_x11(self) -> bool:
        return QGuiApplication.platformName() == "xcb"

    def get_scale_factor(self) -> int:
        screen = QGuiApplication.primaryScreen()
        return max(1, round(screen.devicePixelRatio())) if screen else 1

    def get_display_manager(self) -> DisplayManager | None:
        return None

    def inhibit_suspend(self, reason: str) -> int | None:
        return None

    def uninhibit_suspend(self, cookie: int) -> None:
        pass
