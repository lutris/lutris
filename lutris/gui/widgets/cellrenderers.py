# pylint:disable=using-constant-test
# pylint:disable=comparison-with-callable
from math import floor

import cairo
from gi.repository import GLib, GObject, Gtk, Pango

from lutris.gui.widgets.utils import (
    get_default_icon_path, get_media_generation_number, get_runtime_icon_path, get_scaled_surface_by_path,
    get_surface_size
)


class GridViewCellRendererText(Gtk.CellRendererText):
    """CellRendererText adjusted for grid view display, removes extra padding
    and caches cell metrics for improved resize performance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.props.alignment = Pango.Alignment.CENTER
        self.props.wrap_mode = Pango.WrapMode.WORD
        self.props.xalign = 0.5
        self.props.yalign = 0
        self.fixed_width = None
        self.cached_height = {}
        self.cached_width = {}

    def set_width(self, width):
        self.fixed_width = width
        self.props.wrap_width = width
        self.clear_caches()

    def clear_caches(self):
        self.cached_height.clear()
        self.cached_width.clear()

    def do_get_preferred_width(self, widget):
        text = self.props.text  # pylint:disable=no-member
        if self.fixed_width and text in self.cached_width:
            return self.cached_width[text]

        width = Gtk.CellRendererText.do_get_preferred_width(self, widget)

        if self.fixed_width:
            self.cached_width[text] = width

        return width

    def do_get_preferred_width_for_height(self, widget, width):
        text = self.props.text  # pylint:disable=no-member
        if self.fixed_width and text in self.cached_width:
            return self.cached_width[text]

        width = Gtk.CellRendererText.do_get_preferred_width_for_height(self, widget, width)

        if self.fixed_width:
            self.cached_width[text] = width

        return width

    def do_get_preferred_height(self, widget):
        text = self.props.text  # pylint:disable=no-member
        if self.fixed_width and text in self.cached_height:
            return self.cached_height[text]

        height = Gtk.CellRendererText.do_get_preferred_height(self, widget)

        if self.fixed_width:
            self.cached_height[text] = height

        return height

    def do_get_preferred_height_for_width(self, widget, width):
        text = self.props.text  # pylint:disable=no-member
        if self.fixed_width and text in self.cached_height:
            return self.cached_height[text]

        height = Gtk.CellRendererText.do_get_preferred_height_for_width(self, widget, width)

        if self.fixed_width:
            self.cached_height[text] = height

        return height


class GridViewCellRendererImage(Gtk.CellRenderer):
    """A pixbuf cell renderer that takes not the pixbuf but a path to an image file;
    it loads that image only when rendering. It also has properties for its width
    and height, so it need not load the pixbuf to know its size."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._media_width = 0
        self._media_height = 0
        self._media_path = None
        self._platform = None
        self._is_installed = True
        self.cached_surfaces_new = {}
        self.cached_surfaces_old = {}
        self.cached_surfaces_loaded = 0
        self.cycle_cache_idle_id = None
        self.cached_surface_generation = 0

    @GObject.Property(type=int, default=0)
    def media_width(self):
        """This is the width of the media being rendered; if the cell is larger
        it will be centered in the cell area."""
        return self._media_width

    @media_width.setter
    def media_width(self, value):
        self._media_width = value
        self.clear_cache()

    @GObject.Property(type=int, default=0)
    def media_height(self):
        """This is the height of the media being rendered; if the cell is larger
        it will be at the bottom of the cell area."""
        return self._media_height

    @media_height.setter
    def media_height(self, value):
        self._media_height = value
        self.clear_cache()

    @GObject.Property(type=str)
    def media_path(self):
        """This is the path to the media file to be displayed."""
        return self._media_path

    @media_path.setter
    def media_path(self, value):
        self._media_path = value

    @GObject.Property(type=str)
    def platform(self):
        """This is the platform text, a comma separated list; we try to convert
        this into icons, if it is not None."""
        return self._platform

    @platform.setter
    def platform(self, value):
        self._platform = value

    @GObject.Property(type=bool, default=True)
    def is_installed(self):
        """This flag indicates if the game is installed; if not the media is shown
        faded out."""
        return self._is_installed

    @is_installed.setter
    def is_installed(self, value):
        self._is_installed = value

    def do_get_preferred_width(self, widget):
        return self.media_width, self.media_width

    def do_get_preferred_height(self, widget):
        return self.media_height, self.media_height

    def do_render(self, cr, widget, background_area, cell_area, flags):
        media_width = self.media_width
        media_height = self.media_height
        path = self.media_path
        alpha = 1 if self.is_installed else 100 / 255

        if media_width > 0 and media_height > 0 and path:
            surface = self.get_cached_surface_by_path(widget, path)
            if not surface:
                # The default icon needs to be scaled to fill the cell space.
                path = get_default_icon_path((media_width, media_height))
                surface = self.get_cached_surface_by_path(widget, path,
                                                          preserve_aspect_ratio=False)

            if surface:
                x, y = self.get_media_position(surface, cell_area)

                if alpha >= 1:
                    self.render_media(cr, widget, surface, x, y)
                    self.render_platforms(cr, widget, surface, x, cell_area)
                else:
                    cr.push_group()
                    self.render_media(cr, widget, surface, x, y)
                    self.render_platforms(cr, widget, surface, x, cell_area)
                    cr.pop_group_to_source()
                    cr.paint_with_alpha(alpha)

            # Idle time will wait until the widget has drawn whatever it wants to;
            # we can then discard surfaces we aren't using anymore.
            if not self.cycle_cache_idle_id:
                self.cycle_cache_idle_id = GLib.idle_add(self.cycle_cache)

    @staticmethod
    def is_bright_corner(surface, corner_size):
        """Tests several pixels near the corner of the surface where the badges
        are drawn. If all are 'bright', we'll render the badges differently. This
        means all 4 components must be at least 128/255."""
        surface_format = surface.get_format()

        # We only use the ARGB32 format, so we just give up
        # for anything else.
        if surface_format != cairo.FORMAT_ARGB32:  # pylint:disable=no-member
            return False

        # Scale the corner according to the surface's scale factor -
        # normally the same as our UI scale factor.
        device_scale_x, device_scale_y = surface.get_device_scale()
        corner_pixel_width = int(corner_size[0] * device_scale_x)
        corner_pixel_height = int(corner_size[1] * device_scale_y)
        pixel_width = surface.get_width()
        pixel_height = surface.get_height()

        def is_bright_pixel(x, y):
            # Checks if a pixel is 'bright'; this does not care
            # if the pixel is big or little endian- it just checks
            # all four channels.
            if 0 <= x < pixel_width and 0 <= y < pixel_height:
                stride = surface.get_stride()
                data = surface.get_data()

                offset = (y * stride) + x * 4
                pixel = data[offset: offset + 4]

                for channel in pixel:
                    if channel < 128:
                        return False
                return True
            return False

        return (
            is_bright_pixel(pixel_width - 1, pixel_height - 1)
            and is_bright_pixel(pixel_width - corner_pixel_width, pixel_height - 1)
            and is_bright_pixel(pixel_width - 1, pixel_height - corner_pixel_height)
            and is_bright_pixel(pixel_width - corner_pixel_width, pixel_height - corner_pixel_height)
        )

    def get_media_position(self, surface, cell_area):
        """Computes the position of the upper left corner where we will render
        a surface within the cell area."""
        width, height = get_surface_size(surface)
        x = round(cell_area.x + (cell_area.width - width) / 2)  # centered
        y = round(cell_area.y + cell_area.height - height)  # at bottom of cell
        return x, y

    def get_badge_icon_size(self):
        """Returns the size of the badge icons to render, or None to hide them. We check
        width for the smallest size because Dolphin has very thin banners, but we only hide
        badges for icons, not banners."""
        if self.media_width < 64:
            return None
        if self.media_height < 128:
            return 16, 16
        if self.media_height < 256:
            return 24, 24
        return 32, 32

    def render_media(self, cr, widget, surface, x, y):
        """Renders the media itself, given the surface containing it
        and the position."""
        width, height = get_surface_size(surface)

        cr.set_source_surface(surface, x, y)
        cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
        cr.rectangle(x, y, width, height)
        cr.fill()

    def render_platforms(self, cr, widget, surface, surface_x, cell_area):
        """Renders the stack of platform icons. They appear lined up vertically to the
        right of 'media_right', if that will fit in 'cell_area'."""
        platform = self.platform
        icon_size = self.get_badge_icon_size()
        if platform and icon_size:
            if "," in platform:
                platforms = platform.split(",")  # pylint:disable=no-member
            else:
                platforms = [platform]

            icon_paths = [get_runtime_icon_path(p + "-symbolic") for p in platforms]
            icon_paths = [path for path in icon_paths if path]
            if icon_paths:
                self.render_badge_stack(cr, widget, surface, surface_x, icon_paths, icon_size, cell_area)

    def render_badge_stack(self, cr, widget, surface, surface_x, icon_paths, icon_size, cell_area):
        """Renders a vertical stack of badges, placed at the edge of the media, off to the right
        of 'media_right' if this will fit in the 'cell_area'. The icons in icon_paths are drawn from
        top to bottom, and spaced to fit in 'cell_area', even if they overlap because of this."""

        badge_width = icon_size[0]
        badge_height = icon_size[1]
        on_bright_surface = GridViewCellRendererImage.is_bright_corner(surface, (badge_width, badge_height))

        alpha = 0.6
        bright_color = 0.8, 0.8, 0.8
        dark_color = 0.2, 0.2, 0.2
        back_color = bright_color if on_bright_surface else dark_color
        fore_color = dark_color if on_bright_surface else bright_color

        def render_badge(badge_x, badge_y, path):
            cr.rectangle(badge_x, badge_y, icon_size[0], icon_size[0])
            cr.set_source_rgba(back_color[0], back_color[1], back_color[2], alpha)
            cr.fill()

            icon = self.get_cached_surface_by_path(widget, path, size=icon_size)
            cr.set_source_rgba(fore_color[0], fore_color[1], fore_color[2], alpha)
            cr.mask_surface(icon, badge_x, badge_y)

        media_right = surface_x + get_surface_size(surface)[0]

        x = media_right - badge_width
        spacing = (cell_area.height - badge_height * len(icon_paths)) / max(1, len(icon_paths) - 1)
        spacing = min(spacing, 1)
        y_offset = floor(badge_height + spacing)
        y = cell_area.y + cell_area.height - badge_height - y_offset * (len(icon_paths) - 1)

        for icon_path in icon_paths:
            render_badge(x, y, icon_path)
            y = y + y_offset

    def clear_cache(self):
        """Discards all cached surfaces; used when some properties are changed."""
        self.cached_surfaces_old.clear()
        self.cached_surfaces_new.clear()

    def cycle_cache(self):
        """Is the key cache size control trick. When called, the surfaces cached or used
        since the last call are preserved, but those not touched are discarded.

        We call this at idle time after rendering a cell; this should keep all the surfaces
        rendered at that time, so during scrolling the visible media are kept and scrolling is smooth.
        At other times we may discard almost all surfaces, saving memory.

        We skip clearing anything if no surfaces have been loaded; this happens if drawing was
        serviced entirely from cache. GTK may have redrawn just one image or something, so
        let's not disturb the cache for that."""
        if self.cached_surfaces_loaded > 0:
            self.cached_surfaces_old = self.cached_surfaces_new
            self.cached_surfaces_new = {}
            self.cached_surfaces_loaded = 0
        self.cycle_cache_idle_id = None

    def get_cached_surface_by_path(self, widget, path, size=None, preserve_aspect_ratio=True):
        """This obtains the scaled surface to rander for a given media path; this is cached
        in this render, but we'll clear that cache when the media generation number is changed,
        or certain properties are. We also age surfaces from the cache at idle time after
        rendering."""
        if self.cached_surface_generation != get_media_generation_number():
            self.cached_surface_generation = get_media_generation_number()
            self.clear_cache()

        key = widget, path, size, preserve_aspect_ratio

        if key in self.cached_surfaces_new:
            return self.cached_surfaces_new[key]

        if key in self.cached_surfaces_old:
            surface = self.cached_surfaces_old[key]
        else:
            surface = self.get_surface_by_path(widget, path, size, preserve_aspect_ratio)
            # We cache missing surfaces too, but only a successful load trigger
            # cache cycling
            if surface:
                self.cached_surfaces_loaded += 1

        self.cached_surfaces_new[key] = surface
        return surface

    def get_surface_by_path(self, widget, path, size=None, preserve_aspect_ratio=True):
        cell_size = size or (self.media_width, self.media_height)
        scale_factor = widget.get_scale_factor() if widget else 1
        return get_scaled_surface_by_path(path, cell_size, scale_factor,
                                          preserve_aspect_ratio=preserve_aspect_ratio)
