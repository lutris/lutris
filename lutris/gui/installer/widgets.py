from gi.repository import Gtk, Pango


class InstallerLabel(Gtk.Label):
    """A label for installers"""

    def __init__(self, text, wrap=True):
        super().__init__()
        if wrap:
            self.set_line_wrap(True)
            self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        else:
            self.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.set_alignment(0, 0.5)
        self.set_margin_right(12)
        self.set_markup(text)
        self.props.can_focus = False
        self.set_tooltip_text(text)
