"""AppIndicator based tray icon"""
from gettext import gettext as _

import gi
from gi.repository import Gdk, Gtk

from lutris.database.games import get_games
from lutris.game import Game
from lutris.util import cache_single

try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

    APP_INDICATOR_SUPPORTED = True
except (ImportError, ValueError):
    APP_INDICATOR_SUPPORTED = False


@cache_single
def supports_status_icon():
    if APP_INDICATOR_SUPPORTED:
        return True

    display = Gdk.Display.get_default()
    return "x11" in type(display).__name__.casefold()


class LutrisStatusIcon:
    """This is a proxy for the status icon, which can be an AppIndicator or a Gtk.StatusIcon. Or if
    neither is supported, it can be a null object that silently does nothing."""

    def __init__(self, application):
        self.application = application
        self.indicator = None
        self.tray_icon = None
        self.menu = None
        self.present_menu = None

        if supports_status_icon():
            self.menu = self._get_menu()
            if APP_INDICATOR_SUPPORTED:
                self.indicator = AppIndicator.Indicator.new(
                    "net.lutris.Lutris", "lutris", AppIndicator.IndicatorCategory.APPLICATION_STATUS
                )
                self.indicator.set_menu(self.menu)
            else:
                self.tray_icon = self._get_tray_icon()
                self.tray_icon.connect("activate", self.on_activate)
                self.tray_icon.connect("popup-menu", self.on_menu_popup)

            self.set_visible(True)

    def is_visible(self):
        """Whether the icon is visible"""
        if self.indicator:
            return self.indicator.get_status() != AppIndicator.IndicatorStatus.PASSIVE

        if self.tray_icon:
            return self.tray_icon.get_visible()

        return False

    def set_visible(self, value):
        """Set the visibility of the icon"""
        if self.indicator:
            if value:
                visible = AppIndicator.IndicatorStatus.ACTIVE
            else:
                visible = AppIndicator.IndicatorStatus.PASSIVE
            self.indicator.set_status(visible)
        elif self.tray_icon:
            self.tray_icon.set_visible(value)

    def _get_menu(self):
        """Instantiates the menu attached to the tray icon"""
        menu = Gtk.Menu()
        installed_games = self._get_installed_games()
        number_of_games_in_menu = 10
        for game in installed_games[:number_of_games_in_menu]:
            menu.append(self._make_menu_item_for_game(game))
        menu.append(Gtk.SeparatorMenuItem())

        self.present_menu = Gtk.ImageMenuItem()
        self.present_menu.set_image(Gtk.Image.new_from_icon_name("lutris", Gtk.IconSize.MENU))
        self.present_menu.set_label(_("Show Lutris"))
        self.present_menu.connect("activate", self.on_activate)
        menu.append(self.present_menu)

        quit_menu = Gtk.MenuItem()
        quit_menu.set_label(_("Quit"))
        quit_menu.connect("activate", self.on_quit_application)
        menu.append(quit_menu)
        menu.show_all()
        return menu

    def _get_tray_icon(self):
        tray_icon = Gtk.StatusIcon()
        tray_icon.set_tooltip_text(_("Lutris"))
        tray_icon.set_visible(True)
        tray_icon.set_from_icon_name("lutris")
        return tray_icon

    def update_present_menu(self):
        app_window = self.application.window
        if app_window and self.present_menu:
            if app_window.get_visible():
                self.present_menu.set_label(_("Hide Lutris"))
            else:
                self.present_menu.set_label(_("Show Lutris"))

    def on_activate(self, _status_icon, _event=None):
        """Callback to show or hide the window"""
        app_window = self.application.window
        if app_window.get_visible():
            # If the window has any transients, hiding it will hide them too
            # never to be shown again, which is broken. So we don't allow that.
            windows = Gtk.Window.list_toplevels()
            for w in windows:
                if w.get_visible() and w.get_transient_for() == app_window:
                    return

            app_window.hide()
        else:
            app_window.show()

    def on_menu_popup(self, _status_icon, button, time):
        """Callback to show the contextual menu"""
        self.menu.popup(None, None, None, None, button, time)

    def on_quit_application(self, _widget):
        """Callback to quit the program"""
        self.application.quit()

    def _make_menu_item_for_game(self, game):
        menu_item = Gtk.MenuItem()
        menu_item.set_label(game["name"])
        menu_item.connect("activate", self.on_game_selected, game["id"])
        return menu_item

    @staticmethod
    def _get_installed_games():
        """Adds installed games in order of last use"""
        installed_games = get_games(filters={"installed": 1})
        installed_games.sort(
            key=lambda game: max(game["lastplayed"] or 0, game["installed_at"] or 0),
            reverse=True,
        )
        return installed_games

    def on_game_selected(self, _widget, game_id):
        launch_ui_delegate = self.application.get_launch_ui_delegate()
        Game(game_id).launch(launch_ui_delegate)
