"""Module for the tray icon"""
from gi.repository import Gtk

from lutris.gui import dialogs
from lutris import runners
from lutris import pga
from lutris.gui.widgets.utils import get_runner_icon


class LutrisTray(Gtk.StatusIcon):
    """Lutris tray icon"""
    def __init__(self, application, **kwargs):
        super().__init__()
        self.set_tooltip_text('Lutris')
        self.set_visible(True)
        self.application = application
        self.set_from_icon_name('lutris')

        self.installed_runners = None
        self.active_platforms = None
        self.menu = None

        self.load_menu()

        self.connect('activate', self.on_left_click)
        self.connect('popup-menu', self.on_right_click)

    def load_menu(self):
        self.menu = Gtk.Menu()

        self.menu.append(Gtk.SeparatorMenuItem())
        self.add_runners()
        self.menu.append(Gtk.SeparatorMenuItem())
        self.add_platforms()
        self.menu.append(Gtk.SeparatorMenuItem())

        quit = Gtk.MenuItem()
        quit.set_label("Quit")
        quit.connect("activate", self.quit_application)
        self.menu.append(quit)

        self.menu.show_all()

    def on_left_click(self, widget, event=None):
        if self.application.window.is_active():
            self.application.window.iconify()
        else:
            self.application.window.present()

    def on_right_click(self, status, button, time):
        self.menu.popup(None, None, None, None, button, time)

    def show_about_dialog(self, widget):
        dialogs.AboutDialog(parent=self.application.window)

    def quit_application(self, widget):
        self.application.do_shutdown()

    def add_runners(self):
        self.installed_runners = runners.get_installed()
        for runner in self.installed_runners:
            menu_item = Gtk.ImageMenuItem()
            menu_item.set_label(runner.human_name)
            menu_item.set_image(Gtk.Image.new_from_pixbuf(get_runner_icon(runner.name, format='pixbuf', size=(16, 16))))
            menu_item.connect('activate', self.on_runner_selected, runner.name)
            self.menu.append(menu_item)

    def add_platforms(self):
        self.active_platforms = pga.get_used_platforms()
        for platform in self.active_platforms:
            menu_item = Gtk.MenuItem()
            menu_item.set_label(platform)
            menu_item.connect('activate', self.on_platform_selected, platform)
            self.menu.append(menu_item)

    def on_runner_selected(self, widget, *data):
        selected_runner = data[0]
        self.application.window.set_selected_filter(selected_runner, None)
        self.application.window.present()

    def on_platform_selected(self, widget, *data):
        selected_platform = data[0]
        self.application.window.set_selected_filter(None, selected_platform)
        self.application.window.present()
