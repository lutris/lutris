"""Open writable configuration files with the desktop's default application."""

import os

from gi.repository import Gio, GLib

from lutris.util.log import logger


def open_config_file(path: str) -> None:
    """Use the writable OpenFile portal inside Flatpak, and file associations otherwise."""
    if not os.path.exists("/.flatpak-info"):
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(path).get_uri(), None)
        return

    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    descriptors = Gio.UnixFDList.new()
    with open(path, "r+b") as config_file:
        handle = descriptors.append(config_file.fileno())

    def on_opened(bus, result):
        try:
            bus.call_with_unix_fd_list_finish(result)
        except GLib.Error:
            logger.exception("Unable to open game configuration in the default application")

    connection.call_with_unix_fd_list(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.OpenURI",
        "OpenFile",
        GLib.Variant("(sha{sv})", ("", handle, {"writable": GLib.Variant("b", True)})),
        GLib.VariantType.new("(o)"),
        Gio.DBusCallFlags.NONE,
        -1,
        descriptors,
        None,
        on_opened,
    )
