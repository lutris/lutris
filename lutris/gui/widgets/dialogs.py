from gi.repository import Gtk


class Dialog(Gtk.Dialog):
    def __init__(self, title=None, parent=None, flags=0, buttons=None):
        super(Dialog, self).__init__(title, parent, flags, buttons)
        self.set_border_width(10)
        self.set_destroy_with_parent(True)
