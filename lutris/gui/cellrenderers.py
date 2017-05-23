from gi.repository import Gtk, Pango


class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding"""
    def __init__(self, width, **kwargs):
        super().__init__(
            alignment=Pango.Alignment.CENTER,
            wrap_mode=Pango.WrapMode.WORD,
            xalign=0.5,
            yalign=0,
            width=width,
            wrap_width=width,
            **kwargs
        )
