from gi.repository import Gio, GLib, GObject

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"


class Portal(GObject.Object):

    _dbus_proxy = None
    portal_interface = NotImplemented
    setting_namespace = NotImplemented
    setting_name = NotImplemented

    def __init__(self):
        super().__init__()

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

    def _read_portal_setting(self) -> None:
        if not self._dbus_proxy:
            return

        variant = GLib.Variant.new_tuple(
            GLib.Variant.new_string(self.setting_namespace),
            GLib.Variant.new_string(self.setting_name),
        )
        self._dbus_proxy.call(
            "Read",
            variant,
            Gio.DBusCallFlags.NONE,
            GObject.G_MAXINT,
            None,
            self._call_cb,
        )

    def store_result(self, result):
        raise NotImplementedError

    def _on_settings_changed(self):
        raise NotImplementedError

    def _read_value(self, value):
        raise NotImplementedError

    def _new_for_bus_cb(self, obj, result):
        proxy = obj.new_for_bus_finish(result)
        if proxy:
            proxy.connect("g-signal", self._on_settings_changed)
            self._dbus_proxy = proxy
            self._read_portal_setting()
        else:
            raise RuntimeError("Could not start GDBusProxy")

    def _call_cb(self, obj, result):
        values = obj.call_finish(result)
        if values:
            value = values[0]
            result = self._read_value(value)
            self.store_result(result)
        else:
            raise RuntimeError("Could not read %s" % self.setting_name)


class TrashPortal(GObject.Object):

    portal_interface = "org.freedesktop.portal.Trash"
    _dbus_proxy = None

    def __init__(self):
        super().__init__()

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
            print("Proxy", proxy)
            self._dbus_proxy = proxy
            self.trash_file("/home/strider/bliblu")
        else:
            raise RuntimeError("Could not start GDBusProxy")

    def _on_settings_changed(self, _proxy, _sender_name, signal_name, params):
        print(_proxy)
        print(_sender_name)
        print(signal_name)

    def trash_file(self, file_path):
        if not self._dbus_proxy:
            return

        variant = GLib.Variant.new_string(file_path)
        self._dbus_proxy.call(
            "TrashFile",
            variant,
            Gio.DBusCallFlags.NONE,
            GObject.G_MAXINT,
            None,
            self._call_cb,
        )

    def _call_cb(self, data):
        print(data)

    def store_result(self, result):
        self.result = result
