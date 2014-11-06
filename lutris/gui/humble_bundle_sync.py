#! /usr/bin/python
from gi.repository import Gtk
from lutris.gui.widgets import Dialog
from lutris.util import humbleapi


class HumbleBundleDialog(Dialog):
    def __init__(self):
        super(HumbleBundleDialog, self).__init__(title="Humble Bundle")
        self.connect('destroy', self.on_destroy)
        self.login_entry = Gtk.Entry()
        self.login_entry.set_text("login")
        self.login_entry.get_text()
        self.vbox.pack_start(self.login_entry, True, True, 0)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_text("password")
        self.vbox.pack_start(self.password_entry, True, True, 0)

        connect_button = Gtk.Button("Connect")
        connect_button.connect("clicked", self.on_connect_clicked)
        self.vbox.pack_start(connect_button, True, True, 0)

    def on_destroy(self, widget):
        Gtk.main_quit()

    def on_connect_clicked(self, button):
        login = self.login_entry.get_text()
        password = self.password_entry.get_text()
        self.client = humbleapi.Client(login, password)
        self.client.store_credentials(login, password)

if __name__ == "__main__":
    dlg = HumbleBundleDialog()
    dlg.show_all()
    Gtk.main()
