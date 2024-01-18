import os
from typing import Callable

from gi.repository import Gio, GLib, GObject

from lutris.util.jobs import schedule_at_idle
from lutris.util.log import logger

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"


class TrashPortal(GObject.Object):
    portal_interface = "org.freedesktop.portal.Trash"
    _dbus_proxy = None

    CompletionFunction = Callable[[], None]
    ErrorFunction = Callable[[Exception], None]

    def __init__(self, file_path: str,
                 completion_function: CompletionFunction = None,
                 error_function: ErrorFunction = None):
        super().__init__()
        self.file_path = file_path
        self.completion_function = completion_function
        self.error_function = error_function
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

    def _new_for_bus_cb(self, obj, result):
        proxy = obj.new_for_bus_finish(result)
        if proxy:
            self._dbus_proxy = proxy
            self.trash_file()

    def trash_file(self):
        try:
            flags = os.O_RDONLY | os.O_PATH | os.O_CLOEXEC
            if not os.path.isdir(self.file_path):
                flags |= os.O_NOFOLLOW
            file_handle = os.open(self.file_path, flags)
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
        except Exception as ex:
            self.report_error(ex)

    def _call_cb(self, obj, result):
        values = obj.call_finish(result)
        if values:
            result = values[0]
            if result == 0:
                self.report_error(RuntimeError("The folder could not be moved to the trash."))
                return
        self.report_completion()

    def report_error(self, error: Exception) -> None:
        if self.error_function:
            schedule_at_idle(self.error_function, error)
        else:
            logger.exception("Failed to trash folder %s: %s", self.file_path, error)

    def report_completion(self):
        if self.completion_function:
            schedule_at_idle(self.completion_function)
