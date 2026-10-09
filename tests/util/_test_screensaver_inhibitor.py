"""Tests for picking the D-Bus screensaver interface used to inhibit the
screensaver while a game runs."""

from unittest import TestCase
from unittest.mock import patch

from lutris.util import display
from lutris.util.display import DesktopEnvironment


class _FakeProxy:
    """Stands in for a Gio.DBusProxy; 'owner' is None when no running service
    owns the bus name, as for org.xfce.ScreenSaver on XFCE with light-locker."""

    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def get_name_owner(self):
        return self.owner


class _FakeProxyFactory:
    """Stands in for Gio.DBusProxy.new_for_bus_sync(); 'owners' maps each bus
    name to its unique owner name, or None if the name is not owned."""

    def __init__(self, owners):
        self.owners = owners

    def __call__(self, bus_type, flags, info, name, path, interface, cancellable):
        return _FakeProxy(name, self.owners[name])


class TestGetSuspendInhibitor(TestCase):
    def get_inhibitor(self, desktop_environment, owners):
        with (
            patch.object(display, "get_desktop_environment", return_value=desktop_environment),
            patch.object(display.Gio.DBusProxy, "new_for_bus_sync", _FakeProxyFactory(owners)),
        ):
            return display._get_suspend_inhibitor()

    def test_xfce_skips_unowned_xfce_interface(self):
        inhibitor = self.get_inhibitor(
            DesktopEnvironment.XFCE,
            {"org.xfce.ScreenSaver": None, "org.freedesktop.ScreenSaver": ":1.36"},
        )
        self.assertEqual(inhibitor.proxy.name, "org.freedesktop.ScreenSaver")

    def test_xfce_prefers_owned_xfce_interface(self):
        inhibitor = self.get_inhibitor(
            DesktopEnvironment.XFCE,
            {"org.xfce.ScreenSaver": ":1.20", "org.freedesktop.ScreenSaver": ":1.36"},
        )
        self.assertEqual(inhibitor.proxy.name, "org.xfce.ScreenSaver")

    def test_no_owned_interface_falls_back_to_gtk(self):
        inhibitor = self.get_inhibitor(
            DesktopEnvironment.XFCE,
            {"org.xfce.ScreenSaver": None, "org.freedesktop.ScreenSaver": None},
        )
        self.assertIsNone(inhibitor.proxy)
