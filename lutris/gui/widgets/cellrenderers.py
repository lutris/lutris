import cairo
from gi.repository import GLib, Gtk, Pango, GObject

from lutris.gui.widgets.utils import get_default_icon_path, get_scaled_surface_by_path, get_media_generation_number, \
    get_surface_size, has_stock_icon, get_runtime_icon_path, ICON_SIZE


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
        self._platform = None
        self._is_installed = True
        self.cached_surfaces_new = {}
        self.cached_surfaces_old = {}
        self.cycle_cache_idle_id = None
        self.cached_surface_generation = 0

    @GObject.Property(type=int, default=0)
    def cell_width(self):
        return self._cell_width

    @cell_width.setter
    def cell_width(self, value):
        self._cell_width = value
        self.clear_cache()

    @GObject.Property(type=int, default=0)
    def cell_height(self):
        return self._cell_height

    @cell_height.setter
    def cell_height(self, value):
        self._cell_height = value
        self.clear_cache()

    @GObject.Property(type=str)
    def media_path(self):
        return self._media_path

    @media_path.setter
    def media_path(self, value):
        self._media_path = value

    @GObject.Property(type=str)
    def platform(self):
        return self._platform

    @platform.setter
    def platform(self, value):
        self._platform = value

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

        if cell_width > 0 and cell_height > 0 and path:  # pylint: disable=comparison-with-callable
            surface = self.get_cached_surface_by_path(widget, path)
            if not surface:
                # The default icon needs to be scaled to fill the cell space.
                path = get_default_icon_path((cell_width, cell_height))
                surface = self.get_cached_surface_by_path(widget, path,
                                                          preserve_aspect_ratio=False)

            if surface:
                width, height = get_surface_size(surface)

                x = round(cell_area.x + (cell_area.width - width) / 2)  # centered
                y = round(cell_area.y + cell_area.height - height)  # at bottom of cell

                cr.set_source_surface(surface, x, y)
                cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
                cr.rectangle(x, y, width, height)
                cr.fill()

            if self.platform:
                icon_path = get_runtime_icon_path(self.platform + "-symbolic")
                if not icon_path:
                    icon_path = get_runtime_icon_path(self.platform)
                if icon_path:
                    icon_size = 16, 16
                    alpha = 1 if self.is_installed else 100/255
                    x = min(x + cell_width - icon_size[0] / 2  - 1, cell_area.x + cell_area.width - icon_size[0] -1 )
                    y = cell_area.y + cell_area.height - icon_size[1] - 1

                    cr.save()
                    cr.rectangle(x, y, icon_size[0], icon_size[0])
                    cr.set_source_rgba(1, 1, 1, alpha)
                    cr.fill()

                    cr.rectangle(x-.5, y-.5, icon_size[0] + 1, icon_size[0] + 1)
                    cr.set_source_rgba(0, 0, 0, alpha)
                    cr.set_line_width(.5)
                    cr.stroke()
                    cr.restore()

                    icon = self.get_cached_surface_by_path(widget, icon_path, icon_size)
                    cr.set_source_surface(icon, x, y)
                    cr.paint()

            # Idle time will wait until the widget has drawn whatever it wants to;
            # we can then discard surfaces we aren't using anymore.
            if not self.cycle_cache_idle_id:
                self.cycle_cache_idle_id = GLib.idle_add(self.cycle_cache)

    def clear_cache(self):
        """Discards all cached surfaces; used when some properties are changed."""
        self.cached_surfaces_old.clear()
        self.cached_surfaces_new.clear()

    def cycle_cache(self):
        """Is the key cache size control trick. When called, the surfaces cached or used
        since the last call are preserved, but those not touched are discarded.

        We call this at idle time after rendering a cell; this should keep all the surfaces
        rendered at that time, so during scrolling the visible media are kept and scrolling is smooth.
        At other times we may discard almost all surfaces, saving memory."""
        self.cached_surfaces_old = self.cached_surfaces_new
        self.cached_surfaces_new = {}
        self.cycle_cache_idle_id = None

    def get_cached_surface_by_path(self, widget, path, size=None, preserve_aspect_ratio=True):
        """This obtains the scaled surface to rander for a given media path; this is cached
        in this render, but we'll clear that cache when the media generation number is changed,
        or certain properties are. We also age surfaces from the cache at idle time after
        rendering."""
        if self.cached_surface_generation != get_media_generation_number():
            self.cached_surface_generation = get_media_generation_number()
            self.clear_cache()

        key = widget, path, size, self.is_installed, preserve_aspect_ratio

        surface = self.cached_surfaces_new.get(key)
        if surface:
            return surface

        surface = self.cached_surfaces_old.get(key)

        if not surface:
            surface = self.get_surface_by_path(widget, path, size, preserve_aspect_ratio)

        self.cached_surfaces_new[key] = surface
        return surface

    def get_surface_by_path(self, widget, path, size=None, preserve_aspect_ratio=True):
        cell_size = size or (self.cell_width, self.cell_height)
        scale_factor = widget.get_scale_factor() if widget else 1
        alpha = 1 if self.is_installed else 100 / 255  # pylint:disable=using-constant-test
        return get_scaled_surface_by_path(path, cell_size, scale_factor, alpha,
                                          preserve_aspect_ratio=preserve_aspect_ratio)
