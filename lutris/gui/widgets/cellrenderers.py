# pylint: disable=no-member
# pylint:disable=using-constant-test
# pylint:disable=comparison-with-callable
from gettext import gettext as _
from math import floor

from gi.repository import Gdk, GObject, Graphene, Gtk, Pango

from lutris.gui.widgets.utils import (
    MEDIA_CACHE_INVALIDATED,
    get_default_icon_path,
    get_pixbuf_by_path,
    get_runtime_icon_path,
    get_scaled_texture_by_path,
)
from lutris.services.service_media import resolve_media_path
from lutris.util.jobs import schedule_at_idle
from lutris.util.log import logger
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
        # Cache for the main media as Gdk.Texture tuples: (texture, logical_size, corner_is_bright).
        self.cached_textures_new = {}
        self.cached_textures_old = {}
        # Cache for small Gdk.Textures used by snapshot-drawn badges, keyed by icon path.
        self.cached_badge_textures_new = {}
        self.cached_badge_textures_old = {}
        self.cached_items_loaded = 0
        self.cached_surface_generation = 0
        self.badge_size = 0, 0
        self.badge_alpha = 0.6
        self.badge_fore_color = 1, 1, 1
        self.badge_back_color = 0, 0, 0
        self._inset_fractions = {}
        self._expected_width = None
        self._expected_height = None

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

    def is_library_view(self):
        """Returns True if this is rendering for the library view (not a service view)"""
        return self.service is None

    def set_expected_size(self, width, height):
        """Sets the expected dimensions for library view based on the selected zoom level"""
        self._expected_width = width
        self._expected_height = height

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
        if self.is_library_view() and self._expected_width:
            return self._expected_width, self._expected_width
        size = self._get_preferred_size()
        return size[0], size[0]

    def do_get_preferred_height(self, widget):
        if self.is_library_view() and self._expected_height:
            return self._expected_height, self._expected_height
        size = self._get_preferred_size()
        return size[1], size[1]

    def do_snapshot(self, snapshot, widget, background_area, cell_area, flags):
        """GTK 4 snapshot entry point.

        The media image goes through snapshot.append_texture() so GSK can composite
        it on the GPU."""
        media_path = resolve_media_path(self.media_paths) if self.media_paths else None
        if not media_path:
            return

        media_width = media_path.width
        media_height = media_path.height
        path = media_path.path
        if media_width <= 0 or media_height <= 0 or not path:
            return

        badge_size = self._compute_badge_size(media_width, media_height)
        corner_physical = None
        if badge_size:
            device_scale = widget.get_scale_factor() if widget else 1
            corner_physical = (int(badge_size[0] * device_scale), int(badge_size[1] * device_scale))

        entry = self._get_cached_texture_by_path(
            widget, path, size=(media_width, media_height), corner_size_physical=corner_physical
        )
        if not entry:
            path = get_default_icon_path((media_width, media_height))
            entry = self._get_cached_texture_by_path(
                widget,
                path,
                size=(media_width, media_height),
                preserve_aspect_ratio=False,
                corner_size_physical=corner_physical,
            )
        if not entry:
            schedule_at_idle(self.cycle_cache)
            return

        texture, logical_size, corner_is_bright = entry
        media_area = self.get_media_area(logical_size, cell_area)
        self.select_badge_metrics(corner_is_bright, badge_size)

        inset_fraction = self._inset_fractions.get(self.game_id, 0.0) if self.game_id else 0.0
        alpha = 1.0 if self.is_installed else 100 / 255

        if alpha < 1.0:
            snapshot.push_opacity(alpha)

        # Inset animation: scale the whole subtree (media + badges) about the media centre so
        # badges bounce along with the image. Now that badges are emitted as pure snapshot
        # primitives, there's no append_cairo rasterization-under-transform to work around.
        if inset_fraction > 0:
            scale = 1 - inset_fraction
            cx = media_area.x + media_area.width / 2
            cy = media_area.y + media_area.height / 2
            snapshot.save()
            forward = Graphene.Point()
            forward.init(cx, cy)
            snapshot.translate(forward)
            snapshot.scale(scale, scale)
            back = Graphene.Point()
            back.init(-cx, -cy)
            snapshot.translate(back)

        texture_bounds = Graphene.Rect()
        texture_bounds.init(media_area.x, media_area.y, media_area.width, media_area.height)
        snapshot.append_texture(texture, texture_bounds)

        if self.show_badges:
            self._snapshot_badges(snapshot, widget, media_area)

        if inset_fraction > 0:
            snapshot.restore()

        if alpha < 1.0:
            snapshot.pop()

        # Idle time will wait until the widget has drawn whatever it wants to;
        # we can then discard cached items we aren't using anymore.
        schedule_at_idle(self.cycle_cache)

    @staticmethod
    def _compute_badge_size(media_width: float, media_height: float) -> tuple[int, int] | None:
        """Returns the size of badge icons to render, or None to hide them. We check
        width for the smallest size because Dolphin has very thin banners, but we only hide
        badges for icons, not banners."""
        if media_width < 64:
            return None
        if media_height < 128:
            return 16, 16
        if media_height < 256:
            return 24, 24
        return 32, 32

    def select_badge_metrics(self, corner_is_bright: bool, badge_size: tuple[int, int] | None) -> None:
        """Updates fields holding data about the appearance of the badges;
        this sets self.badge_size to None if no badges should be shown at all."""
        self.badge_size = badge_size
        on_bright_surface = bool(badge_size) and corner_is_bright

        bright_color = 0.8, 0.8, 0.8
        dark_color = 0.2, 0.2, 0.2
        self.badge_fore_color = dark_color if on_bright_surface else bright_color
        self.badge_back_color = bright_color if on_bright_surface else dark_color

    def get_media_area(self, logical_size, cell_area):
        """Computes the position of the upper left corner where we will render
        the media within the cell area."""
        media_area = Gdk.Rectangle()
        width, height = logical_size

        # Horizontal centering (same for both library and service views)
        media_area.x = round(cell_area.x + (cell_area.width - width) / 2)

        if self.is_library_view():
            # For library view, center vertically within cell height
            media_area.y = round(cell_area.y + (cell_area.height - height) / 2)
        else:
            # Service views: bottom-aligned
            media_area.y = round(cell_area.y + cell_area.height - height)

        media_area.width, media_area.height = width, height
        return media_area

    def _snapshot_badges(self, snapshot, widget, media_area) -> None:
        """Emits badge nodes directly into the snapshot. Any enclosing snapshot transform
        (e.g. the inset-animation scale) is picked up for free."""
        self._snapshot_platform_badges(snapshot, media_area)
        self._snapshot_missing_badge(snapshot, widget, media_area)

    def _snapshot_platform_badges(self, snapshot, media_area) -> None:
        platform = self.platform
        if not platform or not self.badge_size:
            return
        icon_paths = self.get_platform_icon_paths(platform)
        if not icon_paths:
            return

        badge_width = self.badge_size[0]
        badge_height = self.badge_size[1]
        alpha = self.badge_alpha
        back_color = _make_rgba(self.badge_back_color, alpha)
        fore_matrix, fore_offset = _color_matrix_tint(self.badge_fore_color, alpha)

        spacing = (media_area.height - badge_height * len(icon_paths)) / max(1, len(icon_paths) - 1)
        spacing = min(spacing, 1)
        y_offset = floor(badge_height + spacing)
        x = media_area.x + media_area.width - badge_width
        y = media_area.y + media_area.height - badge_height - y_offset * (len(icon_paths) - 1)

        for icon_path in icon_paths:
            rect = Graphene.Rect()
            rect.init(x, y, badge_width, badge_height)
            snapshot.append_color(back_color, rect)

            icon_texture = self._get_cached_badge_texture(icon_path)
            if icon_texture is not None:
                snapshot.push_color_matrix(fore_matrix, fore_offset)
                snapshot.append_texture(icon_texture, rect)
                snapshot.pop()

            y = y + y_offset

    def _snapshot_missing_badge(self, snapshot, widget, media_area) -> None:
        game_id = self.game_id
        if not game_id or not self.badge_size:
            return
        if self.service:
            game_id = self.service.resolve_game_id(game_id)
        if game_id not in MISSING_GAMES.missing_game_ids:
            return

        layout, text_width, text_height, text_scale = self._build_missing_layout(widget)
        alpha = self.badge_alpha
        left = media_area.x
        top = media_area.y + media_area.height - text_height

        back_rect = Graphene.Rect()
        back_rect.init(left, top, text_width + 4, text_height)
        snapshot.append_color(_make_rgba(self.badge_back_color, alpha), back_rect)

        # Pango layout renders at its native size; scale the snapshot to make it badge-tall,
        # matching the Cairo-era behaviour. Scaling the font size measures the wrong height.
        snapshot.save()
        text_origin = Graphene.Point()
        text_origin.init(left + 2, top)
        snapshot.translate(text_origin)
        if text_scale != 1.0:
            snapshot.scale(text_scale, text_scale)
        snapshot.append_layout(layout, _make_rgba(self.badge_fore_color, alpha))
        snapshot.restore()

    def _build_missing_layout(self, widget):
        """Builds the Pango layout for the 'Missing' label and returns (layout, width, height)
        where width/height are in logical pixels and scaled to match self.badge_size[1]."""
        text = _("Missing")
        layout = widget.create_pango_layout(text)
        font = layout.get_context().get_font_description()
        font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font)
        _ink_rect, text_bounds = layout.get_extents()
        raw_width = text_bounds.width / Pango.SCALE
        raw_height = text_bounds.height / Pango.SCALE
        # Scale text so its rendered height matches the badge height (same as before; scaling
        # the font size measures the wrong height). text_scale is applied at render time by
        # the snapshot transform.
        text_scale = self.badge_size[1] / raw_height if raw_height else 1.0
        return layout, round(raw_width * text_scale), self.badge_size[1], text_scale

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

    def clear_cache(self):
        """Discards all cached textures; used when some properties are changed."""
        self.cached_textures_old.clear()
        self.cached_textures_new.clear()
        self.cached_badge_textures_old.clear()
        self.cached_badge_textures_new.clear()

    def cycle_cache(self) -> None:
        """Is the key cache size control trick. When called, the items cached or used
        since the last call are preserved, but those not touched are discarded.

        We call this at idle time after rendering a cell; this should keep all the items
        rendered at that time, so during scrolling the visible media are kept and scrolling is smooth.
        At other times we may discard almost all items, saving memory.

        We skip clearing anything if no items have been loaded; this happens if drawing was
        serviced entirely from cache. GTK may have redrawn just one image or something, so
        let's not disturb the cache for that."""
        if self.cached_items_loaded > 0:
            self.cached_textures_old = self.cached_textures_new
            self.cached_textures_new = {}
            self.cached_badge_textures_old = self.cached_badge_textures_new
            self.cached_badge_textures_new = {}
            self.cached_items_loaded = 0

    def _check_cache_generation(self) -> None:
        if self.cached_surface_generation != _MEDIA_CACHE_GENERATION_NUMBER:
            self.cached_surface_generation = _MEDIA_CACHE_GENERATION_NUMBER
            self.clear_cache()

    def _get_cached_texture_by_path(self, widget, path, size, preserve_aspect_ratio=True, corner_size_physical=None):
        """Obtains the scaled Gdk.Texture for a given media path, bundled with its logical size
        and a corner-brightness flag. Cached like _get_cached_surface_by_path; cycled together."""
        self._check_cache_generation()

        key = widget, path, size, preserve_aspect_ratio, corner_size_physical

        if key in self.cached_textures_new:
            return self.cached_textures_new[key]

        if key in self.cached_textures_old:
            entry = self.cached_textures_old[key]
        else:
            entry = self._get_texture_by_path(widget, path, size, preserve_aspect_ratio, corner_size_physical)
            if entry:
                self.cached_items_loaded += 1

        self.cached_textures_new[key] = entry
        return entry

    def _get_texture_by_path(self, widget, path, size, preserve_aspect_ratio, corner_size_physical):
        scale_factor = widget.get_scale_factor() if widget else 1
        try:
            return get_scaled_texture_by_path(
                path,
                size,
                scale_factor,
                preserve_aspect_ratio=preserve_aspect_ratio,
                corner_size_physical=corner_size_physical,
            )
        except Exception as ex:
            # We need to survive nasty data in the media files, so the user can replace them.
            logger.exception("Unable to load media '%s': %s", path, ex)
            return None

    def _get_cached_badge_texture(self, path):
        """Returns a Gdk.Texture for a badge icon at 'path', or None if it can't be loaded.
        Badge icons are small and reused across cells, so we cache them keyed by path only
        and let the GPU scale them to the badge rect when they're emitted."""
        self._check_cache_generation()

        if path in self.cached_badge_textures_new:
            return self.cached_badge_textures_new[path]

        if path in self.cached_badge_textures_old:
            texture = self.cached_badge_textures_old[path]
        else:
            try:
                pixbuf = get_pixbuf_by_path(path)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf) if pixbuf else None
            except Exception as ex:
                logger.exception("Unable to load badge icon '%s': %s", path, ex)
                texture = None
            if texture is not None:
                self.cached_items_loaded += 1

        self.cached_badge_textures_new[path] = texture
        return texture


def _make_rgba(color: tuple[float, float, float], alpha: float) -> Gdk.RGBA:
    """Builds a Gdk.RGBA from an (r, g, b) tuple and a separate alpha value."""
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = color[0], color[1], color[2], alpha
    return rgba


def _color_matrix_tint(color: tuple[float, float, float], alpha: float) -> tuple[Graphene.Matrix, Graphene.Vec4]:
    """Returns a (matrix, offset) pair for snapshot.push_color_matrix() that tints an input
    texture so its RGB becomes the given 'color' and its alpha becomes (input_alpha * alpha).

    Applied as pixel_rgba = matrix * pixel_rgba + offset (column-major). We zero out all
    input-RGB contributions and scale input-alpha into the output alpha channel; the offset
    supplies the fixed foreground colour. Symbolic icons are effectively a black-on-alpha
    mask, so this reproduces the cairo `mask_surface` behaviour used previously."""
    matrix = Graphene.Matrix()
    # Column-major: 12 zeros, then column 3 = (0, 0, 0, alpha).
    matrix.init_from_float(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            alpha,
        ]
    )
    offset = Graphene.Vec4()
    offset.init(color[0], color[1], color[2], 0.0)
    return matrix, offset


def _on_media_cached_invalidated() -> None:
    # Increment a counter, so we can passively detect when the media cache is invalid
    # without a per-object handler. We have no way to unregister that handler, but we never
    # need to unregister this global one.
    global _MEDIA_CACHE_GENERATION_NUMBER
    _MEDIA_CACHE_GENERATION_NUMBER += 1


MEDIA_CACHE_INVALIDATED.register(_on_media_cached_invalidated)
