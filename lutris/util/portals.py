import os
from gettext import gettext as _
from typing import Callable, Iterable

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

    def __init__(
        self,
        file_paths: Iterable[str],
        completion_function: CompletionFunction = None,
        error_function: ErrorFunction = None,
    ):
        super().__init__()
        self.file_paths = list(file_paths)
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
            fds_in = Gio.UnixFDList.new()

            for file_path in self.file_paths:
                flags = os.O_RDONLY | os.O_PATH | os.O_CLOEXEC
                # You'd think you could use O_NOFOLLOW for any file, but
                # I find TrashFile fails. We don't want to trash the link target
                # in any case.
                if os.path.islink(file_path):
                    flags |= os.O_NOFOLLOW
                file_handle = os.open(file_path, flags)
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
                self._call_cb,
            )
        except Exception as ex:
            self.report_error(ex)

    def _call_cb(self, obj, result):
        values = obj.call_finish(result)
        if values:
            result = values[0]
            if result == 0:
                if len(self.file_paths) == 1:
                    message = (
                        _("'%s' could not be moved to the trash. You will need to delete it yourself.")
                        % self.file_paths[0]
                    )
                else:
                    message = _(
                        "The items could not be moved to the trash. You will need to delete them yourself:\n%s"
                    ) % "\n".join(self.file_paths)
                self.report_error(RuntimeError(message))
                return
        self.report_completion()

    def report_error(self, error: Exception) -> None:
        if self.error_function:
            schedule_at_idle(self.error_function, error)
        else:
            logger.exception("Failed to trash %s: %s", ", ".join(self.file_paths), error)

    def report_completion(self):
        if self.completion_function:
            schedule_at_idle(self.completion_function)
