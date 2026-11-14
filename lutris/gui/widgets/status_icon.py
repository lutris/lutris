"""Tray icon, implemented with the StatusNotifierItem and DBusMenu D-Bus protocols.

GTK 4 has no status icon, and the AppIndicator libraries that provide one require GTK 3. But
those are wrappers over these two protocols, which need only D-Bus: we export one object that
describes the icon, and another that describes its menu, and tell the desktop's 'watcher'
where to find them. The desktop draws both; we are told when something is clicked."""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from gettext import gettext as _
from typing import TYPE_CHECKING, Any

from gi.repository import Gio, GLib

from lutris.database import categories
from lutris.database.games import get_games
from lutris.game import Game
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.gui.application import LutrisApplication

WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
ICON_NAME = "net.lutris.Lutris"
GAMES_IN_MENU = 10

INTERFACES = Gio.DBusNodeInfo.new_for_xml("""
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
    <signal name="NewStatus"><arg type="s"/></signal>
  </interface>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
      <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
    <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
    <method name="AboutToShowGroup">
      <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
    </method>
    <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  </interface>
</node>
""")


@dataclass
class MenuItem:
    """An item in the status icon's menu; with no callback, it is a separator."""

    label: str = ""
    # Not compared, so that we can tell if the menu the desktop has seen is out of date.
    callback: Callable[[], None] | None = field(default=None, compare=False)


def supports_status_icon() -> bool:
    """True if the desktop has somewhere to show a status icon. GNOME needs an extension for this."""
    try:
        result = Gio.bus_get_sync(Gio.BusType.SESSION).call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", (WATCHER_NAME,)),
            GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE,
            -1,
        )
        return bool(result.unpack()[0])
    except GLib.Error:
        logger.exception("Unable to check for a status icon host")
        return False


class LutrisStatusIcon:
    """The Lutris tray icon and its menu. If the desktop can't show one, this does nothing."""

    def __init__(self, application: "LutrisApplication") -> None:
        self.application = application
        self.connection: Gio.DBusConnection = application.get_dbus_connection()
        self.status = "Active"
        self.registered = False
        self.menu_revision = 0
        # An item's ID is its index here plus one, as 0 is the menu itself.
        self.menu_items: list[MenuItem] = []

        if self.connection:
            item, menu = INTERFACES.interfaces
            self.connection.register_object(ITEM_PATH, item, self._on_item_call, self._get_item_property)
            self.connection.register_object(MENU_PATH, menu, self._on_menu_call, self._get_menu_property)
            self._update_menu()
            # The watcher comes and goes with the desktop shell, and we must register with each
            # new one. We register now too, so we know at once if the icon will be shown.
            self._register()
            Gio.bus_watch_name_on_connection(
                self.connection,
                WATCHER_NAME,
                Gio.BusNameWatcherFlags.NONE,
                lambda *_args: self._register(),
                lambda *_args: setattr(self, "registered", False),
            )

    def _register(self) -> None:
        if not self.registered:
            try:
                self.connection.call_sync(
                    WATCHER_NAME,
                    WATCHER_PATH,
                    WATCHER_NAME,
                    "RegisterStatusNotifierItem",
                    GLib.Variant("(s)", (ITEM_PATH,)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    -1,
                )
                self.registered = True
            except GLib.Error as ex:
                logger.debug("No status icon host to register with: %s", ex.message)

    def is_visible(self) -> bool:
        """Whether the icon is visible"""
        return self.registered and self.status == "Active"

    def set_visible(self, value: bool) -> None:
        """Set the visibility of the icon"""
        status = "Active" if value else "Passive"
        if self.connection and status != self.status:
            self.status = status
            self.connection.emit_signal(
                None, ITEM_PATH, "org.kde.StatusNotifierItem", "NewStatus", GLib.Variant("(s)", (status,))
            )

    def update_present_menu(self) -> None:
        if self.connection:
            self._update_menu()

    # The icon

    def _get_item_property(self, _connection, _sender, _path, _interface, name: str) -> GLib.Variant:
        if name == "Category":
            return GLib.Variant("s", "ApplicationStatus")
        if name == "Id":
            return GLib.Variant("s", ICON_NAME)
        if name == "Title":
            return GLib.Variant("s", "Lutris")
        if name == "Status":
            return GLib.Variant("s", self.status)
        if name == "IconName":
            return GLib.Variant("s", ICON_NAME)
        if name == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)", ("", [], "Lutris", ""))
        if name == "ItemIsMenu":
            return GLib.Variant("b", False)
        return GLib.Variant("o", MENU_PATH)

    def _on_item_call(self, _connection, _sender, _path, _interface, method: str, _parameters, invocation) -> None:
        invocation.return_value(None)
        if method == "Activate":
            self.on_activate()

    def on_activate(self) -> None:
        """Callback to show or hide the window"""
        app_window = self.application.window
        if not app_window:
            return
        if app_window.get_visible():
            # If the window has any transients, hiding it will hide them too
            # never to be shown again, which is broken. So we don't allow that.
            for w in self.application.get_windows():
                if w.get_visible() and w.get_transient_for() == app_window:
                    return
            app_window.set_visible(False)
        else:
            app_window.present()

    # The menu

    def _update_menu(self) -> None:
        """Rebuilds the menu, and tells the desktop if it has changed."""
        items: list[MenuItem] = []
        for game in self._get_installed_games()[:GAMES_IN_MENU]:
            # DBusMenu takes an underscore to mark a mnemonic
            items.append(MenuItem(game["name"].replace("_", "__"), partial(self.on_game_selected, game["id"])))
        items.append(MenuItem())
        app_window = self.application.window
        is_shown = bool(app_window and app_window.get_visible())
        items.append(MenuItem(_("Hide Lutris") if is_shown else _("Show Lutris"), self.on_activate))
        items.append(MenuItem(_("Quit"), self.application.quit))

        changed = items != self.menu_items
        self.menu_items = items
        if changed:
            self.menu_revision += 1
            self.connection.emit_signal(
                None,
                MENU_PATH,
                "com.canonical.dbusmenu",
                "LayoutUpdated",
                GLib.Variant("(ui)", (self.menu_revision, 0)),
            )

    def _get_menu_item_properties(self, item_id: int) -> dict[str, GLib.Variant]:
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        item = self.menu_items[item_id - 1]
        if item.callback:
            return {"label": GLib.Variant("s", item.label)}
        return {"type": GLib.Variant("s", "separator")}

    def _get_menu_property(self, _connection, _sender, _path, _interface, name: str) -> GLib.Variant:
        if name == "Version":
            return GLib.Variant("u", 3)
        if name == "TextDirection":
            return GLib.Variant("s", "ltr")
        if name == "Status":
            return GLib.Variant("s", "normal")
        return GLib.Variant("as", [])

    def _on_menu_call(self, _connection, _sender, _path, _interface, method: str, parameters, invocation) -> None:
        args: Any = parameters.unpack()
        item_ids = range(1, len(self.menu_items) + 1)
        if method == "GetLayout":
            parent_id, depth = args[0], args[1]
            children = [
                GLib.Variant("(ia{sv}av)", (i, self._get_menu_item_properties(i), []))
                for i in (item_ids if parent_id == 0 and depth != 0 else [])
            ]
            layout = (parent_id, self._get_menu_item_properties(parent_id), children)
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self.menu_revision, layout)))
        elif method == "GetGroupProperties":
            wanted = [i for i in (args[0] or item_ids) if i in item_ids]
            properties = [(i, self._get_menu_item_properties(i)) for i in wanted]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (properties,)))
        elif method == "GetProperty":
            value = self._get_menu_item_properties(args[0]).get(args[1], GLib.Variant("s", ""))
            invocation.return_value(GLib.Variant("(v)", (value,)))
        elif method == "AboutToShow":
            revision = self.menu_revision
            self._update_menu()
            invocation.return_value(GLib.Variant("(b)", (revision != self.menu_revision,)))
        elif method == "AboutToShowGroup":
            self._update_menu()
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            # We reply before we act, as a callback may run for some time.
            events = [args] if method == "Event" else args[0]
            invocation.return_value(None if method == "Event" else GLib.Variant("(ai)", ([],)))
            for item_id, event_id, _data, _timestamp in events:
                item = self.menu_items[item_id - 1] if item_id in item_ids else None
                if item and item.callback and event_id == "clicked":
                    item.callback()

    @staticmethod
    def _get_installed_games() -> list[dict[str, Any]]:
        """Returns the installed games in order of last use"""
        installed_games = get_games(filters={"installed": 1})
        hidden_game_ids = categories.get_game_ids_for_categories([".hidden"])
        installed_games = [g for g in installed_games if str(g.get("id")) not in hidden_game_ids]
        installed_games.sort(
            key=lambda game: max(game["lastplayed"] or 0, game["installed_at"] or 0),
            reverse=True,
        )
        return installed_games

    def on_game_selected(self, game_id: str) -> None:
        Game(game_id).launch(self.application.launch_ui_delegate)
