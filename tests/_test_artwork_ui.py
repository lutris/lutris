import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402

from lutris.gui.config.game_common import GameDialogCommon  # noqa: E402
from lutris.gui.config.game_info_box import GameInfoBox  # noqa: E402
from lutris.gui.config.preferences_box import InterfacePreferencesBox  # noqa: E402
from lutris.gui.lutriswindow import LutrisWindow  # noqa: E402
from lutris.gui.widgets.artwork_source import ArtworkSourceButtons  # noqa: E402

GTK_AVAILABLE = Gtk.init_check()[0]


class TestArtworkPreferences(TestCase):
    def test_source_change_persists_then_refreshes_inherited_games(self):
        events = []
        with (
            patch("lutris.gui.config.preferences_box.settings.write_setting", side_effect=lambda *a: events.append(a)),
            patch("lutris.gui.config.preferences_box.AsyncCall", side_effect=lambda *a, **kw: events.append((a, kw))),
        ):
            InterfacePreferencesBox.on_artwork_source_changed(Mock(), "lutris")
        self.assertEqual(events[0], ("artwork_source", "lutris"))
        self.assertEqual(events[1][1], {"force": True, "inherited_only": True})

    def test_steamgriddb_without_key_keeps_selection_and_prompts(self):
        dialog = Mock()
        box = Mock()
        with (
            patch("lutris.gui.config.preferences_box.settings.write_setting") as write,
            patch("lutris.gui.config.preferences_box.settings.read_setting", return_value=""),
            patch("lutris.gui.config.preferences_box.AsyncCall") as refresh,
            patch("lutris.gui.config.preferences_box.Gtk.MessageDialog", return_value=dialog),
        ):
            InterfacePreferencesBox.on_artwork_source_changed(box, "steamgriddb")
        write.assert_called_once_with("artwork_source", "steamgriddb")
        refresh.assert_called_once()
        dialog.run.assert_called_once()

    def test_inherited_help_tracks_effective_source(self):
        help_label = Mock()
        box = SimpleNamespace(artwork_source_help=help_label)
        with patch("lutris.gui.config.game_info_box.settings.read_setting", return_value="steamgriddb"):
            GameInfoBox._on_artwork_source_changed(box, None)
            help_label.set_visible.assert_called_with(True)
            GameInfoBox._on_artwork_source_changed(box, "lutris")
            help_label.set_visible.assert_called_with(False)

    def test_save_callback_distinguishes_no_match_error_and_stale_results(self):
        dialog = Mock()
        dialog.game.id = "1"
        dialog.game.name = "Old"
        dialog.game.artwork_source = None
        dialog.game.custom_images = {"icon"}
        dialog.info_box.name_entry.get_text.return_value = "New"
        dialog.info_box.sortname_entry.get_text.return_value = ""
        dialog.info_box.year_entry.get_text.return_value = ""
        dialog.info_box.playtime_entry.get_text.return_value = ""
        dialog.info_box.artwork_source_buttons.get_value.return_value = "steamgriddb"
        dialog.info_box.slug = dialog.info_box.initial_slug = "game"
        dialog.lutris_config.game_config_id = "game"
        window = SimpleNamespace(
            show_artwork_toast=Mock(), _artwork_request_generations={}, _artwork_window_destroyed=False
        )
        dialog.get_transient_for.return_value = window
        row = {"id": "1", "name": "New", "artwork_source": "steamgriddb"}
        with (
            patch("lutris.gui.config.game_common.rename_config", return_value=None),
            patch("lutris.gui.config.game_common.AsyncCall") as worker,
            patch("lutris.database.games.get_games_by_ids", return_value=[row]),
        ):
            GameDialogCommon.on_save(dialog, None)
            callback = worker.call_args.args[1]
            result = SimpleNamespace(game_id="1", title="New", source="steamgriddb", status="no_match")
            callback({"1": result}, None)
            self.assertIn("No SteamGridDB match", window.show_artwork_toast.call_args.args[0])
            callback(None, RuntimeError("authentication"))
            self.assertIn("Couldn't look up", window.show_artwork_toast.call_args.args[0])
            window.show_artwork_toast.reset_mock()
            window._artwork_request_generations["1"] += 1
            callback({"1": result}, None)
            window.show_artwork_toast.assert_not_called()


class TestArtworkGtk(TestCase):
    def setUp(self):
        if not GTK_AVAILABLE:
            self.skipTest("GTK display unavailable")

    def test_linked_buttons_are_exclusive_and_do_not_emit_on_init(self):
        changed = Mock()
        buttons = ArtworkSourceButtons([("Lutris.net", "lutris"), ("SteamGridDB", "steamgriddb")], "lutris", changed)
        changed.assert_not_called()
        buttons.buttons["steamgriddb"].set_active(True)
        self.assertEqual(buttons.get_value(), "steamgriddb")
        self.assertFalse(buttons.buttons["lutris"].get_active())
        changed.assert_called_once_with("steamgriddb")
        buttons.destroy()

    def test_per_game_buttons_can_return_to_global(self):
        changed = Mock()
        buttons = ArtworkSourceButtons(
            [("Use global", None), ("Lutris.net", "lutris"), ("SteamGridDB", "steamgriddb")], None, changed
        )
        buttons.buttons["steamgriddb"].set_active(True)
        buttons.buttons[None].set_active(True)
        self.assertIsNone(buttons.get_value())
        self.assertEqual(changed.call_args_list[-1].args, (None,))
        buttons.destroy()

    def test_toast_is_bottom_center_plain_text_and_replaces_timer(self):
        revealer = Gtk.Revealer(halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
        label = Gtk.Label()
        window = SimpleNamespace(_artwork_toast=revealer, _artwork_toast_label=label, _artwork_toast_timer=None)
        LutrisWindow.show_artwork_toast(window, "<not markup>")
        self.assertEqual(label.get_text(), "<not markup>")
        self.assertTrue(revealer.get_reveal_child())
        first_timer = window._artwork_toast_timer
        LutrisWindow.show_artwork_toast(window, "new")
        self.assertNotEqual(first_timer, window._artwork_toast_timer)
        self.assertEqual(revealer.get_halign(), Gtk.Align.CENTER)
        self.assertEqual(revealer.get_valign(), Gtk.Align.END)
        GLib.source_remove(window._artwork_toast_timer)
        revealer.destroy()
        label.destroy()

    def test_toast_timeout_hides_it(self):
        revealer = Gtk.Revealer()
        label = Gtk.Label()
        window = SimpleNamespace(_artwork_toast=revealer, _artwork_toast_label=label, _artwork_toast_timer=None)
        with patch("lutris.gui.lutriswindow.GLib.timeout_add_seconds", return_value=123) as timeout:
            LutrisWindow.show_artwork_toast(window, "message")
        self.assertFalse(timeout.call_args.args[1]())
        self.assertFalse(revealer.get_reveal_child())
        self.assertIsNone(window._artwork_toast_timer)
        revealer.destroy()
        label.destroy()

    def test_manual_save_preserves_dimensions_and_notifies(self):
        game = SimpleNamespace(id="1", custom_images=set())
        box = SimpleNamespace(game=game, parent_widget=Mock(), _artwork_destroyed=False, image_refreshed_cb=Mock())
        dimensions = []

        def publish(_game_id, _kind, image_path):
            image = GdkPixbuf.Pixbuf.new_from_file(image_path)
            dimensions.append((image.get_width(), image.get_height()))

        def run(worker, callback, **_kwargs):
            callback(worker(), None)

        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "image.png")
            image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1000, 500)
            image.fill(0x123456FF)
            image.savev(path, "png", [], [])
            with (
                patch("lutris.artwork.save_custom_artwork", side_effect=publish),
                patch("lutris.gui.config.game_info_box.AsyncCall", side_effect=run),
                patch("lutris.gui.config.game_info_box.GAME_UPDATED.fire") as updated,
            ):
                GameInfoBox.save_custom_media(box, "banner", path)
        self.assertEqual(dimensions, [(1000, 500)])
        self.assertIn("banner", game.custom_images)
        updated.assert_called_once_with(game)

    def test_failed_reset_retains_flag_and_success_notifies(self):
        game = SimpleNamespace(id="1", custom_images={"icon"})
        box = SimpleNamespace(game=game, parent_widget=Mock(), _artwork_destroyed=False, image_refreshed_cb=Mock())
        callbacks = []
        with (
            patch("lutris.artwork.reset_custom_artwork"),
            patch(
                "lutris.gui.config.game_info_box.AsyncCall", side_effect=lambda _f, cb, *_a, **_kw: callbacks.append(cb)
            ),
            patch("lutris.gui.config.game_info_box.GAME_UPDATED.fire") as updated,
        ):
            GameInfoBox.refresh_image(box, "icon")
            callbacks[-1](SimpleNamespace(status="error"), None)
            self.assertIn("icon", game.custom_images)
            updated.assert_not_called()
            GameInfoBox.refresh_image(box, "icon")
            callbacks[-1](SimpleNamespace(status="success"), None)
            self.assertNotIn("icon", game.custom_images)
            updated.assert_called_once_with(game)
