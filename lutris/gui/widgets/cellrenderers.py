from gi.repository import Gtk, Gdk, Pango, GObject

from lutris.gui.widgets.utils import get_pixbuf


class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0

    def set_width(self, width):
        self.props.wrap_width = width


class GridViewCellRendererImage(Gtk.CellRenderer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cell_width = 0
        self.cell_height = 0
        self._pixbuf_path = None

    @GObject.Property(type=str)
    def pixbuf_path(self):
        return self._pixbuf_path

    @pixbuf_path.setter
    def pixbuf_path(self, value):
        self._pixbuf_path = value

    def do_get_size(self, widget, cell_area):
        return 0, 0, self.cell_width, self.cell_height

    def do_render(self, cr, widget, background_area, cell_area, flags):
        pixbuf = get_pixbuf(self.pixbuf_path, (self.cell_width, self.cell_height))

        if pixbuf:
            x = cell_area.x + (cell_area.width - self.cell_width) / 2
            y = cell_area.y + (cell_area.height - self.cell_height) / 2

            Gdk.cairo_set_source_pixbuf(cr, pixbuf, x, y)
            cr.paint()
