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
            logger.warning(
                "Could not connect to the Trash portal (%s); falling back to g_file_trash_async().",
                ex.message,
            )
        else:
            if proxy:
                self._dbus_proxy = proxy
            else:
                logger.warning("Could not connect to the Trash portal; falling back to g_file_trash_async().")
        self._trash_next_file()

    def _trash_next_file(self):
        """Trash the next file in the list, then re-invoked from
        _call_cb since TrashFile accepts only a single fd per call."""
        if not self.file_paths:
            self.report_completion()
            return

        file_path = self.file_paths[0]

        if self._dbus_proxy is None:
            self.file_paths.pop(0)
            self._fallback_trash(file_path)
            return

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
        failure_reason = None
        try:
            values = obj.call_with_unix_fd_list_finish(result)
        except GLib.Error as ex:
            failure_reason = ex.message
        else:
            if values and values[0][0] == 0:
                failure_reason = "portal returned failure"

        if failure_reason is not None:
            logger.warning(
                "Trash portal refused '%s' (%s); falling back to g_file_trash_async().",
                file_path,
                failure_reason,
            )
            self._fallback_trash(file_path)
        else:
            self._trash_next_file()

    def _fallback_trash(self, file_path: str) -> None:
        try:
            gfile = Gio.File.new_for_path(file_path)
            gfile.trash_async(GLib.PRIORITY_DEFAULT, None, self._fallback_cb)
        except Exception as ex:
            logger.error("Fallback trash of '%s' failed to start: %s", file_path, ex)
            self._trash_next_file()

    def _fallback_cb(self, obj, result):
        try:
            obj.trash_finish(result)
        except GLib.Error as ex:
            logger.error("Failed to trash '%s': %s", obj.get_path(), ex.message)
        self._trash_next_file()

    def report_error(self, error: Exception) -> None:
        if self.error_function:
            schedule_at_idle(self.error_function, error)
        else:
            logger.exception("Failed to trash %s: %s", ", ".join(self.file_paths), error)

    def report_completion(self):
        if self.completion_function:
            schedule_at_idle(self.completion_function)
