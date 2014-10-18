#! /usr/bin/python
from gi.repository import Gtk
import humblebundle




class ConnectWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Humble Bundle sync")
        self.set_size_request(200, 100)

        self.timeout_id = None

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_text("login")
        login = self.entry.get_text()
        vbox.pack_start(self.entry, True, True, 0)
        hbox = Gtk.Box(spacing=6)
        vbox.pack_start(hbox, True, True, 0)

        self.entry2 = Gtk.Entry()
        passwd = self.entry2.set_text("password")
        login = self.entry2.get_text()
        vbox.pack_start(self.entry2, True, True, 0)
        hbox = Gtk.Box(spacing=6)
        vbox.pack_start(hbox, True, True, 0)

        button = Gtk.Button("Connect")
        button.connect("clicked", self.on_connection)
        hbox.pack_start(button, True, True, 0)
        passwd = self.entry2

    def get_order_products(client, gamekey):
            order = client.get_order(gamekey)
            return order.subproducts


    def on_connection(self, button):

        client = humblebundle.HumbleApi()
        self.login = self.entry.get_text()
        self.passwd = self.entry2.get_text()

        client.login(self.login, self.passwd)
        gamekeys = client.get_gamekeys()
        print(gamekeys)
        global order_list

        global gameName
        order_list = client.order_list()
        gamekeys = client.get_gamekeys()
        self.get_order_products(client, gamekeys[0])
        gameName = [product.human_name for product in self.get_order_products(client, gamekeys[0])]
        print(gameName[0])
        
        # We are trying to print gameName in a beautiful list, but their is an error...
        # python:
        #
        # line 55, in on_connection
        # self.get_order_products(client, gamekeys[0])
        # TypeError: get_order_products() takes 2 positional arguments but 3 were given


# Precedent try 
#
# for gamekey in gamekeys:
#     order = client.get_order(gamekey)

# for subproduct in order.subproducts:
#     global gameName
#     subproduct.machine_name
#     print([product.human_name for product in products])


    def on_editable_toggled(self, button):

        value = button.get_activate()
        self.entry.set_editable(value)


class MainHBSyncWindow(Gtk.Window):

    def __init__(self):

        Gtk.Window.__init__(self, title="CellRendererToggle Example")

        self.set_default_size(200, 200)



        self.liststore = Gtk.ListStore(str, bool)

        self.liststore.append([order_list, False, True])

        self.liststore.append([gameName[0], False, True])
        
        # Used [0] for testing purpose, a for loop will come one day 
        # so one day we will just use [count] but for now it's [0]
        

        treeview = Gtk.TreeView(model=self.liststore)

        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Text", renderer_text, text=0)
        treeview.append_column(column_text)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_cell_toggled)

        column_toggle = Gtk.TreeViewColumn("Toggle", renderer_toggle, active=1)
        treeview.append_column(column_toggle)

        renderer_radio = Gtk.CellRendererToggle()
        renderer_radio.set_radio(True)
        renderer_radio.connect("toggled", self.on_cell_radio_toggled)

        column_radio = Gtk.TreeViewColumn("Radio", renderer_radio, active=2)
        treeview.append_column(column_radio)

        self.add(treeview)


    def on_cell_radio_toggled(self, widget, path):
        selected_path = Gtk.TreePath(path)
        for row in self.liststore:
            row[2] = (row.path == selected_path)

    def on_cell_toggled(self, widget, path):
        self.liststore[path][1] = not self.liststore[path][1]

conwin = ConnectWindow()
conwin.connect("delete-event", Gtk.main_quit)
conwin.show_all()
Gtk.main()

mainwin = MainHBSyncWindow()
mainwin.connect("delete-event", Gtk.main_quit)
mainwin.show_all()
Gtk.main()
