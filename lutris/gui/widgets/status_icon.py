"""AppIndicator based tray icon"""
from gettext import gettext as _

import gi
from gi.repository import Gtk

from lutris.database.games import get_games
from lutris.game import Game

try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as AppIndicator
    APP_INDICATOR_SUPPORTED = True
except (ImportError, ValueError):
    APP_INDICATOR_SUPPORTED = False


class LutrisStatusIcon:

    def __init__(self, application):
        self.application = application
        self.icon = self.create()
        self.menu = self.get_menu()
        self.set_visible(True)
        if APP_INDICATOR_SUPPORTED:
            self.icon.set_menu(self.menu)
        else:
            self.icon.connect("activate", self.on_activate)
            self.icon.connect("popup-menu", self.on_menu_popup)

    def create(self):
        """Create an appindicator"""
        if APP_INDICATOR_SUPPORTED:
            return AppIndicator.Indicator.new(
                "net.lutris.Lutris", "lutris", AppIndicator.IndicatorCategory.APPLICATION_STATUS
            )
        return LutrisTray(self.application)

    def is_visible(self):
        """Whether the icon is visible"""
        if APP_INDICATOR_SUPPORTED:
            return self.icon.get_status() != AppIndicator.IndicatorStatus.PASSIVE
        return self.icon.is_visible()

    def set_visible(self, value):
        """Set the visibility of the icon"""
        if APP_INDICATOR_SUPPORTED:
            if value:
                visible = AppIndicator.IndicatorStatus.ACTIVE
            else:
                visible = AppIndicator.IndicatorStatus.ACTIVE
            self.icon.set_status(visible)
        else:
            self.icon.set_visible(value)

    def get_menu(self):
        """Instanciates the menu attached to the tray icon"""
        menu = Gtk.Menu()
        installed_games = self.add_games()
        number_of_games_in_menu = 10
        for game in installed_games[:number_of_games_in_menu]:
            menu.append(self._make_menu_item_for_game(game))
        menu.append(Gtk.SeparatorMenuItem())

        present_menu = Gtk.ImageMenuItem()
        present_menu.set_image(Gtk.Image.new_from_icon_name("lutris", Gtk.IconSize.MENU))
        present_menu.set_label(_("Show Lutris"))
        present_menu.connect("activate", self.on_activate)
        menu.append(present_menu)

        quit_menu = Gtk.MenuItem()
        quit_menu.set_label(_("Quit"))
        quit_menu.connect("activate", self.on_quit_application)
        menu.append(quit_menu)
        menu.show_all()
        return menu

    def on_activate(self, _status_icon, _event=None):
        """Callback to show or hide the window"""
        self.application.window.present()

    def on_menu_popup(self, _status_icon, button, time):
        """Callback to show the contextual menu"""
        self.menu.popup(None, None, None, None, button, time)

    def on_quit_application(self, _widget):
        """Callback to quit the program"""
        self.application.do_shutdown()

    def _make_menu_item_for_game(self, game):
        menu_item = Gtk.MenuItem()
        menu_item.set_label(game["name"])
        menu_item.connect("activate", self.on_game_selected, game["id"])
        return menu_item

    @staticmethod
    def add_games():
        """Adds installed games in order of last use"""
        installed_games = get_games(filters={"installed": 1})
        installed_games.sort(
            key=lambda game: max(game["lastplayed"] or 0, game["installed_at"] or 0),
            reverse=True,
        )
        return installed_games

    def on_game_selected(self, _widget, game_id):
        Game(game_id).launch()


class LutrisTray(Gtk.StatusIcon):

    """Lutris tray icon"""

    def __init__(self, application, **_kwargs):
        super().__init__()
        self.set_tooltip_text(_("Lutris"))
        self.set_visible(True)
        self.application = application
        self.set_from_icon_name("lutris")
