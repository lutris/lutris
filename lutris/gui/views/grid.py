"""Gtk.GridView based game grid."""

# pylint: disable=no-member
from gi.repository import Gtk, Pango

from lutris.gui.views.base import GameView
from lutris.gui.widgets.game_cover import GameCoverWidget
from lutris.util.log import logger


class _GridImageRenderer:
    """Shim exposed as GameGridView.image_renderer.

    GameView.on_game_start calls inset_game(id, fraction) 40x/s to drive the
    launch-bounce. We track the per-game fraction here and forward it to any
    bound GameCoverWidget whose item id matches.

    TODO: Once the bounce animation state is owned by each view directly
    instead of flowing through GameView.on_game_start, drop this shim.
    """

    def __init__(self, view: "GameGridView"):
        self._view = view
        self._inset_fractions: dict[str, float] = {}
        self._show_badges = True
        # Set by GameView.set_game_store() so cellrenderer-era consumers can
        # find the service; kept here for compatibility with the base mixin.
        self.service = None

    @property
    def show_badges(self) -> bool:
        return self._show_badges

    @show_badges.setter
    def show_badges(self, value: bool) -> None:
        self._show_badges = bool(value)
        self._view._apply_show_badges(self._show_badges)

    def get_inset_fraction(self, game_id: str) -> float:
        return self._inset_fractions.get(game_id, 0.0)

    def inset_game(self, game_id: str, fraction: float) -> bool:
        if fraction > 0.0:
            if fraction != self._inset_fractions.get(game_id):
                self._inset_fractions[game_id] = fraction
                self._view._apply_inset_for_game(game_id, fraction)
                return True
        elif game_id in self._inset_fractions:
            del self._inset_fractions[game_id]
            self._view._apply_inset_for_game(game_id, 0.0)
            return True
        return False


class GameGridView(Gtk.GridView, GameView):  # type:ignore[misc]
    """Main games grid as a Gtk.GridView."""

    __gsignals__ = GameView.__gsignals__

    # Floor for the per-cell width so labels don't collapse to the cover's
    # natural width at icon zoom levels (where covers can be as narrow as 32px).
    MIN_CELL_WIDTH = 70

    def __init__(self, store, hide_text: bool = False) -> None:
        Gtk.GridView.__init__(self)
        GameView.__init__(self)

        self.hide_text = hide_text
        self.add_css_class("lutris-game-grid")

        self._bound_covers: "set[GameCoverWidget]" = set()
        self.image_renderer = _GridImageRenderer(self)
        self.sort_model: "Gtk.SortListModel | None" = None
        self.selection: "Gtk.MultiSelection | None" = None

        GameView.set_game_store(self, store)
        self.set_factory(self._make_factory())
        self._rebind_model(store)

        self.connect_signals()
        self.connect("activate", self._on_activate)

    def set_game_store(self, game_store):
        super().set_game_store(game_store)
        self._rebind_model(game_store)
        # Cell dimensions come from the current service_media, so every bound
        # cover widget needs to track it on zoom changes; the enclosing box
        # also needs its min-width floor updated for the new cover size.
        size = game_store.service_media.size
        cell_width = self._cell_width(size[0])
        for cover in self._bound_covers:
            cover.set_expected_size(size[0], size[1])
            box = cover.get_parent()
            if box is not None:
                box.set_size_request(cell_width, -1)

    def _cell_width(self, media_width: int) -> int:
        if self.hide_text:
            return media_width
        return max(media_width, self.MIN_CELL_WIDTH)

    def _rebind_model(self, game_store) -> None:
        self.sort_model = Gtk.SortListModel.new(game_store.list_store, None)
        self.selection = Gtk.MultiSelection(model=self.sort_model)
        self.selection.connect("selection-changed", self._on_selection_changed)
        self.set_model(self.selection)

    def _make_factory(self) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def on_setup(_factory, list_item):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.START)

            cover = GameCoverWidget()
            cover.set_halign(Gtk.Align.CENTER)
            size = self.game_store.service_media.size
            cover.set_expected_size(size[0], size[1])
            box.set_size_request(self._cell_width(size[0]), -1)
            box.append(cover)

            if not self.hide_text:
                label = Gtk.Label(xalign=0.5, yalign=0, use_markup=True)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_wrap(True)
                label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                label.set_lines(2)
                label.set_justify(Gtk.Justification.CENTER)
                label.set_max_width_chars(1)
                label.set_hexpand(True)
                box.append(label)

            list_item.set_child(box)

        def on_bind(_factory, list_item):
            box = list_item.get_child()
            cover = box.get_first_child()
            item = list_item.get_item()
            # Stash the bound item on box and cover so right-click can map
            # pick() to a row from any descendant of the cell.
            box._bound_item = item  # type: ignore[attr-defined]
            cover._bound_item = item  # type: ignore[attr-defined]
            self._bound_covers.add(cover)

            size = self.game_store.service_media.size
            cover.set_expected_size(size[0], size[1])
            cover.set_data(
                game_id=item.id,
                service=self.service,
                media_paths=item.media_paths or [],
                platform=item.platform,
                is_installed=item.installed,
                show_badges=self.image_renderer.show_badges,
            )
            cover.set_inset_fraction(self.image_renderer.get_inset_fraction(item.id))

            label = cover.get_next_sibling()
            if label is not None:
                label.set_label(item.name)

        def on_unbind(_factory, list_item):
            box = list_item.get_child()
            cover = box.get_first_child()
            box._bound_item = None  # type: ignore[attr-defined]
            cover._bound_item = None  # type: ignore[attr-defined]
            self._bound_covers.discard(cover)
            cover.set_inset_fraction(0.0)

        factory.connect("setup", on_setup)
        factory.connect("bind", on_bind)
        factory.connect("unbind", on_unbind)
        return factory

    # ---- image_renderer shim callbacks -------------------------------

    def _apply_inset_for_game(self, game_id: str, fraction: float) -> None:
        for cover in self._bound_covers:
            if cover.game_id == game_id:
                cover.set_inset_fraction(fraction)

    def _apply_show_badges(self, show_badges: bool) -> None:
        for cover in self._bound_covers:
            item = getattr(cover, "_bound_item", None)
            if item is None:
                continue
            cover.set_data(
                game_id=item.id,
                service=self.service,
                media_paths=item.media_paths or [],
                platform=item.platform,
                is_installed=item.installed,
                show_badges=show_badges,
            )

    # ---- GameView API ------------------------------------------------

    def _on_activate(self, _grid_view, position) -> None:
        assert self.selection is not None
        item = self.selection.get_item(position)
        if item:
            logger.debug("Item activated: %s", item.id)
            self.emit("game-activated", item.id)

    def _on_selection_changed(self, _model, _position, _n_items) -> None:
        self.emit("game-selected", self.get_selected())

    def get_selected(self):
        if self.selection is None:
            return []
        bitset = self.selection.get_selection()
        return [bitset.get_nth(i) for i in range(bitset.get_size())]

    def set_selected(self, positions, scroll_into_view: bool = False) -> None:
        if self.selection is None:
            return
        positions = list(positions)
        self.selection.unselect_all()
        for pos in positions:
            self.selection.select_item(pos, False)
        if scroll_into_view and positions:
            self.scroll_to(positions[0], Gtk.ListScrollFlags.NONE, None)

    def get_game_id_for_path(self, path):
        if self.selection is None:
            return None
        item = self.selection.get_item(path)
        return item.id if item else None

    def get_path_for_game_id(self, game_id):
        if not game_id or not self.game_store:
            return None
        item = self.game_store._items_by_id.get(str(game_id))
        if item is None:
            return None
        found, pos = self.game_store.list_store.find(item)
        return pos if found else None

    def set_selected_game(self, game_id) -> None:
        pos = self.get_path_for_game_id(game_id)
        if pos is not None:
            self.set_selected([pos], scroll_into_view=True)

    def get_path_at(self, x, y):
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        widget = picked
        while widget is not None:
            item = getattr(widget, "_bound_item", None)
            if item is not None:
                found, pos = self.game_store.list_store.find(item)
                return pos if found else None
            widget = widget.get_parent()
        return None
