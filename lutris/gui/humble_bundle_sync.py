#! /usr/bin/python
from gi.repository import Gtk
from lutris.util import humbleapi


class HumbleBundleDialog(Gtk.Dialog):
    def __init__(self):
        Gtk.Dialog.__init__(self, title="Humble Bundle sync")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        self.login_entry = Gtk.Entry()
        self.login_entry.set_text("login")
        self.login_entry.get_text()
        vbox.pack_start(self.login_entry, True, True, 0)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_text("password")
        vbox.pack_start(self.password_entry, True, True, 0)

        connect_button = Gtk.Button("Connect")
        connect_button.connect("clicked", self.on_connect_clicked)
        vbox.pack_start(connect_button, True, True, 0)

    def get_order_products(client, gamekey):
            order = client.get_order(gamekey)
            return order.subproducts

    def on_connect_clicked(self, button):
        self.login = self.entry.get_text()
        self.passwd = self.entry2.get_text()

        self.client = humbleapi.HumbleApi()
        self.client.login(self.login, self.passwd)

        order_list = self.client.order_list()
        print order_list
        # gamekeys = client.get_gamekeys()
        # self.get_order_products(client, gamekeys[0])
        # self.game_name = [product.human_name for product in self.get_order_products(client, gamekeys[0])]


if __name__ == "__main__":
    HumbleBundleDialog()
    Gtk.main()
