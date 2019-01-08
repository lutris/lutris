"""Module for the tray icon"""
from gi.repository import Gtk

from lutris import pga
from lutris.gui.widgets.utils import get_pixbuf_for_game


class LutrisTray(Gtk.StatusIcon):
    """Lutris tray icon"""

    def __init__(self, application, **_kwargs):
        super().__init__()
        self.set_tooltip_text("Lutris")
        self.set_visible(True)
        self.application = application
        self.set_from_icon_name("lutris")

        self.menu = None

        self.load_menu()

        self.connect("activate", self.on_activate)
        self.connect("popup-menu", self.on_menu_popup)

    def load_menu(self):
        """Instanciates the menu attached to the tray icon"""
        self.menu = Gtk.Menu()
        self.add_games()
        self.menu.append(Gtk.SeparatorMenuItem())

        quit_menu = Gtk.MenuItem()
        quit_menu.set_label("Quit")
        quit_menu.connect("activate", self.on_quit_application)
        self.menu.append(quit_menu)
        self.menu.show_all()

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
        menu_item = Gtk.ImageMenuItem()
        menu_item.set_label(game["name"])
        game_icon = get_pixbuf_for_game(game["slug"], "icon_small")
        menu_item.set_image(Gtk.Image.new_from_pixbuf(game_icon))
        menu_item.connect("activate", self.on_game_selected, game["id"])
        return menu_item

    def add_games(self):
        """Adds installed games in order of last use"""
        number_of_games_in_menu = 10
        installed_games = pga.get_games(filter_installed=True)
        installed_games.sort(
            key=lambda game: max(game["lastplayed"] or 0, game["installed_at"] or 0),
            reverse=True,
        )
        for game in installed_games[:number_of_games_in_menu]:
            self.menu.append(self._make_menu_item_for_game(game))

    def on_game_selected(self, _widget, game_id):
        self.application.launch(game_id)
