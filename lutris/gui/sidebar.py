# from gi.repository import Gtk


class Sidebar(object):
    def __init__(self, treeview, liststore):
        self.treeview = treeview
        self.liststore = liststore
        self.liststore.set_column_types((str, str, str))
        self.liststore.append(['1', '1', '1'])
