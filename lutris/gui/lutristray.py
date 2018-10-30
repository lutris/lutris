"""Module for the tray icon"""
from gi.repository import Gtk

from lutris import runners
from lutris import pga
from lutris.gui.widgets.utils import get_runner_icon


class LutrisTray(Gtk.StatusIcon):
    """Lutris tray icon"""
    def __init__(self, application, **_kwargs):
        super().__init__()
        self.set_tooltip_text('Lutris')
        self.set_visible(True)
        self.application = application
        self.set_from_icon_name('lutris')

        self.installed_runners = None
        self.active_platforms = None
        self.menu = None

        self.load_menu()

        self.connect('activate', self.on_activate)
        self.connect('popup-menu', self.on_menu_popup)

    def load_menu(self):
        """Instanciates the menu attached to the tray icon"""
        self.menu = Gtk.Menu()
        self.add_runners()
        self.menu.append(Gtk.SeparatorMenuItem())
        self.add_platforms()
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

    def add_runners(self):
        """?"""
        self.installed_runners = runners.get_installed()
        for runner in self.installed_runners:
            menu_item = Gtk.ImageMenuItem()
            menu_item.set_label(runner.human_name)
            runner_icon = get_runner_icon(runner.name, format='pixbuf', size=(16, 16))
            menu_item.set_image(Gtk.Image.new_from_pixbuf(runner_icon))
            menu_item.connect('activate', self.on_runner_selected, runner.name)
            self.menu.append(menu_item)

    def add_platforms(self):
        """?"""
        self.active_platforms = pga.get_used_platforms()
        for platform in self.active_platforms:
            menu_item = Gtk.MenuItem()
            menu_item.set_label(platform)
            menu_item.connect('activate', self.on_platform_selected, platform)
            self.menu.append(menu_item)

    def on_runner_selected(self, _widget, *data):
        """?"""
        selected_runner = data[0]
        self.application.window.set_selected_filter(selected_runner, None)
        self.application.window.present()

    def on_platform_selected(self, _widget, *data):
        """?"""
        selected_platform = data[0]
        self.application.window.set_selected_filter(None, selected_platform)
        self.application.window.present()
