"""GameGridView FlowBox behavior (headless widget tests, no display needed).

Builds a real ListStore + GameGridView and exercises model sync, card
structure, selection round-trips and path mapping.
"""

import os
import unittest
from types import SimpleNamespace

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import GObject, Gtk

from lutris import settings
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.database import schema
from lutris.gui.views import COL_ID, COL_NAME
from lutris.gui.views.grid import GameGridView
from lutris.util.test_config import setup_test_environment

setup_test_environment()


def make_store(rows):
    """A ListStore with the real 16-column game schema."""
    store = Gtk.ListStore(
        str,
        str,
        str,
        str,
        GObject.TYPE_PYOBJECT,
        str,
        str,
        str,
        str,
        GObject.TYPE_INT64,
        str,
        bool,
        GObject.TYPE_INT64,
        str,
        float,
        str,
    )
    for values in rows:
        store.append(values)
    return store


def make_row(game_id, name, runner="Linux", platform="Linux"):
    return (
        game_id,  # COL_ID
        game_id,  # COL_SLUG
        name,  # COL_NAME
        name,  # COL_SORTNAME
        [],  # COL_MEDIA_PATHS
        "",  # COL_YEAR
        runner.lower(),  # COL_RUNNER
        runner,  # COL_RUNNER_HUMAN_NAME
        platform,  # COL_PLATFORM
        0,  # COL_LASTPLAYED
        "",  # COL_LASTPLAYED_TEXT
        True,  # COL_INSTALLED
        0,  # COL_INSTALLED_AT
        "",  # COL_INSTALLED_AT_TEXT
        0.0,  # COL_PLAYTIME
        "",  # COL_PLAYTIME_TEXT
    )


def make_view(rows):
    store = make_store(rows)
    game_store = SimpleNamespace(
        store=store,
        service=None,
        service_media=SimpleNamespace(size=(184, 69)),
        get_path_by_id=lambda game_id: _find_path(store, game_id),
    )
    return GameGridView(game_store)


def _find_path(store, game_id):
    tree_iter = store.get_iter_first()
    while tree_iter:
        if store.get_value(tree_iter, COL_ID) == game_id:
            return store.get_path(tree_iter)
        tree_iter = store.iter_next(tree_iter)
    return None


class TestFlowBoxGrid(unittest.TestCase):
    def test_tiles_match_rows(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        self.assertEqual(len(view.get_children()), 2)
        self.assertEqual(view._ordered_ids, ["1", "2"])

    def test_cards_have_game_card_class(self):
        view = make_view([make_row("1", "Undertail")])
        card = view._cards_by_id["1"]["card"]
        self.assertIn("game-card", card.get_style_context().list_classes())

    def test_selection_round_trip(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        view.set_selected([Gtk.TreePath(1)])
        selected = view.get_selected()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].get_indices(), [1])
        self.assertEqual(view.get_game_id_for_path(selected[0]), "2")

    def test_path_for_game_id(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        path = view.get_path_for_game_id("2")
        self.assertIsNotNone(path)

    def test_caption_markup(self):
        view = make_view([make_row("1", "Undertail", runner="Wine", platform="Windows")])
        caption = view._cards_by_id["1"]["caption"]
        self.assertIn("Undertail", caption.get_text())
        self.assertIn("Wine", caption.get_text())

    def test_missing_art_falls_back(self):
        view = make_view([make_row("1", "Undertail")])
        art = view._cards_by_id["1"]["art"]
        self.assertIsNotNone(art.get_pixbuf())

    def test_row_changed_updates_caption(self):
        store = make_store([make_row("1", "Undertail")])
        game_store = SimpleNamespace(store=store, service=None, service_media=SimpleNamespace(size=(184, 69)))
        view = GameGridView(game_store)
        store[0][COL_NAME] = "Undertail Remastered"
        caption = view._cards_by_id["1"]["caption"]
        self.assertIn("Undertail Remastered", caption.get_text())

    def test_row_inserted_adds_tile(self):
        store = make_store([make_row("1", "Undertail")])
        game_store = SimpleNamespace(store=store, service=None, service_media=SimpleNamespace(size=(184, 69)))
        view = GameGridView(game_store)
        view._rebuild_pending = False
        store.append(make_row("2", "Doom"))
        view._do_rebuild()
        self.assertEqual(len(view.get_children()), 2)
        self.assertEqual(view._ordered_ids, ["1", "2"])

    def test_empty_press_clears_selection(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        view.set_selected([Gtk.TreePath(0)])
        self.assertEqual(len(view.get_selected()), 1)
        view.on_button_press(view, SimpleNamespace(button=1, x=99999, y=99999))
        self.assertEqual(view.get_selected(), [])

    def test_right_press_keeps_selection(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        view.set_selected([Gtk.TreePath(0)])
        view.on_button_press(view, SimpleNamespace(button=3, x=99999, y=99999))
        self.assertEqual(len(view.get_selected()), 1)

    def test_press_on_child_never_crashes(self):
        """The press handler must cope with the real translate_coordinates
        binding, which returns a 2-tuple (or None), never a 3-tuple."""
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        view.set_selected([Gtk.TreePath(0)])
        child = view.get_child_at_index(0)
        view.get_child_at_pos = lambda _x, _y: child
        try:
            view.on_button_press(view, SimpleNamespace(button=1, x=10, y=10))
        finally:
            del view.get_child_at_pos

    def test_stale_path_after_removal_returns_none(self):
        """Removing games must never crash selection mapping: paths that
        outlive their model rows resolve harmlessly instead of raising."""
        store = make_store([make_row("1", "Undertail"), make_row("2", "Doom")])
        game_store = SimpleNamespace(store=store, service=None, service_media=SimpleNamespace(size=(184, 69)))
        view = GameGridView(game_store)
        view.set_selected([Gtk.TreePath(0), Gtk.TreePath(1)])
        store.clear()
        # Stale but harmless pre-rebuild (callers already skip missing games);
        # the crash used to happen right here in model.get_iter().
        self.assertEqual(view.get_game_id_for_path(Gtk.TreePath(0)), "1")
        view._rebuild()
        self.assertIsNone(view.get_game_id_for_path(Gtk.TreePath(0)))
        self.assertIsNone(view.get_game_id_for_path(Gtk.TreePath(9)))
        self.assertEqual(view.get_selected(), [])

    def test_rebuild_emits_single_selection_event(self):
        store = make_store([make_row("1", "Undertail"), make_row("2", "Doom")])
        game_store = SimpleNamespace(store=store, service=None, service_media=SimpleNamespace(size=(184, 69)))
        view = GameGridView(game_store)
        view.set_selected([Gtk.TreePath(0)])
        emissions = []
        view.connect("game-selected", lambda _view, selection: emissions.append(list(selection)))
        view._rebuild()
        self.assertEqual(len(emissions), 1)

    def test_badges_anchor_to_art_overlay(self):
        view = make_view([make_row("1", "Undertail")])
        card = view._cards_by_id["1"]["card"]
        overlays = [c for c in card.get_children() if isinstance(c, Gtk.Overlay)]
        self.assertEqual(len(overlays), 1)
        self.assertEqual(overlays[0].get_halign(), Gtk.Align.CENTER)

    def test_star_button_present(self):
        view = make_view([make_row("1", "Undertail")])
        star_button = view._cards_by_id["1"]["star_button"]
        self.assertIsNotNone(star_button)
        classes = star_button.get_style_context().list_classes()
        self.assertIn("game-card-favorite", classes)

    def test_selection_syncs_card_class(self):
        view = make_view([make_row("1", "Undertail"), make_row("2", "Doom")])
        card = view._cards_by_id["1"]["card"]
        view.set_selected([Gtk.TreePath(0)])
        self.assertIn("selected", card.get_style_context().list_classes())
        view.set_selected([])
        self.assertNotIn("selected", card.get_style_context().list_classes())

    def test_generated_art(self):
        view = make_view([make_row("1", "Undertail")])
        first = view._generated_art(view.model, view.model.get_iter_first())
        second = view._generated_art(view.model, view.model.get_iter_first())
        self.assertIsNotNone(first)
        self.assertEqual((first.get_width(), first.get_height()), (184, 69))
        self.assertIs(first, second)

    def test_shared_generator_is_deterministic(self):
        from lutris.gui.widgets.utils import get_generated_game_art

        first = get_generated_game_art("7", "Undertail", (64, 64))
        second = get_generated_game_art("7", "Undertail", (64, 64))
        other = get_generated_game_art("8", "Doom", (64, 64))
        self.assertIsNotNone(first)
        self.assertEqual((first.get_width(), first.get_height()), (64, 64))
        self.assertEqual(bytes(first.get_data()), bytes(second.get_data()))
        self.assertNotEqual(bytes(first.get_data()), bytes(other.get_data()))
        self.assertIsNone(get_generated_game_art("7", "Undertail", (0, 64)))


class TestFavoriteToggle(unittest.TestCase):
    def setUp(self):
        if os.path.exists(settings.DB_PATH):
            os.remove(settings.DB_PATH)
        schema.syncdb()

    def test_toggle_adds_and_removes_favorite(self):
        game_id = games_db.add_game(name="Undertail", runner="linux")
        view = make_view([make_row(game_id, "Undertail")])
        star_button = view._cards_by_id[game_id]["star_button"]

        view._toggle_favorite(game_id)
        self.assertIn(game_id, view._favorite_ids)
        self.assertIn("favorite", categories_db.get_categories_in_game(game_id))
        self.assertIn("favorite-active", star_button.get_style_context().list_classes())

        view._toggle_favorite(game_id)
        self.assertNotIn(game_id, view._favorite_ids)
        self.assertNotIn("favorite", categories_db.get_categories_in_game(game_id))
        self.assertNotIn("favorite-active", star_button.get_style_context().list_classes())


if __name__ == "__main__":
    unittest.main()
