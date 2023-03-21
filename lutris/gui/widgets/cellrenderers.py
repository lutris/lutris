import cairo
from gi.repository import Gtk, Gdk, Pango, GObject

from lutris.gui.widgets.utils import get_default_icon_path, get_cached_pixbuf_by_path


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
        self._media_path = None
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
    def media_path(self):
        return self._media_path

    @media_path.setter
    def media_path(self, value):
        self._media_path = value

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
        path = self.media_path

        def is_hard_scale_factor(scale_factor):
            # We need to use 'BEST' filtering for difficult scaling factors,
            # which produce edge artifacts with the faster GOOD filter.
            # We see this if we are scaling to enlarge an image, or shrinking to
            # arbitrary size; but Lutris icons default to 128x128, and shrink to 32x32 -
            # that works fine. So we think x.25, x.5 and x1 are easy and all others
            # factors hard.
            widget_scale_factor = widget.get_scale_factor() if widget else 1
            real_scale_factor = float(scale_factor * widget_scale_factor)
            return real_scale_factor not in [0.25, 0.5, 1]

        if cell_width > 0 and cell_height > 0 and path:  # pylint: disable=comparison-with-callable
            pixbuf = get_cached_pixbuf_by_path(path, self.is_installed)
            source_filter = cairo.Filter.GOOD  # pylint:disable=no-member

            if pixbuf:
                x, y, fit_factor_x, fit_factor_y = self._get_fit_factors(pixbuf, cell_area)
                if is_hard_scale_factor(fit_factor_x) or is_hard_scale_factor(fit_factor_y):
                    source_filter = cairo.Filter.BEST  # pylint:disable=no-member
            else:
                # The default icon needs to be scaled to fill the cell space, but it so happens
                # that the default images do not produce edge artifacts anyway.
                path = get_default_icon_path((cell_width, cell_height))
                pixbuf = get_cached_pixbuf_by_path(path, self.is_installed)
                x, y, fit_factor_x, fit_factor_y = self._get_fill_factors(pixbuf, cell_area)

            if pixbuf:
                cr.translate(x, y)
                cr.scale(fit_factor_x, fit_factor_y)
                Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)

                cr.get_source().set_filter(source_filter)  # pylint: disable=no-member
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
        # Try to place x,y on a pixel edge
        return round(x), round(y), fit_factor_x, fit_factor_y

    def _get_fill_factors(self, pixbuf, cell_area):
        """The provides the position and scaling to draw a pixbuf, filling the
        target area, and not preserving its aspect ratio."""
        actual_width = pixbuf.get_width()
        actual_height = pixbuf.get_height()

        fit_factor_x = self.cell_width / actual_width
        fit_factor_y = self.cell_height / actual_height
        x = cell_area.x + (cell_area.width - actual_width * fit_factor_x) / 2  # centered
        y = cell_area.y + cell_area.height - actual_height * fit_factor_y  # at bottom of cell
        # Try to place x,y on a pixel edge
        return round(x), round(y), fit_factor_x, fit_factor_y
