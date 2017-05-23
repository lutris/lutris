from gi.repository import Gtk, Pango


class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding"""
    def __init__(self, width, *args, **kwargs):
        super(GridViewCellRendererText, self).__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0
        self.props.width = width
        self.props.wrap_width = width
