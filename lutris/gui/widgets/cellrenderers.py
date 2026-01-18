# pylint: disable=no-member
# pylint:disable=using-constant-test
# pylint:disable=comparison-with-callable
from gettext import gettext as _
from math import floor

import gi

from lutris.util.jobs import schedule_at_idle
from lutris.util.log import logger

gi.require_version("PangoCairo", "1.0")

import cairo
from gi.repository import Gdk, GObject, Gtk, Pango, PangoCairo

from lutris.gui.widgets.utils import (
    MEDIA_CACHE_INVALIDATED,
    get_default_icon_path,
    get_runtime_icon_path,
    get_scaled_surface_by_path,
    get_surface_size,
)
from lutris.services.service_media import resolve_media_path
from lutris.util.path_cache import MISSING_GAMES

_MEDIA_CACHE_GENERATION_NUMBER = 0


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
        self._game_id = None
        self._service = None
        self._media_paths = []
        self._show_badges = True
        self._platform = None
        self._is_installed = True
        self.cached_surfaces_new = {}
        self.cached_surfaces_old = {}
        self.cached_surfaces_loaded = 0
        self.cached_surface_generation = 0
        self.badge_size = 0, 0
        self.badge_alpha = 0.6
        self.badge_fore_color = 1, 1, 1
        self.badge_back_color = 0, 0, 0
        self._inset_fractions = {}

    def inset_game(self, game_id: str, fraction: float) -> bool:
        """This function indicates that a particular game should be displayed inset by a certain fraction of
        its total size; 0 is full size, 0.1 would show it at 90% size, but centered.

        This is not bound as an attribute; it's used for an ephemeral animation, and we wouldn't want
        to mess with the GameStore to do it. Instead, the cell renderer tracks these per game ID, and
        the caller uses queue_draw() to trigger a redraw.

        Set the fraction to 0 for a game to remove the effect when done.

        This returns True if it alters the inset of a game, and False if not because it was
        already set that way."""
        if fraction > 0.0:
            if fraction != self._inset_fractions.get(game_id):
                self._inset_fractions[game_id] = fraction
                return True
        elif game_id in self._inset_fractions:
            del self._inset_fractions[game_id]
            return True

        return False

    @GObject.Property(type=str)
    def game_id(self):
        """This is the path to the media file to be displayed."""
        return self._game_id

    @game_id.setter
    def game_id(self, value):
        self._game_id = value

    @GObject.Property(type=GObject.TYPE_PYOBJECT)
    def service(self):
        return self._service

    @service.setter
    def service(self, value):
        self._service = value

    @GObject.Property(type=GObject.TYPE_PYOBJECT)
    def media_paths(self):
        """This is the list of paths where the media to be displayed may be."""
        return self._media_paths

    @media_paths.setter
    def media_paths(self, value):
        self._media_paths = value

    @GObject.Property(type=bool, default=True)
    def show_badges(self):
        """This is the path to the media file to be displayed."""
        return self._show_badges

    @show_badges.setter
    def show_badges(self, value):
        self._show_badges = value

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

    def _get_preferred_size(self):
        paths = self.media_paths
        if paths:
            path = paths[0]
            return path.width, path.height
        return 0, 0

    def do_get_preferred_width(self, widget):
        size = self._get_preferred_size()
        return size[0], size[0]

    def do_get_preferred_height(self, widget):
        size = self._get_preferred_size()
        return size[1], size[1]

    def do_render(self, cr, widget, background_area, cell_area, flags):
        media_path = resolve_media_path(self.media_paths) if self.media_paths else None
        if not media_path:
            return

        media_width = media_path.width
        media_height = media_path.height
        path = media_path.path
        alpha = 1 if self.is_installed else 100 / 255

        if media_width > 0 and media_height > 0 and path:
            surface = self._get_cached_surface_by_path(widget, path, size=(media_width, media_height))
            if not surface:
                # The default icon needs to be scaled to fill the cell space.
                path = get_default_icon_path((media_width, media_height))
                surface = self._get_cached_surface_by_path(
                    widget, path, size=(media_width, media_height), preserve_aspect_ratio=False
                )
            if surface:
                media_area = self.get_media_area(surface, cell_area)
                self.select_badge_metrics(surface, media_width, media_height)

                cr.save()

                # Adjust context to place media_area at 0,0 and scale it.
                inset_fraction = self._inset_fractions.get(self.game_id) or 0.0 if self.game_id else 0.0
                if inset_fraction > 0:
                    media_area.x += (media_area.width * inset_fraction) / 2
                    media_area.y += (media_area.height * inset_fraction) / 2
                    cr.translate(media_area.x, media_area.y)
                    cr.scale(1 - inset_fraction, 1 - inset_fraction)
                else:
                    cr.translate(media_area.x, media_area.y)

                media_area.x = 0
                media_area.y = 0

                if alpha >= 1:
                    self.render_media(cr, widget, surface, 0, 0)
                    if self.show_badges:
                        self._render_badges(cr, widget, surface, media_area)
                else:
                    cr.push_group()
                    self.render_media(cr, widget, surface, 0, 0)
                    if self.show_badges:
                        self._render_badges(cr, widget, surface, media_area)
                    cr.pop_group_to_source()
                    cr.paint_with_alpha(alpha)
                cr.restore()

                if inset_fraction > 0:
                    # Since we are restoring a scale change _again_ we need
                    # to update the layout with that change too, or the other text
                    # in the view will be broken. So lame.
                    layout = widget.create_pango_layout("")
                    PangoCairo.update_layout(cr, layout)

            # Idle time will wait until the widget has drawn whatever it wants to;
            # we can then discard surfaces we aren't using anymore.
            schedule_at_idle(self.cycle_cache)

    def select_badge_metrics(self, surface, media_width, media_height):
        """Updates fields holding data about the appearance of the badges;
        this sets self.badge_size to None if no badges should be shown at all."""

        def get_badge_icon_size():
            """Returns the size of the badge icons to render, or None to hide them. We check
            width for the smallest size because Dolphin has very thin banners, but we only hide
            badges for icons, not banners."""
            if media_width < 64:
                return None
            if media_height < 128:
                return 16, 16
            if media_height < 256:
                return 24, 24
            return 32, 32

        self.badge_size = get_badge_icon_size()
        on_bright_surface = self.badge_size and GridViewCellRendererImage.is_bright_corner(surface, self.badge_size)

        bright_color = 0.8, 0.8, 0.8
        dark_color = 0.2, 0.2, 0.2
        self.badge_fore_color = dark_color if on_bright_surface else bright_color
        self.badge_back_color = bright_color if on_bright_surface else dark_color

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
                pixel = data[offset : offset + 4]

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

    @staticmethod
    def get_media_area(surface, cell_area):
        """Computes the position of the upper left corner where we will render
        a surface within the cell area."""
        media_area = Gdk.Rectangle()
        width, height = get_surface_size(surface)
        media_area.x = round(cell_area.x + (cell_area.width - width) / 2)  # centered
        media_area.y = round(cell_area.y + cell_area.height - height)  # at bottom of cell
        media_area.width, media_area.height = width, height
        return media_area

    def render_media(self, cr, widget, surface, x, y):
        """Renders the media itself, given the surface containing it
        and the position."""
        width, height = get_surface_size(surface)

        cr.set_source_surface(surface, x, y)
        cr.get_source().set_extend(cairo.Extend.PAD)  # pylint: disable=no-member
        cr.rectangle(x, y, width, height)
        cr.fill()

    def _render_badges(self, cr, widget, surface, media_area):
        self.render_platforms(cr, widget, surface, 0, media_area)

        game_id = self.game_id
        if game_id:
            if self.service:
                game_id = self.service.resolve_game_id(game_id)

            if game_id in MISSING_GAMES.missing_game_ids:
                self.render_text_badge(cr, widget, _("Missing"), 0, media_area.y + media_area.height)

    def render_platforms(self, cr, widget, surface, surface_x, media_area):
        """Renders the stack of platform icons."""
        platform = self.platform
        if platform and self.badge_size:
            icon_paths = self.get_platform_icon_paths(platform)
            if icon_paths:
                self.render_badge_stack(cr, widget, surface, surface_x, icon_paths, media_area)

    @staticmethod
    def get_platform_icon_paths(platform):
        if platform in GridViewCellRendererImage._platform_icon_paths:
            return GridViewCellRendererImage._platform_icon_paths[platform]

        if "," in platform:
            platforms = platform.split(",")  # pylint:disable=no-member
        else:
            platforms = [platform]

        icon_paths = []
        for p in platforms:
            icon_path = get_runtime_icon_path(p + "-symbolic")
            if icon_path:
                icon_paths.append(icon_path)

        GridViewCellRendererImage._platform_icon_paths[platform] = icon_paths
        return icon_paths

    _platform_icon_paths = {}

    def render_badge_stack(self, cr, widget, surface, surface_x, icon_paths, media_area):
        """Renders a vertical stack of badges, placed at the edge of the media, just to the left
        of 'media_area.right'. The icons in icon_paths are drawn from top to bottom, and spaced
        to fit in 'media_area', even if they overlap because of this."""

        badge_width = self.badge_size[0]
        badge_height = self.badge_size[1]
        alpha = self.badge_alpha
        fore_color = self.badge_fore_color
        back_color = self.badge_back_color

        def render_badge(badge_x, badge_y, path):
            cr.rectangle(badge_x, badge_y, badge_width, badge_height)
            cr.set_source_rgba(back_color[0], back_color[1], back_color[2], alpha)
            cr.fill()

            icon = self._get_cached_surface_by_path(widget, path, size=self.badge_size)
            cr.set_source_rgba(fore_color[0], fore_color[1], fore_color[2], alpha)
            cr.mask_surface(icon, badge_x, badge_y)

        media_right = surface_x + get_surface_size(surface)[0]

        x = media_right - badge_width
        spacing = (media_area.height - badge_height * len(icon_paths)) / max(1, len(icon_paths) - 1)
        spacing = min(spacing, 1)
        y_offset = floor(badge_height + spacing)
        y = media_area.y + media_area.height - badge_height - y_offset * (len(icon_paths) - 1)

        for icon_path in icon_paths:
            render_badge(x, y, icon_path)
            y = y + y_offset

    def render_text_badge(self, cr, widget, text, left, bottom):
        """Draws a short text in the lower left corner of the media, in the
        style of a badge."""

        def get_layout():
            """Constructs a layout with the text to draw, but also returns its size
            in pixels. This is boldfaced, but otherwise in the default font."""
            lo = widget.create_pango_layout(text)
            font = lo.get_context().get_font_description()
            font.set_weight(Pango.Weight.BOLD)
            lo.set_font_description(font)
            _, text_bounds = lo.get_extents()
            return lo, text_bounds.width / Pango.SCALE, text_bounds.height / Pango.SCALE

        if self.badge_size:
            alpha = self.badge_alpha
            fore_color = self.badge_fore_color
            back_color = self.badge_back_color

            layout, text_width, text_height = get_layout()

            cr.save()

            # To get the text to be as tall as a badge, we'll scale it
            # with Cairo. Scaling the font size does not work; the font
            # size measures the wrong height for this.
            text_scale = self.badge_size[1] / text_height
            text_height = self.badge_size[1]
            text_width = round(text_width * text_scale)

            cr.rectangle(left, bottom - text_height, text_width + 4, text_height)
            cr.set_source_rgba(back_color[0], back_color[1], back_color[2], alpha)
            cr.fill()

            cr.translate(left + 2, bottom - text_height)
            cr.scale(text_scale, text_scale)
            cr.set_source_rgba(fore_color[0], fore_color[1], fore_color[2], alpha)
            PangoCairo.update_layout(cr, layout)
            PangoCairo.show_layout(cr, layout)

            cr.restore()

            # Looks like we need to make cr.restore() take effect for
            # explicitly, or further text in this cairo context winds up scaled.
            # It must be doing something squirrely with the context that we just
            # spoiled with cr.restore(), and this fixes that.
            PangoCairo.update_layout(cr, layout)

    def clear_cache(self):
        """Discards all cached surfaces; used when some properties are changed."""
        self.cached_surfaces_old.clear()
        self.cached_surfaces_new.clear()

    def cycle_cache(self) -> None:
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

    def _get_cached_surface_by_path(self, widget, path, size, preserve_aspect_ratio=True):
        """This obtains the scaled surface to rander for a given media path; this is cached
        in this render, but we'll clear that cache when the media generation number is changed,
        or certain properties are. We also age surfaces from the cache at idle time after
        rendering."""
        if self.cached_surface_generation != _MEDIA_CACHE_GENERATION_NUMBER:
            self.cached_surface_generation = _MEDIA_CACHE_GENERATION_NUMBER
            self.clear_cache()

        key = widget, path, size, preserve_aspect_ratio

        if key in self.cached_surfaces_new:
            return self.cached_surfaces_new[key]

        if key in self.cached_surfaces_old:
            surface = self.cached_surfaces_old[key]
        else:
            surface = self._get_surface_by_path(widget, path, size, preserve_aspect_ratio)
            if surface:
                # We cache missing surfaces too, but only a successful load trigger
                # cache cycling
                self.cached_surfaces_loaded += 1

        self.cached_surfaces_new[key] = surface
        return surface

    def _get_surface_by_path(self, widget, path, size, preserve_aspect_ratio=True):
        cell_size = size
        scale_factor = widget.get_scale_factor() if widget else 1
        try:
            return get_scaled_surface_by_path(
                path, cell_size, scale_factor, preserve_aspect_ratio=preserve_aspect_ratio
            )
        except Exception as ex:
            # We need to survive nasty data in the media files, so the user can replace
            # them.
            logger.exception("Unable to load media '%s': %s", path, ex)
            return None


def _on_media_cached_invalidated() -> None:
    # Increment a counter, so we can passively detect when the media cache is invalid
    # without a per-object handler. We have no way to unregister that handler, but we never
    # need to unregister this global one.
    global _MEDIA_CACHE_GENERATION_NUMBER
    _MEDIA_CACHE_GENERATION_NUMBER += 1


MEDIA_CACHE_INVALIDATED.register(_on_media_cached_invalidated)
