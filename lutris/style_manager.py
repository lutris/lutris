import enum

from gi.repository import Gio, GLib, GObject, Gtk

from lutris import settings
from lutris.util.log import logger

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SETTINGS_INTERFACE = "org.freedesktop.portal.Settings"


class ColorScheme(enum.Enum):

    NO_PREFERENCE = 0  # Default
    PREFER_DARK = 1
    PREFER_LIGHT = 2


class StyleManager(GObject.Object):
    """Manages the color scheme of the app.

    Has a single readable GObject property `is_dark` telling whether the app is
    in dark mode, it is set to True, when either the user preference on the
    preferences panel or in the a system is set to prefer dark mode.
    """

    _color_scheme = ColorScheme.NO_PREFERENCE
    _dbus_proxy = None
    _is_config_dark = False
    _is_dark = False
    _is_system_dark = False

    def __init__(self):
        super().__init__()

        self.gtksettings = Gtk.Settings.get_default()
        self.is_config_dark = settings.read_setting("dark_theme", default="false").lower() == "true"

        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            PORTAL_BUS_NAME,
            PORTAL_OBJECT_PATH,
            PORTAL_SETTINGS_INTERFACE,
            None,
            self._new_for_bus_cb,
        )

    def _read_portal_setting(self) -> None:
        if not self._dbus_proxy:
            return

        variant = GLib.Variant.new_tuple(
            GLib.Variant.new_string("org.freedesktop.appearance"),
            GLib.Variant.new_string("color-scheme"),
        )
        self._dbus_proxy.call(
            "Read",
            variant,
            Gio.DBusCallFlags.NONE,
            GObject.G_MAXINT,
            None,
            self._call_cb,
        )

    def _new_for_bus_cb(self, obj, result):
        try:
            proxy = obj.new_for_bus_finish(result)
            if proxy:
                proxy.connect("g-signal", self._on_settings_changed)
                self._dbus_proxy = proxy
                self._read_portal_setting()
            else:
                raise Exception("Could not start GDBusProxy")

        except Exception as err:
            logger.error("Unable to start Settings portal: %s", err)

    def _call_cb(self, obj, result):
        try:
            values = obj.call_finish(result)
            if values:
                value = values[0]
                self.color_scheme = self._read_value(value)
            else:
                raise Exception("Could not read color-scheme")
        except Exception:
            pass

    def _on_settings_changed(self, _proxy, _sender_name, signal_name, params):
        if signal_name != "SettingChanged":
            return

        namespace, name, value = params

        if namespace == "org.freedesktop.appearance" and name == "color-scheme":
            self.color_scheme = self._read_value(value)

    def _read_value(self, value: int) -> ColorScheme:
        if value == 1:
            return ColorScheme.PREFER_DARK

        if value == 2:
            return ColorScheme.PREFER_LIGHT

        return ColorScheme.NO_PREFERENCE

    @property
    def is_system_dark(self) -> bool:
        return self._is_system_dark

    @is_system_dark.setter  # type: ignore
    def is_system_dark(self, is_system_dark: bool) -> None:
        if self._is_system_dark == is_system_dark:
            return

        self._is_system_dark = is_system_dark
        self._set_is_dark(self._is_config_dark or is_system_dark)

    @property
    def is_config_dark(self) -> bool:
        return self._is_config_dark

    @is_config_dark.setter  # type: ignore
    def is_config_dark(self, is_config_dark: bool) -> None:
        if self._is_config_dark == is_config_dark:
            return

        self._is_config_dark = is_config_dark
        self._set_is_dark(is_config_dark or self._is_system_dark)

    @GObject.Property(type=bool, default=False, flags=GObject.ParamFlags.READABLE)
    def is_dark(self) -> bool:
        return self._is_dark

    def _set_is_dark(self, is_dark: bool) -> None:
        if self._is_dark == is_dark:
            return

        self._is_dark = is_dark
        self.notify("is-dark")

        self.gtksettings.set_property(
            "gtk-application-prefer-dark-theme", is_dark
        )

    @property
    def color_scheme(self) -> ColorScheme:
        return self._color_scheme

    @color_scheme.setter  # type: ignore
    def color_scheme(self, color_scheme: ColorScheme) -> None:
        if self._color_scheme == color_scheme:
            return

        self._color_scheme = color_scheme

        self.is_system_dark = self.color_scheme == ColorScheme.PREFER_DARK
