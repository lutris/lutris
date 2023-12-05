import os

from gi.repository import Gio, GLib, GObject

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"


class TrashPortal(GObject.Object):
    portal_interface = "org.freedesktop.portal.Trash"
    _dbus_proxy = None

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            PORTAL_BUS_NAME,
            PORTAL_OBJECT_PATH,
            self.portal_interface,
            None,
            self._new_for_bus_cb,
        )
        self.result = None

    def _new_for_bus_cb(self, obj, result):
        proxy = obj.new_for_bus_finish(result)
        if proxy:
            self._dbus_proxy = proxy
            self.trash_file()

    def trash_file(self):
        file_handle = os.open(self.file_path, os.O_RDONLY)
        fds_in = Gio.UnixFDList.new()
        fds_in.append(file_handle)
        self._dbus_proxy.call_with_unix_fd_list(
            "TrashFile",
            GLib.Variant.new_tuple(
                GLib.Variant.new_handle(0),
            ),
            Gio.DBusCallFlags.NONE,
            GObject.G_MAXINT,
            fds_in,
            None,
            self._call_cb
        )

    def _call_cb(self, obj, result):
        values = obj.call_finish(result)
        if values:
            self.result = values[0]

    def store_result(self, result):
        self.result = result
