"""lutris.util.display asks the installed DisplayBackend what only a UI toolkit knows."""

import pytest

from lutris.util import display, display_backend
from lutris.util.display_backend import EnvironmentDisplayBackend, get_display_backend, set_display_backend


class FakeDisplayManager:
    def get_display_names(self) -> list[str]:
        return ["Fake"]

    def get_resolutions(self) -> list[str]:
        return ["640x480"]

    def get_current_resolution(self) -> tuple[str, str]:
        return "640", "480"

    def set_resolution(self, resolution: object) -> None:
        pass

    def get_config(self) -> list[object]:
        return []


class FakeDisplayBackend(EnvironmentDisplayBackend):
    def __init__(self) -> None:
        self.display_manager = FakeDisplayManager()
        self.inhibited: list[int] = []

    def is_x11(self) -> bool:
        return True

    def get_scale_factor(self) -> int:
        return 2

    def get_display_manager(self) -> FakeDisplayManager:
        return self.display_manager

    def inhibit_suspend(self, reason: str) -> int | None:
        self.inhibited.append(7)
        return 7

    def uninhibit_suspend(self, cookie: int) -> None:
        self.inhibited.remove(cookie)


@pytest.fixture
def backend(monkeypatch):
    """Install a FakeDisplayBackend for the test, with Mutter unavailable."""
    monkeypatch.setattr(display_backend, "_display_backend", None)
    monkeypatch.setattr(display, "_display_manager", None)
    monkeypatch.setattr(display, "DBUS_AVAILABLE", False)
    fake = FakeDisplayBackend()
    set_display_backend(fake)
    return fake


def test_default_backend_needs_no_toolkit(monkeypatch):
    monkeypatch.setattr(display_backend, "_display_backend", None)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    assert isinstance(get_display_backend(), EnvironmentDisplayBackend)
    assert not display.is_display_x11()
    monkeypatch.delenv("WAYLAND_DISPLAY")
    assert display.is_display_x11()
    assert display.get_default_dpi() == 96


def test_display_questions_go_to_the_backend(backend):
    assert display.is_display_x11()
    assert display.get_default_dpi() == 192
    assert display.get_display_manager() is backend.display_manager


def test_display_manager_follows_the_installed_backend(backend, monkeypatch):
    first = display.get_display_manager()
    assert display.get_display_manager() is first  # Created once

    monkeypatch.setattr(display, "LegacyDisplayManager", FakeDisplayManager)
    set_display_backend(EnvironmentDisplayBackend())
    assert display.get_display_manager() is not first


def test_inhibitor_without_d_bus_asks_the_backend(backend):
    inhibitor = display.DBusScreenSaverInhibitor()

    cookie = inhibitor.inhibit("Some Game")
    assert cookie == 7
    assert backend.inhibited == [7]

    inhibitor.uninhibit(cookie)
    assert backend.inhibited == []
