import os
from collections.abc import Callable, Iterable

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
        completion_function: CompletionFunction | None = None,
        error_function: ErrorFunction | None = None,
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
        try:
            proxy = obj.new_for_bus_finish(result)
        except GLib.Error as ex:
            logger.error("Could not connect to the Trash portal: %s", ex.message)
            self.report_completion()
            return

        if proxy:
            self._dbus_proxy = proxy
            self._trash_next_file()
        else:
            logger.error("Could not connect to the Trash portal.")
            self.report_completion()

    def _trash_next_file(self):
        """Trash the next file in the list, then re-invoked from
        _call_cb since TrashFile accepts only a single fd per call."""
        if not self.file_paths:
            self.report_completion()
            return

        file_path = self.file_paths[0]
        try:
            fds_in = Gio.UnixFDList.new()
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
        file_path = self.file_paths.pop(0)
        try:
            values = obj.call_with_unix_fd_list_finish(result)
        except GLib.Error as ex:
            logger.error("Failed to trash '%s': %s", file_path, ex.message)
            self._trash_next_file()
            return

        if values:
            trash_result = values[0][0]
            if trash_result == 0:
                logger.error(
                    "'%s' could not be moved to the trash. You will need to delete it yourself.",
                    file_path,
                )

        self._trash_next_file()

    def report_error(self, error: Exception) -> None:
        if self.error_function:
            schedule_at_idle(self.error_function, error)
        else:
            logger.exception("Failed to trash %s: %s", ", ".join(self.file_paths), error)

    def report_completion(self):
        if self.completion_function:
            schedule_at_idle(self.completion_function)
