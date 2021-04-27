from gi.repository import Gtk

from lutris.gui.widgets.common import VBox


class BaseConfigBox(VBox):

    def get_section_label(self, text):
        label = Gtk.Label(visible=True)
        label.set_markup("<b>%s</b>" % text)
        label.set_alignment(0, 0.5)
        return label

    def __init__(self):
        super().__init__(visible=True)
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_right(80)
        self.set_margin_left(80)
