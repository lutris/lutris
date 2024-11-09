from gi.repository import Gio, GLib, GObject, Gtk

from lutris import settings
from lutris.gui.widgets import NotificationSource
from lutris.util.log import logger

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SETTINGS_INTERFACE = "org.freedesktop.portal.Settings"

THEME_CHANGED = NotificationSource()


class StyleManager(GObject.Object):
    """Manages the color scheme of the app.

    Has a single readable GObject property `is_dark` telling whether the app is
    in dark mode, it is set to True, when either the user preference on the
    preferences panel or in the system is set to prefer dark mode.
    """

    _dbus_proxy = None
    _preferred_theme = "default"
    _system_theme = None
    _is_dark = False

    def __init__(self):
        super().__init__()

        self.gtksettings = Gtk.Settings.get_default()
        self.preferred_theme = settings.read_setting("preferred_theme") or "default"

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
                raise RuntimeError("Could not start GDBusProxy")
        except Exception as ex:
            logger.exception("Error setting up style change monitoring: %s", ex)

    def _call_cb(self, obj, result):
        try:
            values = obj.call_finish(result)
            if values:
                value = values[0]
                self.system_theme = self._read_value(value)
            else:
                raise RuntimeError("Could not read color-scheme")
        except Exception as ex:
            logger.exception("Error reading color-scheme: %s", ex)

    def _on_settings_changed(self, _proxy, _sender_name, signal_name, params):
        if signal_name != "SettingChanged":
            return

        namespace, name, value = params

        if namespace == "org.freedesktop.appearance" and name == "color-scheme":
            self.system_theme = self._read_value(value)

    def _read_value(self, value: int) -> str:
        if value == 1:
            return "dark"

        if value == 2:
            return "light"

        return "default"

    @property
    def is_config_dark(self) -> bool:
        """True if we override light mode to be dark; if we're
        defaulting to dark, this does nothing."""
        return self._is_config_dark

    @is_config_dark.setter  # type: ignore
    def is_config_dark(self, is_config_dark: bool) -> None:
        if self._is_config_dark == is_config_dark:
            return

        self._is_config_dark = is_config_dark
        self._update_is_dark()

    @property
    def preferred_theme(self) -> str:
        """Can be 'light' or 'dark' to override the theme, or 'default' to go with
        the system's default theme."""
        return self._preferred_theme

    @preferred_theme.setter  # type: ignore
    def preferred_theme(self, preferred_theme: str) -> None:
        if self._preferred_theme == preferred_theme:
            return

        self._preferred_theme = preferred_theme
        self._update_is_dark()

    @property
    def system_theme(self) -> str:
        return self._system_theme or "default"

    @system_theme.setter  # type: ignore
    def system_theme(self, system_theme: str) -> None:
        if self._system_theme == system_theme:
            return

        self._system_theme = system_theme
        self._update_is_dark()

    @GObject.Property(type=bool, default=False, flags=GObject.ParamFlags.READABLE)
    def is_dark(self) -> bool:
        return self._is_dark

    def _update_is_dark(self) -> None:
        if self.is_dark_by_default:
            is_dark = self.preferred_theme != "light"
        else:
            is_dark = self.preferred_theme == "dark"

        if self._is_dark == is_dark:
            return

        self._is_dark = is_dark
        self.notify("is-dark")

        self.gtksettings.set_property("gtk-application-prefer-dark-theme", is_dark)
        THEME_CHANGED.fire()

    @property
    def is_dark_by_default(self):
        return self.system_theme != "light"
