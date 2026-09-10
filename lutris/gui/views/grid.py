"""Grid view for the main window.

Tiles are real widget cards (artwork, captions, badges) inside a FlowBox,
so they are styled by plain CSS exactly like the rest of the application.
The public surface (paths as Gtk.TreePath, game-selected/game-activated
signals, show_badges, hide_text) is unchanged from the IconView era.
"""

# pylint: disable=no-member
from gettext import gettext as _

import cairo
from gi.repository import Gdk, Gtk

from lutris import settings
from lutris.database import categories as categories_db
from lutris.gui.views import COL_ID, COL_INSTALLED, COL_MEDIA_PATHS, COL_NAME, COL_PLATFORM, COL_RUNNER_HUMAN_NAME
from lutris.gui.views.base import GameView
from lutris.gui.widgets.utils import get_generated_game_art, get_pixbuf_by_path, get_runtime_icon_path
from lutris.services.service_media import resolve_media_path
from lutris.util.jobs import schedule_at_idle
from lutris.util.log import logger
from lutris.util.path_cache import MISSING_GAMES

# Artwork corner rounding, matching the card style.
ART_RADIUS = 8
# Dimming for games that are not installed (was 100/255 in the renderer).
UNINSTALLED_OPACITY = 0.4
# Upper bound for the in-memory artwork cache; oldest entries are reloaded
# from disk, so libraries of any size stay usable.
PIXBUF_CACHE_SIZE = 300


def rounded_pixbuf(pixbuf, radius):
    """Returns a copy of a pixbuf with rounded corners."""
    width, height = pixbuf.get_width(), pixbuf.get_height()
    radius = max(0, min(radius, width / 2, height / 2))
    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, 1, None)
    target = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = cairo.Context(target)
    context.new_sub_path()
    context.arc(width - radius, radius, radius, -1.5708, 0)
    context.arc(width - radius, height - radius, radius, 0, 1.5708)
    context.arc(radius, height - radius, radius, 1.5708, 3.1416)
    context.arc(radius, radius, radius, 3.1416, 4.7124)
    context.close_path()
    context.clip()
    context.set_source_surface(surface, 0, 0)
    context.paint()
    return Gdk.pixbuf_get_from_surface(target, 0, 0, width, height)


class _CardPulseAdapter:
    """Presents widget cards through the inset protocol that
    GameView.on_game_start expects from an image renderer."""

    def __init__(self, view):
        self.view = view

    def inset_game(self, game_id, fraction):
        """Dims the launching tile in and out; returns True when changed."""
        info = self.view.cards_by_id.get(game_id)
        if not info:
            return False
        art = info.get("art")
        if art is None:
            return False
        base_opacity = UNINSTALLED_OPACITY if not info.get("installed", True) else 1.0
        art.set_opacity(max(0.4, base_opacity - fraction * 4))
        return True


class GameGridView(Gtk.FlowBox, GameView):  # type:ignore[misc]
    __gsignals__ = GameView.__gsignals__

    min_width = 70  # Minimum width for a cell

    def __init__(self, store, hide_text=False):
        Gtk.FlowBox.__init__(self)
        GameView.__init__(self)

        self.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.set_activate_on_single_click(False)
        self.set_homogeneous(False)
        self.set_column_spacing(14)
        self.set_row_spacing(14)

        self._hide_text = hide_text
        self._show_badges = True
        self._pixbuf_cache = {}
        self._ordered_ids = []
        self._cards_by_id = {}
        self._favorite_ids = set()
        self._badge_icon_paths = {}
        self._model = None
        self._model_handlers = []
        self._rebuild_pending = False
        self._media_size = (176, 234)

        # Lets GameView.on_game_start animate launching tiles.
        self.image_renderer = _CardPulseAdapter(self)

        self.set_game_store(store)

        self.connect_signals()
        self.categories_registration = categories_db.CATEGORIES_UPDATED.register(self._on_categories_updated)
        self.connect("child-activated", self.on_child_activated)
        self.connect("selected-children-changed", self.on_selection_changed)
        self.connect("button-press-event", self.on_button_press)
        self.connect("destroy", self._disconnect_model)
        self.connect("destroy", self._on_destroy)

    def _on_destroy(self, _widget):
        self.categories_registration.unregister()

    @property
    def cards_by_id(self):
        """Card widgets by game ID, for the launch pulse adapter."""
        return self._cards_by_id

    @property
    def show_badges(self):
        return self._show_badges

    @show_badges.setter
    def show_badges(self, value):
        if self._show_badges != value:
            self._show_badges = value
            self._schedule_rebuild()

    def set_game_store(self, game_store):
        self._disconnect_model()
        super().set_game_store(game_store)
        self.model = game_store.store
        self._model = game_store.store
        self._media_size = tuple(game_store.service_media.size)
        self._connect_model()
        self._rebuild()

    def _connect_model(self):
        if self._model is None or self._model_handlers:
            return
        self._model_handlers = [
            self._model.connect("row-inserted", self._on_model_structure_changed),
            self._model.connect("row-deleted", self._on_model_structure_changed),
            self._model.connect("row-changed", self._on_row_changed),
            self._model.connect("rows-reordered", self._on_model_structure_changed),
        ]

    def _disconnect_model(self, _widget=None):
        if self._model is not None:
            for handler_id in self._model_handlers:
                self._model.disconnect(handler_id)
        self._model = None
        self._model_handlers = []

    def _on_model_structure_changed(self, *_args):
        self._schedule_rebuild()

    def _on_row_changed(self, model, _path, tree_iter):
        """Refreshes a single card in place; a changed ID means the row was
        replaced, which needs a structural rebuild instead."""
        game_id = model.get_value(tree_iter, COL_ID)
        if game_id not in self._cards_by_id:
            self._schedule_rebuild()
            return
        self._refresh_card(model, tree_iter, game_id)

    def _schedule_rebuild(self):
        if self._rebuild_pending:
            return
        self._rebuild_pending = True
        schedule_at_idle(self._do_rebuild)

    def _do_rebuild(self):
        self._rebuild_pending = False
        self._rebuild()

    def _rebuild(self):
        """Recreates every tile from the model, preserving selection by ID.

        Selection signals stay blocked throughout: children are transiently
        out of sync with the model mid-rebuild, so any interim emission
        would hand out stale paths. One coherent event goes out at the end.
        """
        try:
            self.handler_block_by_func(self.on_selection_changed)
            blocked = True
        except TypeError:
            blocked = False
        try:
            self._rebuild_locked()
        finally:
            if blocked:
                try:
                    self.handler_unblock_by_func(self.on_selection_changed)
                except TypeError:
                    pass
        self._sync_selected_styles()
        self.on_selection_changed(self)

    def _rebuild_locked(self):
        """Rebuild body; runs with selection signals blocked."""
        selected_ids = set(self._selected_ids())
        for child in self.get_children():
            self.remove(child)
            child.destroy()
        self._ordered_ids = []
        self._cards_by_id = {}
        if self._model is None:
            return
        tree_iter = self._model.get_iter_first()
        while tree_iter:
            self._ordered_ids.append(self._model.get_value(tree_iter, COL_ID))
            tree_iter = self._model.iter_next(tree_iter)
        self._load_favorite_ids()
        tree_iter = self._model.get_iter_first()
        while tree_iter:
            game_id = self._model.get_value(tree_iter, COL_ID)
            card, refs = self._build_card(self._model, tree_iter, game_id)
            refs["row_ref"] = self._model_row_ref(tree_iter)
            self._cards_by_id[game_id] = refs
            self.add(card)
            tree_iter = self._model.iter_next(tree_iter)
        self.show_all()
        for game_id in selected_ids:
            if game_id in self._cards_by_id:
                child = self._cards_by_id[game_id]["card"].get_parent()
                if child is not None:
                    self.select_child(child)

    def _load_favorite_ids(self):
        """Batch-loads which visible games are favorites (one query)."""
        try:
            categories = categories_db.get_categories_in_games(self._ordered_ids)
        except Exception:  # noqa: BLE001 - tiles must render even without categories
            logger.debug("Could not load favorites", exc_info=True)
            categories = {}
        self._favorite_ids = {game_id for game_id, names in categories.items() if "favorite" in names}

    def _on_categories_updated(self):
        """Refreshes star toggles when favorites change elsewhere."""
        self._load_favorite_ids()
        for game_id, info in self._cards_by_id.items():
            star_button = info.get("star_button")
            if star_button is not None:
                self._update_star_button(star_button, game_id)

    def _toggle_favorite(self, game_id):
        """Adds or removes a game from favorites, mirroring Game.mark_as_favorite."""
        category = categories_db.get_category_by_name("favorite")
        if game_id in self._favorite_ids:
            if category is not None:
                categories_db.remove_category_from_game(game_id, category["id"])
            self._favorite_ids.discard(game_id)
        else:
            if category is None:
                category_id = categories_db.add_category("favorite")
            else:
                category_id = category["id"]
            categories_db.add_game_to_category(game_id, category_id)
            self._favorite_ids.add(game_id)
        info = self._cards_by_id.get(game_id)
        if info and info.get("star_button") is not None:
            self._update_star_button(info["star_button"], game_id)

    def _update_star_button(self, star_button, game_id):
        """Paints the star toggle for the game's favorite state."""
        favorite = game_id in self._favorite_ids
        context = star_button.get_style_context()
        if favorite:
            context.add_class("favorite-active")
        else:
            context.remove_class("favorite-active")
        star_button.set_tooltip_text(_("Remove from favorites") if favorite else _("Add to favorites"))

    def _on_star_clicked(self, _button, game_id):
        self._toggle_favorite(game_id)

    def _sync_selected_styles(self):
        """Paints selection via style classes (deterministic, theme-proof)."""
        selected = {child.get_index() for child in self.get_selected_children()}
        for child in self.get_children():
            card = child.get_child()
            if card is None:
                continue
            context = card.get_style_context()
            if child.get_index() in selected:
                context.add_class("selected")
            else:
                context.remove_class("selected")

    def _model_row_ref(self, tree_iter):
        return Gtk.TreeRowReference(self._model, self._model.get_path(tree_iter))

    def _build_card(self, model, tree_iter, game_id):
        """Creates a tile card widget plus the references needed to refresh it."""
        installed = bool(model.get_value(tree_iter, COL_INSTALLED))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, visible=True)
        card.set_valign(Gtk.Align.START)
        card.set_halign(Gtk.Align.CENTER)
        card.get_style_context().add_class("game-card")

        refs = {
            "card": card,
            "art": None,
            "installed": installed,
            "badge_box": None,
            "missing_label": None,
            "star_button": None,
        }

        if not settings.SHOW_MEDIA:
            pass  # Text-only tile: caption below carries the card.
        else:
            art = Gtk.Image(visible=True, halign=Gtk.Align.CENTER)
            self._set_card_art(art, model, tree_iter)
            if not installed:
                art.set_opacity(UNINSTALLED_OPACITY)
            refs["art"] = art

            overlay = Gtk.Overlay(visible=True)
            # Sized by the artwork (not the card) so overlays anchor to the
            # art's edges instead of floating in the card's empty areas.
            overlay.set_halign(Gtk.Align.CENTER)
            overlay.add(art)

            star_button = Gtk.Button(visible=True, relief=Gtk.ReliefStyle.NONE, focus_on_click=False)
            star_image = Gtk.Image.new_from_icon_name("favorite-symbolic", Gtk.IconSize.MENU)
            star_button.set_image(star_image)
            star_button.set_always_show_image(True)
            star_button.set_halign(Gtk.Align.END)
            star_button.set_valign(Gtk.Align.START)
            star_button.get_style_context().add_class("game-card-favorite")
            self._update_star_button(star_button, game_id)
            star_button.connect("clicked", self._on_star_clicked, game_id)
            refs["star_button"] = star_button
            overlay.add_overlay(star_button)

            if self._show_badges:
                badge_box = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL,
                    spacing=2,
                    visible=True,
                    halign=Gtk.Align.END,
                    valign=Gtk.Align.END,
                )
                badge_box.set_margin_end(8)
                badge_box.set_margin_bottom(8)
                refs["badge_box"] = badge_box
                overlay.add_overlay(badge_box)
            missing_label = Gtk.Label(label=_("Missing"), visible=False, halign=Gtk.Align.START, valign=Gtk.Align.END)
            missing_label.set_margin_start(8)
            missing_label.set_margin_bottom(8)
            missing_label.get_style_context().add_class("game-card-missing")
            refs["missing_label"] = missing_label
            overlay.add_overlay(missing_label)
            card.pack_start(overlay, False, False, 0)

        if not self._hide_text:
            caption = Gtk.Label(visible=True, xalign=0.5)
            caption.set_markup(self.tile_caption_markup(model, tree_iter))
            caption.set_line_wrap(True)
            caption.set_justify(Gtk.Justification.CENTER)
            caption.set_size_request(max(self._media_size[0], self.min_width), -1)
            refs["caption"] = caption
            card.pack_start(caption, False, False, 0)

        self._refresh_badges(refs, model, tree_iter, game_id)
        return card, refs

    def _refresh_card(self, model, tree_iter, game_id):
        """Rebuilds one tile's contents inside its existing selection wrapper."""
        info = self._cards_by_id.get(game_id)
        if not info:
            return
        wrapper = info["card"].get_parent()
        if wrapper is None:
            self._schedule_rebuild()
            return
        card, refs = self._build_card(model, tree_iter, game_id)
        refs["row_ref"] = info.get("row_ref")
        wrapper.remove(info["card"])
        info["card"].destroy()
        wrapper.add(card)
        wrapper.show_all()
        self._cards_by_id[game_id] = refs

    def _refresh_badges(self, refs, model, tree_iter, game_id):
        """Updates platform badges and the missing marker of one tile."""
        badge_box = refs.get("badge_box")
        if badge_box is not None:
            for child in badge_box.get_children():
                badge_box.remove(child)
                child.destroy()
            for icon_path in self._platform_icon_paths(model, tree_iter):
                size = self._badge_size()
                if size is None:
                    break
                icon = self._load_badge_icon(icon_path, size)
                if icon is not None:
                    badge_box.pack_start(icon, False, False, 0)
            badge_box.show_all()
        missing_label = refs.get("missing_label")
        if missing_label is not None:
            missing_label.set_visible(self._is_missing(game_id))

    def _is_missing(self, game_id):
        resolved_id = game_id
        if self.service:
            resolved_id = self.service.resolve_game_id(game_id)
        return resolved_id in MISSING_GAMES.missing_game_ids

    def _platform_icon_paths(self, model, tree_iter):
        platform = model.get_value(tree_iter, COL_PLATFORM) or ""
        if platform in self._badge_icon_paths:
            return self._badge_icon_paths[platform]
        if "," in platform:
            platforms = platform.split(",")
        else:
            platforms = [platform]
        icon_paths = []
        for item in platforms:
            icon_path = get_runtime_icon_path(item.strip() + "-symbolic")
            if icon_path:
                icon_paths.append(icon_path)
        self._badge_icon_paths[platform] = icon_paths
        return icon_paths

    def _badge_size(self):
        """Badge icon size mirroring the old renderer thresholds."""
        media_width, media_height = self._media_size
        if media_width < 64:
            return None
        if media_height < 128:
            return 16
        if media_height < 256:
            return 24
        return 32

    def _load_badge_icon(self, icon_path, size):
        pixbuf = self._load_pixbuf(icon_path, (size, size), True)
        if pixbuf is None:
            return None
        return Gtk.Image.new_from_pixbuf(pixbuf)

    def _set_card_art(self, art, model, tree_iter):
        """Loads (or reloads) the artwork of one tile."""
        media_width, media_height = self._media_size
        pixbuf = None
        media_paths = model.get_value(tree_iter, COL_MEDIA_PATHS) or []
        if media_paths:
            media = resolve_media_path(media_paths)
            if media and media.width > 0 and media.height > 0 and media.path:
                pixbuf = self._load_pixbuf(media.path, (media_width, media_height), True)
        if pixbuf is None:
            pixbuf = self._generated_art(model, tree_iter)
        if pixbuf is not None:
            art.set_from_pixbuf(self._rounded_art(pixbuf))

    def _generated_art(self, model, tree_iter):
        """Fallback artwork via the shared generator (cached per game/size)."""
        width, height = self._media_size
        game_id = model.get_value(tree_iter, COL_ID)
        name = model.get_value(tree_iter, COL_NAME) or ""
        key = ("generated", game_id, width, height)
        if key in self._pixbuf_cache:
            return self._pixbuf_cache[key]
        surface = get_generated_game_art(game_id, name, (width, height))
        if surface is None:
            return None
        pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)
        self._cache_pixbuf(key, pixbuf)
        return pixbuf

    def _cache_pixbuf(self, key, pixbuf):
        if len(self._pixbuf_cache) >= PIXBUF_CACHE_SIZE:
            self._pixbuf_cache.pop(next(iter(self._pixbuf_cache)))
        self._pixbuf_cache[key] = pixbuf

    def _load_pixbuf(self, path, size, keep_aspect):
        """Cached artwork loading; corrupt files fall back to nothing."""
        key = (path, size[0], size[1], keep_aspect)
        if key in self._pixbuf_cache:
            return self._pixbuf_cache[key]
        try:
            pixbuf = get_pixbuf_by_path(path, size=size, preserve_aspect_ratio=keep_aspect)
        except Exception:  # noqa: BLE001 - a corrupt image must not break the view
            logger.debug("Could not load artwork %s", path, exc_info=True)
            pixbuf = None
        self._cache_pixbuf(key, pixbuf)
        return pixbuf

    def _rounded_art(self, pixbuf):
        """Returns an artwork copy with rounded corners for the card."""
        key = ("rounded", id(pixbuf))
        if key in self._pixbuf_cache:
            return self._pixbuf_cache[key]
        width, height = pixbuf.get_width(), pixbuf.get_height()
        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, 1, None)
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        context = cairo.Context(target)
        radius = min(ART_RADIUS, width / 2, height / 2)
        context.new_sub_path()
        context.arc(width - radius, radius, radius, -1.5708, 0)
        context.arc(width - radius, height - radius, radius, 0, 1.5708)
        context.arc(radius, height - radius, radius, 1.5708, 3.1416)
        context.arc(radius, radius, radius, 3.1416, 4.7124)
        context.close_path()
        context.clip()
        context.set_source_surface(surface, 0, 0)
        context.paint()
        rounded = Gdk.pixbuf_get_from_surface(target, 0, 0, width, height)
        self._cache_pixbuf(key, rounded)
        return rounded

    def refresh_images(self):
        """Reloads all artwork in place (used when the media cache changes)."""
        self._pixbuf_cache.clear()
        if self._model is None:
            return
        for info in self._cards_by_id.values():
            if info.get("art") is None:
                continue
            row_ref = info.get("row_ref")
            if not row_ref or not row_ref.valid():
                continue
            path = row_ref.get_path()
            if path is None:
                continue
            tree_iter = self._model.get_iter(path)
            self._set_card_art(info["art"], self._model, tree_iter)

    def on_media_cache_invalidated(self):
        self.refresh_images()

    def on_missing_games_updated(self):
        self._schedule_rebuild()

    @staticmethod
    def tile_caption_markup(model, tree_iter):
        """Two-line tile caption: game name plus a dimmed runner • platform
        subline. Values are already markup-escaped by the store."""
        name = model.get_value(tree_iter, COL_NAME) or ""
        details = " • ".join(
            part
            for part in (
                model.get_value(tree_iter, COL_RUNNER_HUMAN_NAME),
                model.get_value(tree_iter, COL_PLATFORM),
            )
            if part
        )
        if details:
            return '%s\n<span size="smaller" alpha="60%%">%s</span>' % (name, details)
        return name

    @staticmethod
    def format_tile_caption(_layout, cell, model, tree_iter):
        """Cell-renderer era entry point, kept for compatibility and tests."""
        cell.props.markup = GameGridView.tile_caption_markup(model, tree_iter)

    def get_path_at(self, x, y):
        child = self.get_child_at_pos(x, y)
        if child is None:
            return None
        return Gtk.TreePath(child.get_index())

    def _selected_ids(self):
        """Game IDs of the current selection, in display order."""
        ids = []
        for child in self.get_selected_children():
            index = child.get_index()
            if 0 <= index < len(self._ordered_ids):
                ids.append(self._ordered_ids[index])
        ids.sort(key=lambda game_id: self._ordered_ids.index(game_id))
        return ids

    def set_selected(self, paths, scroll_into_view=False):
        self.unselect_all()

        first = True
        for path in paths:
            indices = path.get_indices()
            if not indices:
                continue
            child = self.get_child_at_index(indices[0])
            if child is not None:
                self.select_child(child)
                if scroll_into_view and first:
                    first = False
                    self._scroll_to_child(child)
        self._sync_selected_styles()

    def _scroll_to_child(self, child):
        """Scrolls the containing ScrolledWindow so the child is visible."""
        parent = self.get_parent()
        while parent is not None and not isinstance(parent, Gtk.ScrolledWindow):
            parent = parent.get_parent()
        if parent is None:
            child.grab_focus()
            return

        def scroll_now():
            allocation = child.get_allocation()
            adjustment = parent.get_vadjustment()
            position = allocation.y + allocation.height / 2 - adjustment.get_page_size() / 2
            adjustment.set_value(max(adjustment.get_lower(), min(position, adjustment.get_upper())))

        schedule_at_idle(scroll_now)

    def get_selected(self):
        """Return list of all selected items as paths"""
        return [Gtk.TreePath(index) for index in sorted(child.get_index() for child in self.get_selected_children())]

    def select_path(self, path):
        """Selects the item at a path; kept for callers written against IconView."""
        indices = path.get_indices()
        if not indices:
            return
        child = self.get_child_at_index(indices[0])
        if child is not None:
            self.select_child(child)

    def set_cursor(self, path, _cell=None, _start_editing=False):
        """IconView/TreeView compatibility shim; ensures a selection exists."""
        self.select_path(path)

    def get_game_id_for_path(self, path):
        # Resolved through the child-parallel ID list (never the live
        # model): selections can outlive model rows during removals, and
        # this must return None then instead of raising on a stale path.
        indices = path.get_indices()
        if not indices or indices[0] >= len(self._ordered_ids):
            return None
        return self._ordered_ids[indices[0]]

    def get_path_for_game_id(self, game_id):
        if self.game_store:
            return self.game_store.get_path_by_id(game_id)
        return None

    def on_button_press(self, _view, event):
        """Selects only on real card hits; clicks on wrapper dead zones
        (which the old grid never had) clear the selection instead."""
        if event.button != Gdk.BUTTON_PRIMARY:
            return False
        child = self.get_child_at_pos(event.x, event.y)
        if child is None:
            self.unselect_all()
            return False
        card = child.get_child()
        if card is not None:
            translated = self.translate_coordinates(card, event.x, event.y)
            if translated is None:
                self.unselect_all()
                return True
            hit_x, hit_y = translated
            if not (0 <= hit_x < card.get_allocated_width() and 0 <= hit_y < card.get_allocated_height()):
                self.unselect_all()
                return True
        return False

    def on_child_activated(self, _view, _child):
        """Handles double clicks"""
        selected_id = self.get_selected_game_id()
        if selected_id:
            logger.debug("Item activated: %s", selected_id)
            self.emit("game-activated", selected_id)

    def on_selection_changed(self, _view):
        """Handles selection changes"""
        self._sync_selected_styles()
        selected_items = self.get_selected()
        self.emit("game-selected", selected_items)
