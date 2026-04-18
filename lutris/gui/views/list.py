"""Gtk.ColumnView based game list."""

from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris import settings
from lutris.gui.views.base import GameView
from lutris.gui.widgets.utils import get_default_icon_path
from lutris.services.service_media import resolve_media_path


class _ListImageRenderer:
    """Shim exposed as GameListView.image_renderer.

    GameView.on_game_start drives the launch-bounce by calling inset_game()
    with a 0.0-0.1 fraction each tick. In the list view the actual scaling
    is done in CSS (see `.lutris-game-list picture.launching` keyframes),
    because Gtk.Picture ignores set_size_request below its intrinsic size.
    This shim collapses the fraction-based calls into a boolean "launching"
    class toggled on the bound Picture widgets.

    TODO: Once the grid view is also GTK 4 and no longer needs per-frame
    fraction updates driven from base.py, drop the fraction plumbing and
    let GameView.on_game_start just emit start/stop events.
    """

    show_badges = False

    def __init__(self, view: "GameListView"):
        self._view = view
        self._launching_game_ids: set[str] = set()

    def is_launching(self, game_id: str) -> bool:
        return game_id in self._launching_game_ids

    def inset_game(self, game_id: str, fraction: float) -> bool:
        if fraction > 0.0:
            if game_id not in self._launching_game_ids:
                self._launching_game_ids.add(game_id)
                self._view._apply_launching_for_game(game_id, True)
                return True
        elif game_id in self._launching_game_ids:
            self._launching_game_ids.discard(game_id)
            self._view._apply_launching_for_game(game_id, False)
            return True
        return False


class GameListView(Gtk.ColumnView, GameView):  # type:ignore[misc]
    """Main games list as a Gtk.ColumnView."""

    __gsignals__ = GameView.__gsignals__

    # Column identifiers used as keys in settings.
    NAME_COLUMN = "name"
    YEAR_COLUMN = "year"
    RUNNER_COLUMN = "runner"
    PLATFORM_COLUMN = "platform"
    LASTPLAYED_COLUMN = "lastplayed"
    PLAYTIME_COLUMN = "playtime"
    INSTALLEDAT_COLUMN = "installedat"

    def __init__(self, store) -> None:
        Gtk.ColumnView.__init__(self)
        GameView.__init__(self)

        self.set_show_row_separators(False)
        self.set_show_column_separators(False)
        self.add_css_class("lutris-game-list")

        self.columns_by_id: "dict[str, Gtk.ColumnViewColumn]" = {}
        self.image_column: Gtk.ColumnViewColumn | None = None
        self.sort_model: Gtk.SortListModel | None = None
        self.selection: Gtk.MultiSelection | None = None

        # Bound image widgets and per-game inset fractions are tracked here so
        # the launch-bounce animation can scale in-place rows without walking
        # ColumnView internals. self.image_renderer is the shim GameView's
        # on_game_start drives via inset_game(); see _ListImageRenderer below.
        self._bound_pictures: "set[Gtk.Picture]" = set()
        self.image_renderer = _ListImageRenderer(self)

        # Stash the store on the base mixin before building columns, since
        # column construction reads service_media and the item type from it.
        GameView.set_game_store(self, store)
        self._build_columns()
        self._rebind_model(store)

        self.connect_signals()
        self.connect("activate", self._on_activate)

    def set_game_store(self, game_store):
        super().set_game_store(game_store)
        self._rebind_model(game_store)

    def _rebind_model(self, game_store):
        # LutrisWindow.update_store() creates a fresh GameStore on every
        # refresh and swaps it in, so the ColumnView's model must be re-bound
        # to the new list_store or the view keeps showing the old (now-stale,
        # often empty) store.
        self.sort_model = Gtk.SortListModel.new(game_store.list_store, self.get_sorter())
        self.selection = Gtk.MultiSelection(model=self.sort_model)
        self.selection.connect("selection-changed", self._on_selection_changed)
        self.set_model(self.selection)

        # Zoom changes swap in a new GameStore with a different service_media,
        # so the image column's fixed width must track the current store.
        if self.image_column is not None:
            self.image_column.set_fixed_width(game_store.service_media.size[0])

    def _build_columns(self):
        if settings.SHOW_MEDIA:
            size = self.game_store.service_media.size
            image_column = Gtk.ColumnViewColumn.new("", self._make_image_factory())
            image_column.set_fixed_width(size[0])
            image_column.set_resizable(False)
            self.append_column(image_column)
            self.image_column = image_column

        name_column = self._append_text_column(
            self.NAME_COLUMN,
            _("Name"),
            property_name="name",
            default_width=200,
            always_visible=True,
            sort_property="sortname",
        )
        # Absorb any leftover horizontal space so the sum of column widths
        # always equals the viewport — otherwise the ColumnView's horizontal
        # scroll adjustment ends up with page_size > upper and spams
        # gtk_adjustment_configure CRITICAL warnings every frame.
        name_column.set_expand(True)
        self._append_text_column(
            self.YEAR_COLUMN,
            _("Year"),
            property_name="year",
            default_width=60,
            sort_property="year",
        )
        self._append_text_column(
            self.RUNNER_COLUMN,
            _("Runner"),
            property_name="runner_human_name",
            default_width=120,
            sort_property="runner_human_name",
        )
        self._append_text_column(
            self.PLATFORM_COLUMN,
            _("Platform"),
            property_name="platform",
            default_width=120,
            sort_property="platform",
        )
        self._append_text_column(
            self.LASTPLAYED_COLUMN,
            _("Last Played"),
            property_name="lastplayed_text",
            default_width=120,
            sort_property="lastplayed",
        )
        self._append_text_column(
            self.PLAYTIME_COLUMN,
            _("Play Time"),
            property_name="playtime_text",
            default_width=100,
            sort_property="playtime",
        )
        self._append_text_column(
            self.INSTALLEDAT_COLUMN,
            _("Installed At"),
            property_name="installed_at_text",
            default_width=120,
            sort_property="installed_at",
        )

    def _append_text_column(
        self,
        column_id: str,
        title: str,
        property_name: str,
        default_width: int,
        always_visible: bool = False,
        sort_property: str | None = None,
    ) -> Gtk.ColumnViewColumn:
        column = Gtk.ColumnViewColumn.new(title, self._make_text_factory(property_name))
        column.set_resizable(True)

        width = settings.read_setting("%s_column_width" % column_id, section="list view")
        column.set_fixed_width(int(width) if width else default_width)

        is_visible = settings.read_setting("%s_visible" % column_id, section="list view")
        if is_visible:
            column.set_visible(is_visible == "True" or always_visible)
        else:
            column.set_visible(True)

        if sort_property:
            expr = Gtk.PropertyExpression.new(self.game_store.list_store.get_item_type(), None, sort_property)
            if sort_property in ("lastplayed", "installed_at", "playtime"):
                sorter = Gtk.NumericSorter.new(expr)
            else:
                sorter = Gtk.StringSorter.new(expr)
            column.set_sorter(sorter)

        column.connect("notify::fixed-width", self._on_column_width_changed, column_id)

        self.append_column(column)
        self.columns_by_id[column_id] = column
        return column

    @staticmethod
    def _make_text_factory(property_name: str) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def on_setup(_factory, list_item):
            label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, use_markup=True)
            label.set_margin_start(6)
            label.set_margin_end(6)
            list_item.set_child(label)

        def on_bind(_factory, list_item):
            label = list_item.get_child()
            item = list_item.get_item()
            # Keep the bound item on the widget so right-click handling can map
            # a click location back to a row without walking Gtk.ColumnView internals.
            label._bound_item = item  # type: ignore[attr-defined]
            binding = item.bind_property(property_name, label, "label", GObject.BindingFlags.SYNC_CREATE)
            list_item._binding = binding  # type: ignore[attr-defined]

        def on_unbind(_factory, list_item):
            label = list_item.get_child()
            label._bound_item = None  # type: ignore[attr-defined]
            binding = getattr(list_item, "_binding", None)
            if binding is not None:
                binding.unbind()
                list_item._binding = None  # type: ignore[attr-defined]

        factory.connect("setup", on_setup)
        factory.connect("bind", on_bind)
        factory.connect("unbind", on_unbind)
        return factory

    def _make_image_factory(self) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def on_setup(_factory, list_item):
            picture = Gtk.Picture()
            picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
            picture.set_can_shrink(True)
            picture.set_halign(Gtk.Align.CENTER)
            picture.set_valign(Gtk.Align.CENTER)
            picture.set_hexpand(False)
            picture.set_vexpand(False)
            # size_request is set here (not just in on_bind) so widgets have a
            # predictable size from creation — otherwise freshly-setup rows
            # measure at 0x0 until bound, giving the ColumnView inconsistent
            # row heights that corrupt its scroll adjustment during scrolling.
            size = self.game_store.service_media.size
            picture.set_size_request(size[0], size[1])
            list_item.set_child(picture)

        def on_bind(_factory, list_item):
            picture = list_item.get_child()
            item = list_item.get_item()
            picture._bound_item = item  # type: ignore[attr-defined]
            self._bound_pictures.add(picture)
            # Size tracks the current service_media rather than being baked
            # into the factory, so zoom changes take effect on the next bind.
            size = self.game_store.service_media.size
            picture.set_size_request(size[0], size[1])
            # Re-apply the launching CSS class if this game is mid-bounce and
            # scrolled back into view.
            self._apply_launching_to_picture(picture, self.image_renderer.is_launching(item.id))
            paths = item.media_paths or []
            if paths:
                mp = resolve_media_path(paths)
                if mp and mp.exists:
                    picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
                    picture.set_filename(mp.path)
                    return
            # Fallback: Lutris glyph for square (icon) sizes, gradient banner
            # for non-square sizes — same behavior as the grid view. The PNGs
            # are stored square (256x256), so the non-square banner fallback
            # needs FILL to stretch into the media's aspect ratio; the square
            # icon fallback is fine with SCALE_DOWN.
            picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN if size[0] == size[1] else Gtk.ContentFit.FILL)
            picture.set_filename(get_default_icon_path(size))

        def on_unbind(_factory, list_item):
            picture = list_item.get_child()
            picture._bound_item = None  # type: ignore[attr-defined]
            self._bound_pictures.discard(picture)
            self._apply_launching_to_picture(picture, False)
            picture.set_filename(None)

        factory.connect("setup", on_setup)
        factory.connect("bind", on_bind)
        factory.connect("unbind", on_unbind)
        return factory

    @staticmethod
    def _apply_launching_to_picture(picture, launching: bool) -> None:
        if launching:
            picture.add_css_class("launching")
        else:
            picture.remove_css_class("launching")

    def _apply_launching_for_game(self, game_id: str, launching: bool) -> None:
        for picture in self._bound_pictures:
            item = getattr(picture, "_bound_item", None)
            if item is not None and item.id == game_id:
                self._apply_launching_to_picture(picture, launching)

    @staticmethod
    def _on_column_width_changed(column, _pspec, column_id):
        width = column.get_fixed_width()
        if width > 0:
            settings.write_setting("%s_column_width" % column_id, width, "list view")

    # ---- GameView API -------------------------------------------------

    def _on_activate(self, _column_view, position):
        item = self.selection.get_item(position)
        if item:
            self.emit("game-activated", item.id)

    def _on_selection_changed(self, _model, _position, _n_items):
        self.emit("game-selected", self.get_selected())

    def get_selected(self):
        bitset = self.selection.get_selection()
        return [bitset.get_nth(i) for i in range(bitset.get_size())]

    def set_selected(self, positions, scroll_into_view=False):
        positions = list(positions)
        self.selection.unselect_all()
        for pos in positions:
            self.selection.select_item(pos, False)
        if scroll_into_view and positions:
            self.scroll_to(positions[0], None, Gtk.ListScrollFlags.NONE, None)

    def get_game_id_for_path(self, path):
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

    def set_selected_game(self, game_id):
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


class GameListColumnToggleMenu(Gtk.Popover):
    """Column visibility toggle menu."""

    def __init__(self, columns_by_id: dict[str, Gtk.ColumnViewColumn]):
        super().__init__()
        self.columns_by_id = columns_by_id

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)

        for column_id, column in self.columns_by_id.items():
            title = column.get_title()
            if not title:
                continue
            checkbox = Gtk.CheckButton(label=title)
            checkbox.set_active(column.get_visible())
            if column_id == GameListView.NAME_COLUMN:
                checkbox.set_sensitive(False)
            else:
                checkbox.connect("toggled", self._on_toggle_column, column_id)
            box.append(checkbox)

        self.set_child(box)

    def _on_toggle_column(self, check_button, column_id):
        is_visible = check_button.get_active()
        column = self.columns_by_id[column_id]
        column.set_visible(is_visible)
        settings.write_setting("%s_visible" % column_id, str(is_visible), "list view")
