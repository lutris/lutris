from functools import lru_cache

from gi.repository import Gtk, Gdk, Pango, GObject

from lutris.gui.widgets.utils import get_pixbuf_by_path, get_uninstalled_pixbuf, \
    get_default_icon_path


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
        cell_width = self.cell_width
        cell_height = self.cell_height
        path = self.pixbuf_path

        if cell_width > 0 and cell_height > 0 and path:  # pylint: disable=comparison-with-callable
            pixbuf = self._get_pixbuf(path, self.is_installed)

            if pixbuf:
                x, y, fit_factor_x, fit_factor_y = self._get_fit_factors(pixbuf, cell_area)
            else:
                # The default icon needs to be scaled to fill the cell space
                path = get_default_icon_path((cell_width, cell_height))
                pixbuf = self._get_pixbuf(path, self.is_installed)
                x, y, fit_factor_x, fit_factor_y = self._get_fill_factors(pixbuf, cell_area)

            if pixbuf:
                cr.translate(x, y)
                cr.scale(fit_factor_x, fit_factor_y)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
                cr.paint()

    def _get_fit_factors(self, pixbuf, target_area):
        """The provides the position and scaling to draw a pixbuf in the
        target area, preserving its aspect ratio."""
        if not pixbuf:
            return 0, 0, 0, 0

        actual_width = pixbuf.get_width()
        actual_height = pixbuf.get_height()

        fit_factor_x = min(self.cell_width / actual_width, self.cell_height / actual_height)
        fit_factor_y = fit_factor_x
        x = target_area.x + (target_area.width - actual_width * fit_factor_x) / 2  # centered
        y = target_area.y + target_area.height - actual_height * fit_factor_y  # at bottom of cell
        return x, y, fit_factor_x, fit_factor_y

    def _get_fill_factors(self, pixbuf, cell_area):
        """The provides the position and scaling to draw a pixbuf, filling the
        target area, and not preserving its aspect ratio."""
        actual_width = pixbuf.get_width()
        actual_height = pixbuf.get_height()

        fit_factor_x = self.cell_width / actual_width
        fit_factor_y = self.cell_height / actual_height
        x = cell_area.x + (cell_area.width - actual_width * fit_factor_x) / 2  # centered
        y = cell_area.y + cell_area.height - actual_height * fit_factor_y  # at bottom of cell
        return x, y, fit_factor_x, fit_factor_y

    @lru_cache(maxsize=128)
    def _get_pixbuf(self, path, is_installed=True):
        """This function is really here to cache the images, so it needs
        to be 'pure'- we need all the parameters to be parameters here."""
        pixbuf = get_pixbuf_by_path(path)
        return pixbuf if is_installed else get_uninstalled_pixbuf(pixbuf)
