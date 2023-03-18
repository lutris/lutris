from functools import lru_cache

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
    """A pixbuf cell renderer that takes not the pixbuf but a path to an image file;
    it loads that image only when rendering. It also has properties for its width
    and height, so it need not load the pixbuf to know its size."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cell_width = 0
        self._cell_height = 0
        self._pixbuf_path = None
        self._is_installed = True

    @GObject.Property(type=int, default=0)
    def cell_width(self):
        return self._cell_width

    @cell_width.setter
    def cell_width(self, value):
        self._cell_width = value

    @GObject.Property(type=int, default=0)
    def cell_height(self):
        return self._cell_height

    @cell_height.setter
    def cell_height(self, value):
        self._cell_height = value

    @GObject.Property(type=str)
    def pixbuf_path(self):
        return self._pixbuf_path

    @pixbuf_path.setter
    def pixbuf_path(self, value):
        self._pixbuf_path = value

    @GObject.Property(type=bool, default=True)
    def is_installed(self):
        return self._is_installed

    @is_installed.setter
    def is_installed(self, value):
        self._is_installed = value

    def do_get_size(self, widget, cell_area):
        return 0, 0, self.cell_width, self.cell_height

    def do_render(self, cr, widget, background_area, cell_area, flags):
        # HiDPI support - we'll load the pixbuf at a larger size, but scale
        # it down during rendering. If the render target is really high-DPI
        # and the source image has the detail, this will preserve it.
        scale_factor = widget.get_scale_factor() if widget else 1

        width = self.cell_width * scale_factor
        height = self.cell_height * scale_factor
        path = self.pixbuf_path

        if width > 0 and height > 0 and path:  # pylint: disable=comparison-with-callable
            pixbuf = self._get_pixbuf(path, (width, height), self.is_installed)

            if pixbuf:
                actual_width = pixbuf.get_width() / scale_factor
                actual_height = pixbuf.get_height() / scale_factor
                x = cell_area.x + (cell_area.width - actual_width) / 2  # centered
                y = cell_area.y + cell_area.height - actual_height  # at bottom of cell
                cr.translate(x, y)
                cr.scale(1 / scale_factor, 1 / scale_factor)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
                cr.paint()

    @lru_cache(maxsize=128)
    def _get_pixbuf(self, path, size, is_installed):
        return get_pixbuf(path, size, is_installed=is_installed)
