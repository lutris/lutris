import cairo
from gi.repository import Gtk, Pango, GObject

from lutris.gui.widgets.utils import get_default_icon_path, get_cached_surface_by_path


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
        scale_factor = widget.get_scale_factor() if widget else 1

        if cell_width > 0 and cell_height > 0 and path:  # pylint: disable=comparison-with-callable
            surface = get_cached_surface_by_path(path, cell_width, cell_height, scale_factor, self.is_installed)

            if not surface:
                # The default icon needs to be scaled to fill the cell space.
                path = get_default_icon_path((cell_width, cell_height))
                surface = get_cached_surface_by_path(path, cell_width, cell_height, scale_factor,
                                                     self.is_installed, preserve_aspect_ratio=False)

            if surface:
                ss_scale_x, ss_scale_y = surface.get_device_scale()
                width = surface.get_width() / ss_scale_x
                height = surface.get_height() / ss_scale_y

                x = round(cell_area.x + (cell_area.width - width) / 2)  # centered
                y = round(cell_area.y + cell_area.height - height)  # at bottom of cell

                cr.set_source_surface(surface, x, y)
                cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
                cr.rectangle(x, y, width, height)
                cr.fill()
