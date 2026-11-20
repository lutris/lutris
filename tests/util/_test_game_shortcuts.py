import os
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from gi.repository import Gio, GLib

from lutris import settings
from lutris.config import write_game_config
from lutris.database import games, schema
from lutris.game import Game
from lutris.util import xdgshortcuts


class TestGameShortcutNames(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.desktop = self.directory / "Desktop"
        self.data = self.directory / "data"
        (self.directory / "games").mkdir()
        # Gio checks TryExec; no game or launcher process needs to run here.
        (self.directory / "lutris").symlink_to("/bin/true")
        patches = [
            patch.object(settings, "DB_PATH", str(self.directory / "pga.db")),
            patch.object(settings, "CONFIG_DIR", directory.name),
            patch.object(xdgshortcuts, "CACHE_DIR", directory.name),
            patch.object(GLib, "get_user_special_dir", return_value=str(self.desktop)),
            patch.object(GLib, "get_user_data_dir", return_value=str(self.data)),
            patch.object(xdgshortcuts.LINUX_SYSTEM, "is_flatpak", return_value=False),
            patch.dict(os.environ, {"PATH": directory.name + os.pathsep + os.environ["PATH"]}),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        schema.syncdb()
        config = write_game_config("shortcut-test", {"game": {"exe": "/bin/true"}, "linux": {}})
        game_id = games.add_game(
            name="Original Game", slug="shortcut-test", runner="linux", configpath=config, installed=1
        )
        self.game = Game(str(game_id))

    def create_launchers(self):
        xdgshortcuts.create_launcher(
            self.game.slug, self.game.id, self.game.name, launch_config_name="Alternate launch", desktop=True, menu=True
        )
        return [
            Path(xdgshortcuts.get_launcher_path(self.game.slug, self.game.id)),
            Path(xdgshortcuts.get_menu_launcher_path(self.game.slug, self.game.id)),
        ]

    def rename_game(self):
        self.game.name = "Renamed Game: \u65e5\u672c\u8a9e"
        self.game.save(no_signal=True)
        self.assertEqual(games.get_game_by_field(self.game.id, "id")["name"], self.game.name)

    def assert_launcher_name(self, path, name):
        app = Gio.DesktopAppInfo.new_from_filename(str(path))
        self.assertIsNotNone(app)
        self.assertEqual(app.get_display_name(), name)

    def test_rename_updates_existing_menu_and_desktop_names_without_rebuilding_launchers(self):
        paths = self.create_launchers()
        modes = [0o754, 0o664]
        for path, mode in zip(paths, modes):
            path.write_text(path.read_text() + "# Keep this comment\nX-Custom=keep me\nName[fr]=Mon jeu\n")
            path.chmod(mode)
        before = [
            path.read_text().replace("Name=Original Game", "Name=Renamed Game: \u65e5\u672c\u8a9e") for path in paths
        ]
        self.rename_game()
        for path, expected, mode in zip(paths, before, modes):
            with self.subTest(path=path):
                # The localized display name intentionally remains "Mon jeu" in French.
                app = Gio.DesktopAppInfo.new_from_filename(str(path))
                self.assertEqual(app.get_string("Name"), self.game.name)
                self.assertEqual(path.read_text().strip(), expected.strip())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)

    def test_rename_updates_legacy_launcher_filenames(self):
        paths = self.create_launchers()
        for path, filename in zip(paths, [self.game.slug + ".desktop", f"{self.game.slug}-{self.game.id}.desktop"]):
            path.rename(path.with_name(filename))
        self.rename_game()
        self.assert_launcher_name(self.desktop / (self.game.slug + ".desktop"), self.game.name)
        self.assert_launcher_name(
            self.data / "applications" / f"{self.game.slug}-{self.game.id}.desktop", self.game.name
        )

    def test_rename_uses_the_saved_slug_to_find_existing_launchers(self):
        paths = self.create_launchers()
        self.game.slug = "new-slug"
        self.rename_game()
        for path in paths:
            self.assert_launcher_name(path, self.game.name)
        self.assertEqual(len(list(self.desktop.iterdir())), 1)
        self.assertEqual(len(list((self.data / "applications").iterdir())), 1)

    def test_save_without_a_name_change_does_not_rewrite_launchers(self):
        paths = self.create_launchers()
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        self.game.sortname = "Other sort order"
        self.game.save(no_signal=True)
        self.assertEqual([(path.read_bytes(), path.stat().st_mtime_ns) for path in paths], before)

    def test_rename_preserves_a_custom_shortcut_name(self):
        paths = self.create_launchers()
        paths[0].write_text(paths[0].read_text().replace("Name=Original Game", "Name=Custom shortcut"))
        custom = paths[0].read_bytes()
        self.rename_game()
        self.assertEqual(paths[0].read_bytes(), custom)
        self.assert_launcher_name(paths[1], self.game.name)

    def test_rename_does_not_create_missing_launchers(self):
        self.rename_game()
        self.assertFalse(self.desktop.exists())
        self.assertFalse(self.data.exists())

    def test_saving_a_new_game_does_not_create_launchers(self):
        game = Game()
        game.name = "New game"
        game.slug = "new-game"
        game.runner_name = "linux"
        game.save(no_signal=True)
        self.assertTrue(game.is_db_stored)
        self.assertFalse(self.desktop.exists())
        self.assertFalse(self.data.exists())

    def test_rename_updates_menu_when_no_desktop_directory_is_configured(self):
        paths = self.create_launchers()
        with patch.object(GLib, "get_user_special_dir", return_value=None):
            self.rename_game()
        self.assert_launcher_name(paths[1], self.game.name)

    def test_rename_updates_the_flatpak_shared_menu_directory(self):
        with (
            patch.object(xdgshortcuts.LINUX_SYSTEM, "is_flatpak", return_value=True),
            patch.dict(os.environ, {"HOME": str(self.directory)}),
        ):
            xdgshortcuts.create_launcher(self.game.slug, self.game.id, self.game.name, menu=True)
            path = (
                self.directory
                / ".local/share/applications"
                / xdgshortcuts.get_xdg_basename(self.game.slug, self.game.id)
            )
            self.rename_game()
            self.assert_launcher_name(path, self.game.name)
        self.assertFalse(self.data.exists())

    def test_invalid_launcher_does_not_prevent_saving_or_updating_other_launchers(self):
        paths = self.create_launchers()
        paths[0].write_text("not a desktop entry\n")
        with self.assertLogs(xdgshortcuts.logger, level="WARNING"):
            self.rename_game()
        self.assertEqual(paths[0].read_text(), "not a desktop entry\n")
        self.assert_launcher_name(paths[1], self.game.name)

    def test_rename_keeps_a_symlinked_launcher(self):
        paths = self.create_launchers()
        target = self.directory / "linked.desktop"
        paths[0].rename(target)
        paths[0].symlink_to(target)
        self.rename_game()
        self.assertTrue(paths[0].is_symlink())
        self.assert_launcher_name(target, self.game.name)
        self.assert_launcher_name(paths[1], self.game.name)

    def test_unwritable_launcher_does_not_prevent_saving_or_updating_other_launchers(self):
        paths = self.create_launchers()
        before = paths[0].read_bytes()
        self.desktop.chmod(0o555)
        try:
            with self.assertLogs(xdgshortcuts.logger, level="WARNING"):
                self.rename_game()
        finally:
            self.desktop.chmod(0o755)
        self.assertEqual(paths[0].read_bytes(), before)
        self.assert_launcher_name(paths[1], self.game.name)
