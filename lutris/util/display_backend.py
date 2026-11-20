"""What Lutris learns about the displays from the frontend's toolkit, behind a small interface.

Some of what the core needs to know about the screen is best answered by the UI
toolkit: which windowing system it's connected to, the primary monitor's scale,
and how to keep the computer awake when nothing on D-Bus will. The frontend
installs a DisplayBackend with set_display_backend() before it starts (the GTK
frontend's is lutris.gui.display_backend); without one, the core works these out
from the environment, and reads display modes with xrandr.
"""

import os
from typing import Any, Protocol

from lutris.util.log import logger


class DisplayManager(Protocol):
    """Lists and changes display modes; lutris.util.display picks one of these."""

    def get_display_names(self) -> list[str]:
        """Return the names of the connected displays."""
        ...

    def get_resolutions(self) -> list[str]:
        """Return the available resolutions, as "<width>x<height>", largest first."""
        ...

    def get_current_resolution(self) -> tuple[str, str]:
        """Return the width and height of the primary display."""
        ...

    def set_resolution(self, resolution: Any) -> None:
        """Set the primary display to a "<width>x<height>" resolution, or every display
        to a configuration get_config() returned."""
        ...

    def get_config(self) -> Any:
        """Return the current configuration of the displays, for set_resolution()."""
        ...


class DisplayBackend(Protocol):
    """What Lutris needs to know about the displays from a UI toolkit."""

    def is_x11(self) -> bool:
        """True if the frontend runs on X11 (not Wayland)."""
        ...

    def get_scale_factor(self) -> int:
        """Return the primary monitor's scale factor (2 on a HiDPI screen)."""
        ...

    def get_display_manager(self) -> DisplayManager | None:
        """Return the toolkit's own DisplayManager, or None to use xrandr. Lutris prefers
        Mutter's D-Bus interface to either when it's there."""
        ...

    def inhibit_suspend(self, reason: str) -> int | None:
        """Keep the computer awake, when no screen saver D-Bus interface can; returns a
        cookie for uninhibit_suspend(), or None if it can't."""
        ...

    def uninhibit_suspend(self, cookie: int) -> None:
        """Let the computer sleep again after inhibit_suspend()."""
        ...


class EnvironmentDisplayBackend:
    """Needs no UI toolkit: it reads the session from the environment, uses xrandr
    and can't keep the computer awake itself."""

    def is_x11(self) -> bool:
        # Toolkits use Wayland when they can
        return bool(os.environ.get("DISPLAY")) and not os.environ.get("WAYLAND_DISPLAY")

    def get_scale_factor(self) -> int:
        return 1

    def get_display_manager(self) -> DisplayManager | None:
        return None

    def inhibit_suspend(self, reason: str) -> int | None:
        logger.debug("No screen saver D-Bus interface to keep the computer awake with")
        return None

    def uninhibit_suspend(self, cookie: int) -> None:
        pass


_display_backend: DisplayBackend | None = None


def get_display_backend() -> DisplayBackend:
    """Return the installed DisplayBackend, or one that needs no toolkit if there's none."""
    global _display_backend
    if _display_backend is None:
        _display_backend = EnvironmentDisplayBackend()
    return _display_backend


def set_display_backend(backend: DisplayBackend) -> None:
    """Install the frontend's DisplayBackend; do this before it starts."""
    global _display_backend
    _display_backend = backend
