from gi.repository import GLib, Gtk, Pango


class InstallerLabel(Gtk.Label):
    """A label for installers"""

    def __init__(self, text, wrap=True, selectable=False):
        super().__init__()

        is_valid_markup = InstallerLabel.is_valid_pango_markup(text)

        if wrap:
            self.set_line_wrap(True)
            self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        else:
            self.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)
        self.set_alignment(0, 0.5)
        self.set_margin_right(12)

        if is_valid_markup:
            self.set_markup(text)
        else:
            self.set_text(text)

        self.props.can_focus = False
        self.set_tooltip_text(text)
        self.set_selectable(selectable)

    @staticmethod
    def is_valid_pango_markup(text):
        def destroy_func(_user_data):
            pass  # required by GLib, but we don't need this callback

        if len(text) == 0:
            return True  # Trivial case - empty strings are always valid

        try:
            parser = GLib.MarkupParser()
            context = GLib.MarkupParseContext(parser, GLib.MarkupParseFlags.DEFAULT_FLAGS, None, destroy_func)

            markup = f"<markup>{text}</markup>"
            context.parse(markup, len(markup))
            return True
        except GLib.GError:
            return False
