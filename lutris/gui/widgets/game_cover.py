"""Game cover tile widget used by GameGridView.

Port of GridViewCellRendererImage's snapshot drawing to a Gtk.Widget, so
Gtk.GridView's Gtk.SignalListItemFactory can place one per cell.
"""

# pylint: disable=no-member
from gettext import gettext as _
from math import floor
from typing import TypeAlias

from gi.repository import Gdk, Graphene, Gtk, Pango

from lutris.gui.widgets import NotificationRegistration
from lutris.gui.widgets.utils import (
    MEDIA_CACHE_INVALIDATED,
    ScaledTexture,
    get_default_icon_path,
    get_pixbuf_by_path,
    get_runtime_icon_path,
)
from lutris.services.service_media import resolve_media_path
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES

# (path, (width, height), preserve_aspect_ratio, corner_size_physical, scale_factor)
_TextureCacheKey: TypeAlias = tuple[str, tuple[float, float], bool, tuple[int, int] | None, int]


class GameCoverWidget(Gtk.Widget):
    """Snapshot-rendered game media tile with platform/missing badges.

    Layout is a single fixed rectangle at (0, 0, expected_w, expected_h).
    The owner (GameGridView) calls set_data() on bind; the launch-bounce
    animation is driven by toggling the `.launching` CSS class on the widget.
    """

    _platform_icon_paths: dict[str, list[str]] = {}

    # Cover textures are cached per-widget (see _texture in __init__) — measurement
    # showed that during normal scroll the GridView pool already covers the only
    # reuse case the old class-level cache helped with, so a class-level cache was
    # paying complexity for ~zero hit rate. Badge textures, on the other hand, are
    # heavily shared (every cover for the same platform draws the same badge), so
    # they keep a simple class-level memo.
    _badge_cache: dict[str, Gdk.Texture | None] = {}

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(False)
        self.set_vexpand(False)

        self._game_id: str | None = None
        self._service = None
        self._media_paths: list = []
        self._show_platform_badges = True
        self._show_missing_badge = True
        self._platform: str | None = None
        self._is_installed = True
        self._expected_width = 0
        self._expected_height = 0
        # Per-widget texture cache: holds the most recent ScaledTexture this
        # widget has rendered. Refreshed in _get_texture when the key changes
        # (different game/size/scale) and cleared by _on_media_cache_invalidated
        # while realized so an updated media file repaints without waiting
        # for a scroll or rebind.
        self._texture: ScaledTexture | None = None
        self._texture_key: _TextureCacheKey | None = None
        self._media_cache_registration: NotificationRegistration | None = None
        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)

        self.badge_size: tuple[int, int] | None = None
        self.badge_alpha = 0.6
        self.badge_fore_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self.badge_back_color: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # ---- Data binding ------------------------------------------------

    def set_data(
        self,
        game_id: str | None,
        service,
        media_paths,
        platform: str | None,
        is_installed: bool,
        show_platform_badges: bool,
        show_missing_badge: bool,
    ) -> None:
        """Each badge type is gated independently: the list view always
        suppresses platform badges (rendered as a separate column), while
        both views respect the user's "show badges" setting for the
        missing-game indicator."""
        self._game_id = game_id
        self._service = service
        self._media_paths = media_paths or []
        self._platform = platform
        self._is_installed = bool(is_installed)
        self._show_platform_badges = bool(show_platform_badges)
        self._show_missing_badge = bool(show_missing_badge)
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
    def game_id(self) -> str | None:
        return self._game_id

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

        entry = self._get_texture(path, size=(media_width, media_height), corner_size_physical=corner_physical)
        if not entry:
            entry = self._get_texture(
                get_default_icon_path((media_width, media_height)),
                size=(media_width, media_height),
                preserve_aspect_ratio=False,
                corner_size_physical=corner_physical,
            )
        if not entry:
            return

        media_area = self._get_media_area(entry.logical_size, cell_area)
        self._select_badge_metrics(entry.corner_is_bright, badge_size)

        alpha = 1.0 if self._is_installed else 100 / 255

        if alpha < 1.0:
            snapshot.push_opacity(alpha)

        texture_bounds = Graphene.Rect()
        texture_bounds.init(media_area.x, media_area.y, media_area.width, media_area.height)
        snapshot.append_texture(entry.texture, texture_bounds)

        self._snapshot_badges(snapshot, media_area)

        if alpha < 1.0:
            snapshot.pop()

    def do_measure(self, orientation, for_size):  # type: ignore[override]
        if orientation == Gtk.Orientation.HORIZONTAL:
            size = self._expected_width
        else:
            size = self._expected_height
        return size, size, -1, -1

    # ---- Badge helpers (ported) --------------------------------------

    @staticmethod
    def _compute_badge_size(media_width: float, media_height: float) -> tuple[int, int] | None:
        if media_width < 64:
            return None
        if media_height < 128:
            return 16, 16
        if media_height < 256:
            return 24, 24
        return 32, 32

    def _select_badge_metrics(self, corner_is_bright: bool, badge_size: tuple[int, int] | None) -> None:
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
        media_area.y = round(cell_area.y + (cell_area.height - height) / 2)
        media_area.width, media_area.height = width, height
        return media_area

    def _snapshot_badges(self, snapshot, media_area) -> None:
        if self._show_platform_badges:
            self._snapshot_platform_badges(snapshot, media_area)
        if self._show_missing_badge:
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

            icon_texture = self._get_badge_texture(icon_path)
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
    def _get_platform_icon_paths(cls, platform: str) -> list[str]:
        cached = cls._platform_icon_paths.get(platform)
        if cached is not None:
            return cached

        if "," in platform:
            platforms = platform.split(",")
        else:
            platforms = [platform]

        icon_paths: list[str] = []
        for p in platforms:
            icon_path = get_runtime_icon_path(p + "-symbolic")
            if icon_path:
                icon_paths.append(icon_path)

        cls._platform_icon_paths[platform] = icon_paths
        return icon_paths

    # ---- Texture loading --------------------------------------------

    def _get_texture(
        self,
        path: str,
        size: tuple[float, float],
        preserve_aspect_ratio: bool = True,
        corner_size_physical: tuple[int, int] | None = None,
    ) -> ScaledTexture | None:
        """Return this widget's ScaledTexture for ``path`` at ``size``,
        reloading lazily when the cache key changes or the per-widget
        cache has been invalidated."""
        scale_factor = self.get_scale_factor() or 1
        key: _TextureCacheKey = (path, size, preserve_aspect_ratio, corner_size_physical, scale_factor)
        if self._texture is None or self._texture_key != key:
            try:
                self._texture = ScaledTexture.from_path(
                    path,
                    size,
                    scale_factor,
                    preserve_aspect_ratio=preserve_aspect_ratio,
                    corner_size_physical=corner_size_physical,
                )
            except Exception as ex:
                logger.exception("Unable to load media '%s': %s", path, ex)
                self._texture = None
            self._texture_key = key
        return self._texture

    # ---- MEDIA_CACHE_INVALIDATED lifecycle --------------------------

    def _on_realize(self, _widget: Gtk.Widget) -> None:
        # Register only while realized so the notification source doesn't
        # keep an unrealized cover alive via its strong handler reference.
        if self._media_cache_registration is None:
            self._media_cache_registration = MEDIA_CACHE_INVALIDATED.register(self._on_media_cache_invalidated)

    def _on_unrealize(self, _widget: Gtk.Widget) -> None:
        if self._media_cache_registration is not None:
            self._media_cache_registration.unregister()
            self._media_cache_registration = None

    def _on_media_cache_invalidated(self) -> None:
        self._texture = None
        self._texture_key = None
        self.queue_draw()

    @classmethod
    def _get_badge_texture(cls, path: str) -> Gdk.Texture | None:
        if path in cls._badge_cache:
            return cls._badge_cache[path]
        try:
            pixbuf = get_pixbuf_by_path(path)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf) if pixbuf else None
        except Exception as ex:
            logger.exception("Unable to load badge icon '%s': %s", path, ex)
            texture = None
        cls._badge_cache[path] = texture
        return texture


def _make_rgba(color: tuple[float, float, float], alpha: float) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = color[0], color[1], color[2], alpha
    return rgba


def _color_matrix_tint(color: tuple[float, float, float], alpha: float) -> tuple[Graphene.Matrix, Graphene.Vec4]:
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


MEDIA_CACHE_INVALIDATED.register(GameCoverWidget._badge_cache.clear)
