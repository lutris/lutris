import os
import gi
import signal
from concurrent.futures import ThreadPoolExecutor
from lutris.util.http import Request
from lutris.util import datapath
from lutris.services.gog import GogService

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gio

ICON_CACHE = os.path.expanduser("~/.cache/lutris/gog-cache/")


class GogWindow(Gtk.Window):
    title = "GOG Downloader"

    def __init__(self):
        super(GogWindow, self).__init__(title=self.title)

        headerbar = Gtk.HeaderBar()
        headerbar.set_title(self.title)
        headerbar.set_show_close_button(True)

        user_button = Gtk.MenuButton()
        headerbar.pack_end(user_button)
        icon = Gio.ThemedIcon(name="avatar-default-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        user_button.add(image)

        popover = Gtk.Popover.new(user_button)
        popover_box = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        login_button = Gtk.Button("Login")
        popover_box.add(login_button)
        logout_button = Gtk.Button("Logout")
        popover_box.add(logout_button)
        popover.add(popover_box)

        self.set_titlebar(headerbar)

        self.set_size_request(450, 300)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scrolled_window, True, True, 0)
        self.game_listbox = Gtk.ListBox(visible=True, selection_mode=Gtk.SelectionMode.NONE)

        scrolled_window.add(self.game_listbox)

        self.platform_icons = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.gog_service = GogService()

        self.game_list = self.gog_service.get_library()
        for game in self.game_list['products']:
            self.game_listbox.add(self.get_game_box(game))

    def get_game_box(self, game):
        hbox = Gtk.HBox()

        image = Gtk.Image()
        image.set_size_request(100, 60)
        self.get_gog_image(image, game)
        hbox.pack_start(image, False, False, 0)

        vbox = Gtk.VBox()
        hbox.pack_start(vbox, True, True, 10)

        label = Gtk.Label()
        label.set_markup("<b>{}</b>".format(game['title'].replace('&', '&amp;')))
        label.set_alignment(0, 0)
        vbox.pack_start(label, False, False, 4)

        icon_box = Gtk.HBox()
        vbox.pack_start(icon_box, False, False, 4)

        for platform in game['worksOn']:
            if game['worksOn'][platform]:
                icon_path = os.path.join(datapath.get(), 'media/platforms/{}.png'.format(platform.lower()))
                icon_box.pack_start(Gtk.Image.new_from_file(icon_path), False, False, 2)

        install_button = Gtk.Button.new_from_icon_name("browser-download", Gtk.IconSize.BUTTON)
        install_button.connect('clicked', self.on_download_clicked, game)
        install_align = Gtk.Alignment()
        install_align.set(0, 0.75, 0, 0)
        install_align.add(install_button)
        hbox.pack_end(install_align, False, False, 10)

        return hbox

    def get_gog_image(self, image, game):
        icon_path = os.path.join(ICON_CACHE, game['slug'] + '.jpg')
        if os.path.exists(icon_path):
            self.executor.submit(image.set_from_file, icon_path)
            return
        icon_url = 'http:' + game['image'] + '_100.jpg'

        self.executor.submit(self.download_icon, icon_url, icon_path, image)

    def download_icon(self, icon_url, icon_path, image):
        r = Request(icon_url)
        r.get()
        r.write_to_file(icon_path)
        image.set_from_file(icon_path)

    def on_download_clicked(self, widget, game):
        game_details = self.gog_service.get_game_details(game['id'])
        installer_liststore = Gtk.ListStore(str, str)
        for installer in game_details['downloads']['installers']:
            installer_liststore.append(
                (installer['id'], "{} ({}, {})".format(installer['name'], installer['language_full'], installer['os']))
            )

        installer_combo = Gtk.ComboBox.new_with_model(installer_liststore)
        installer_combo.connect("changed", self.on_installer_combo_changed, installer)
        renderer_text = Gtk.CellRendererText()
        installer_combo.pack_start(renderer_text, True)
        installer_combo.add_attribute(renderer_text, "text", 1)

        dialog = Gtk.Dialog(parent=self)
        dialog.connect('delete-event', lambda *x: x[0].destroy())
        dialog.get_content_area().add(installer_combo)
        dialog.show_all()
        dialog.run()

    def on_installer_combo_changed(self, combo, installer):
        dialog = combo.get_parent().get_parent()
        dialog.destroy()
        print(installer)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    if not os.path.exists(ICON_CACHE):
        os.makedirs(ICON_CACHE)
    win = GogWindow()
    win.connect("delete-event", Gtk.main_quit)
    win.show_all()
    Gtk.main()
