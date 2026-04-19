"""Game cover tile widget used by GameGridView.

Port of GridViewCellRendererImage's snapshot drawing to a Gtk.Widget, so
Gtk.GridView's Gtk.SignalListItemFactory can place one per cell.
"""

# pylint: disable=no-member
from gettext import gettext as _
from math import floor
from typing import TypeAlias

from gi.repository import Gdk, Graphene, Gtk, Pango

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

# (path, (width, height), preserve_aspect_ratio, corner_size_physical, scale_factor)
_TextureCacheKey: TypeAlias = tuple[str, tuple[float, float], bool, "tuple[int, int] | None", int]
# (texture, logical_size, corner_is_bright) — see get_scaled_texture_by_path.
_TextureCacheEntry: TypeAlias = "tuple[Gdk.Texture, tuple[float, float], bool] | None"


class GameCoverWidget(Gtk.Widget):
    """Snapshot-rendered game media tile with platform/missing badges.

    Layout is a single fixed rectangle at (0, 0, expected_w, expected_h).
    The owner (GameGridView) calls set_data() on bind and set_inset_fraction()
    during the launch-bounce animation.
    """

    _platform_icon_paths: "dict[str, list[str]]" = {}

    # Texture caches are shared across all GameCoverWidget instances. Gtk.GridView
    # recycles widgets aggressively during scroll: a given widget gets rebound to
    # different games, so a per-instance cache would miss on every rebind. The old
    # GTK3 code used a single CellRenderer with one shared cache — this mirrors it.
    _cached_textures_new: "dict[_TextureCacheKey, _TextureCacheEntry]" = {}
    _cached_textures_old: "dict[_TextureCacheKey, _TextureCacheEntry]" = {}
    _cached_badge_textures_new: "dict[str, Gdk.Texture | None]" = {}
    _cached_badge_textures_old: "dict[str, Gdk.Texture | None]" = {}
    _cached_items_loaded: int = 0
    _cached_surface_generation: int = 0

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(False)
        self.set_vexpand(False)

        self._game_id: "str | None" = None
        self._service = None
        self._media_paths: list = []
        self._show_badges = True
        self._platform: "str | None" = None
        self._is_installed = True
        self._inset_fraction = 0.0
        self._expected_width = 0
        self._expected_height = 0

        self.badge_size: "tuple[int, int] | None" = None
        self.badge_alpha = 0.6
        self.badge_fore_color: "tuple[float, float, float]" = (1.0, 1.0, 1.0)
        self.badge_back_color: "tuple[float, float, float]" = (0.0, 0.0, 0.0)

    # ---- Data binding ------------------------------------------------

    def set_data(
        self,
        game_id: "str | None",
        service,
        media_paths,
        platform: "str | None",
        is_installed: bool,
        show_badges: bool,
    ) -> None:
        self._game_id = game_id
        self._service = service
        self._media_paths = media_paths or []
        self._platform = platform
        self._is_installed = bool(is_installed)
        self._show_badges = bool(show_badges)
        self.queue_draw()

    def set_expected_size(self, width: int, height: int) -> None:
        width = int(width)
        height = int(height)
        if width == self._expected_width and height == self._expected_height:
            return
        self._expected_width = width
        self._expected_height = height
        self.set_size_request(width, height)
        self.queue_resize()

    @property
    def game_id(self) -> "str | None":
        return self._game_id

    def set_inset_fraction(self, fraction: float) -> None:
        fraction = max(0.0, min(fraction, 1.0))
        if fraction != self._inset_fraction:
            self._inset_fraction = fraction
            self.queue_draw()

    def is_library_view(self) -> bool:
        """True when drawing library tiles (no service attached).

        Library tiles center the media vertically in the cell; service tiles
        align it to the bottom — matches the old cell renderer behaviour."""
        return self._service is None

    # ---- Snapshot rendering (ported from GridViewCellRendererImage) --

    def do_snapshot(self, snapshot) -> None:  # type: ignore[override]
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        media_path = resolve_media_path(self._media_paths) if self._media_paths else None
        if not media_path:
            return

        media_width = media_path.width
        media_height = media_path.height
        path = media_path.path
        if media_width <= 0 or media_height <= 0 or not path:
            return

        cell_area = Gdk.Rectangle()
        cell_area.x = 0
        cell_area.y = 0
        cell_area.width = width
        cell_area.height = height

        badge_size = self._compute_badge_size(media_width, media_height)
        corner_physical = None
        if badge_size:
            device_scale = self.get_scale_factor() or 1
            corner_physical = (int(badge_size[0] * device_scale), int(badge_size[1] * device_scale))

        entry = self._get_cached_texture_by_path(
            path, size=(media_width, media_height), corner_size_physical=corner_physical
        )
        if not entry:
            path = get_default_icon_path((media_width, media_height))
            entry = self._get_cached_texture_by_path(
                path,
                size=(media_width, media_height),
                preserve_aspect_ratio=False,
                corner_size_physical=corner_physical,
            )
        if not entry:
            schedule_at_idle(self.cycle_cache)
            return

        texture, logical_size, corner_is_bright = entry
        media_area = self._get_media_area(logical_size, cell_area)
        self._select_badge_metrics(corner_is_bright, badge_size)

        inset_fraction = self._inset_fraction
        alpha = 1.0 if self._is_installed else 100 / 255

        if alpha < 1.0:
            snapshot.push_opacity(alpha)

        # Inset animation: scale the whole subtree (media + badges) around the
        # media centre so badges bounce along with the image.
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

        if self._show_badges:
            self._snapshot_badges(snapshot, media_area)

        if inset_fraction > 0:
            snapshot.restore()

        if alpha < 1.0:
            snapshot.pop()

        schedule_at_idle(self.cycle_cache)

    def do_measure(self, orientation, for_size):  # type: ignore[override]
        if orientation == Gtk.Orientation.HORIZONTAL:
            size = self._expected_width
        else:
            size = self._expected_height
        return size, size, -1, -1

    # ---- Badge helpers (ported) --------------------------------------

    @staticmethod
    def _compute_badge_size(media_width: float, media_height: float) -> "tuple[int, int] | None":
        if media_width < 64:
            return None
        if media_height < 128:
            return 16, 16
        if media_height < 256:
            return 24, 24
        return 32, 32

    def _select_badge_metrics(self, corner_is_bright: bool, badge_size: "tuple[int, int] | None") -> None:
        self.badge_size = badge_size
        on_bright_surface = bool(badge_size) and corner_is_bright

        bright_color = (0.8, 0.8, 0.8)
        dark_color = (0.2, 0.2, 0.2)
        self.badge_fore_color = dark_color if on_bright_surface else bright_color
        self.badge_back_color = bright_color if on_bright_surface else dark_color

    def _get_media_area(self, logical_size, cell_area) -> Gdk.Rectangle:
        media_area = Gdk.Rectangle()
        width, height = logical_size

        media_area.x = round(cell_area.x + (cell_area.width - width) / 2)
        if self.is_library_view():
            media_area.y = round(cell_area.y + (cell_area.height - height) / 2)
        else:
            media_area.y = round(cell_area.y + cell_area.height - height)

        media_area.width, media_area.height = width, height
        return media_area

    def _snapshot_badges(self, snapshot, media_area) -> None:
        self._snapshot_platform_badges(snapshot, media_area)
        self._snapshot_missing_badge(snapshot, media_area)

    def _snapshot_platform_badges(self, snapshot, media_area) -> None:
        platform = self._platform
        if not platform or not self.badge_size:
            return
        icon_paths = self._get_platform_icon_paths(platform)
        if not icon_paths:
            return

        badge_width, badge_height = self.badge_size
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

    def _snapshot_missing_badge(self, snapshot, media_area) -> None:
        game_id = self._game_id
        if not game_id or not self.badge_size:
            return
        if self._service:
            game_id = self._service.resolve_game_id(game_id)
        if game_id not in MISSING_GAMES.missing_game_ids:
            return

        layout, text_width, text_height, text_scale = self._build_missing_layout()
        alpha = self.badge_alpha
        left = media_area.x
        top = media_area.y + media_area.height - text_height

        back_rect = Graphene.Rect()
        back_rect.init(left, top, text_width + 4, text_height)
        snapshot.append_color(_make_rgba(self.badge_back_color, alpha), back_rect)

        snapshot.save()
        text_origin = Graphene.Point()
        text_origin.init(left + 2, top)
        snapshot.translate(text_origin)
        if text_scale != 1.0:
            snapshot.scale(text_scale, text_scale)
        snapshot.append_layout(layout, _make_rgba(self.badge_fore_color, alpha))
        snapshot.restore()

    def _build_missing_layout(self):
        text = _("Missing")
        layout = self.create_pango_layout(text)
        font = layout.get_context().get_font_description()
        font.set_weight(Pango.Weight.BOLD)
        layout.set_font_description(font)
        _ink_rect, text_bounds = layout.get_extents()
        raw_width = text_bounds.width / Pango.SCALE
        raw_height = text_bounds.height / Pango.SCALE
        assert self.badge_size is not None
        text_scale = self.badge_size[1] / raw_height if raw_height else 1.0
        return layout, round(raw_width * text_scale), self.badge_size[1], text_scale

    @classmethod
    def _get_platform_icon_paths(cls, platform: str) -> "list[str]":
        cached = cls._platform_icon_paths.get(platform)
        if cached is not None:
            return cached

        if "," in platform:
            platforms = platform.split(",")
        else:
            platforms = [platform]

        icon_paths: "list[str]" = []
        for p in platforms:
            icon_path = get_runtime_icon_path(p + "-symbolic")
            if icon_path:
                icon_paths.append(icon_path)

        cls._platform_icon_paths[platform] = icon_paths
        return icon_paths

    # ---- Cache lifecycle (ported) ------------------------------------

    @classmethod
    def clear_cache(cls) -> None:
        cls._cached_textures_old.clear()
        cls._cached_textures_new.clear()
        cls._cached_badge_textures_old.clear()
        cls._cached_badge_textures_new.clear()

    @classmethod
    def cycle_cache(cls) -> None:
        """Discard cached items not touched since the last cycle.

        Called at idle time after rendering, so entries used during the frame
        we just drew are preserved (smooth scrolling) and stale entries are
        freed on the next idle tick. Operates on the class-level shared cache."""
        if cls._cached_items_loaded > 0:
            cls._cached_textures_old = cls._cached_textures_new
            cls._cached_textures_new = {}
            cls._cached_badge_textures_old = cls._cached_badge_textures_new
            cls._cached_badge_textures_new = {}
            cls._cached_items_loaded = 0

    @classmethod
    def _check_cache_generation(cls) -> None:
        if cls._cached_surface_generation != _MEDIA_CACHE_GENERATION_NUMBER:
            cls._cached_surface_generation = _MEDIA_CACHE_GENERATION_NUMBER
            cls.clear_cache()

    def _get_cached_texture_by_path(
        self,
        path: str,
        size: "tuple[float, float]",
        preserve_aspect_ratio: bool = True,
        corner_size_physical: "tuple[int, int] | None" = None,
    ) -> "_TextureCacheEntry":
        cls = type(self)
        cls._check_cache_generation()

        scale_factor = self.get_scale_factor() or 1
        key: "_TextureCacheKey" = (path, size, preserve_aspect_ratio, corner_size_physical, scale_factor)

        if key in cls._cached_textures_new:
            return cls._cached_textures_new[key]

        if key in cls._cached_textures_old:
            entry = cls._cached_textures_old[key]
        else:
            entry = self._load_texture(path, size, preserve_aspect_ratio, corner_size_physical, scale_factor)
            if entry:
                cls._cached_items_loaded += 1

        cls._cached_textures_new[key] = entry
        return entry

    @staticmethod
    def _load_texture(
        path: str,
        size: "tuple[float, float]",
        preserve_aspect_ratio: bool,
        corner_size_physical: "tuple[int, int] | None",
        scale_factor: int,
    ) -> "_TextureCacheEntry":
        try:
            return get_scaled_texture_by_path(
                path,
                size,
                scale_factor,
                preserve_aspect_ratio=preserve_aspect_ratio,
                corner_size_physical=corner_size_physical,
            )
        except Exception as ex:
            logger.exception("Unable to load media '%s': %s", path, ex)
            return None

    def _get_cached_badge_texture(self, path: str) -> "Gdk.Texture | None":
        cls = type(self)
        cls._check_cache_generation()

        if path in cls._cached_badge_textures_new:
            return cls._cached_badge_textures_new[path]

        texture: "Gdk.Texture | None"
        if path in cls._cached_badge_textures_old:
            texture = cls._cached_badge_textures_old[path]
        else:
            try:
                pixbuf = get_pixbuf_by_path(path)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf) if pixbuf else None
            except Exception as ex:
                logger.exception("Unable to load badge icon '%s': %s", path, ex)
                texture = None
            if texture is not None:
                cls._cached_items_loaded += 1

        cls._cached_badge_textures_new[path] = texture
        return texture


def _make_rgba(color: "tuple[float, float, float]", alpha: float) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = color[0], color[1], color[2], alpha
    return rgba


def _color_matrix_tint(color: "tuple[float, float, float]", alpha: float) -> "tuple[Graphene.Matrix, Graphene.Vec4]":
    """(matrix, offset) pair for snapshot.push_color_matrix() that tints an
    input texture so its RGB becomes `color` and its alpha is scaled by `alpha`.

    Applied column-major as out = matrix * in + offset; we zero out RGB input
    contributions and scale alpha through, supplying the fixed foreground via
    offset. Symbolic icons are a black-on-alpha mask, so this reproduces the
    old cairo mask_surface() tinting."""
    matrix = Graphene.Matrix()
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
    global _MEDIA_CACHE_GENERATION_NUMBER
    _MEDIA_CACHE_GENERATION_NUMBER += 1


MEDIA_CACHE_INVALIDATED.register(_on_media_cached_invalidated)
