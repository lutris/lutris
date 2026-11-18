import os
import tempfile
import unittest
from unittest.mock import patch

from lutris.util import xdgshortcuts


class TestCreateLauncherStartupWMClass(unittest.TestCase):
    """A shortcut only binds its icon to the game's window when it names the window
    class Proton derives from the umu GAMEID."""

    def create(self, wm_class):
        with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as desktop_dir:
            with (
                patch.object(xdgshortcuts, "CACHE_DIR", data_dir),
                patch.object(xdgshortcuts.GLib, "get_user_special_dir", return_value=desktop_dir),
                patch.object(xdgshortcuts.GLib, "get_user_data_dir", return_value=data_dir),
                patch.object(xdgshortcuts, "get_lutris_executable", return_value="lutris"),
                patch.object(xdgshortcuts.LINUX_SYSTEM, "is_flatpak", return_value=False),
            ):
                xdgshortcuts.create_launcher(
                    "world-of-warcraft-battlenet", "35", "World of Warcraft", menu=True, wm_class=wm_class
                )
                path = os.path.join(data_dir, "applications", "net.lutris.world-of-warcraft-battlenet-35.desktop")
                with open(path, encoding="utf-8") as launcher:
                    return launcher.read()

    def test_a_window_class_is_written_into_the_shortcut(self):
        content = self.create("steam_app_lutris_35")
        self.assertIn("StartupWMClass=steam_app_lutris_35\n", content)
        # the rest of the entry is untouched
        self.assertIn("Icon=lutris_world-of-warcraft-battlenet", content)
        self.assertNotIn("\n\n", content)

    def test_no_window_class_means_no_key(self):
        content = self.create(None)
        self.assertNotIn("StartupWMClass", content)
        self.assertIn("Icon=lutris_world-of-warcraft-battlenet", content)
        self.assertNotIn("\n\n", content)
