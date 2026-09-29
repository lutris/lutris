import os
import unittest
from unittest.mock import patch

from lutris.util.wine import proton

LUTRIS_ENV = {"HOME": "/home/player", "XDG_DATA_HOME": "/home/player/.local/share"}


@patch.object(proton.LINUX_SYSTEM, "is_flatpak", return_value=False)
class TestUmuFoldersPath(unittest.TestCase):
    """Where Umu keeps its runtime when a game moves its own directories.

    Umu reads XDG_DATA_HOME (HOST_XDG_DATA_HOME under Flatpak) to decide where to
    download the runtime and Proton builds. A game that overrides it to keep its
    saves elsewhere dragged those downloads along with it.
    """

    def get_path(self, env, environ=None):
        with patch.dict(os.environ, LUTRIS_ENV if environ is None else environ, clear=True):
            return proton.get_umu_folders_path(env)

    def test_untouched_environment_is_left_to_umu(self, _is_flatpak):
        self.assertEqual(self.get_path({}), "")
        self.assertEqual(self.get_path(dict(LUTRIS_ENV)), "")

    def test_game_overriding_the_data_home_keeps_umu_in_place(self, _is_flatpak):
        env = dict(LUTRIS_ENV, XDG_DATA_HOME="/games/witcher/data")
        self.assertEqual(self.get_path(env), "/home/player/.local/share")

    def test_game_overriding_home_keeps_umu_in_place(self, _is_flatpak):
        """Umu falls back to Path.home(), so HOME moves the downloads too."""
        env = dict(LUTRIS_ENV, HOME="/games/witcher")
        self.assertEqual(self.get_path(env), "/home/player/.local/share")

    def test_falls_back_to_the_default_share_directory(self, _is_flatpak):
        environ = {"HOME": "/home/player"}
        env = {"XDG_DATA_HOME": "/games/witcher/data"}
        self.assertEqual(self.get_path(env, environ), "/home/player/.local/share")

    def test_nothing_to_point_at_means_nothing_is_set(self, _is_flatpak):
        self.assertEqual(self.get_path({"XDG_DATA_HOME": "/games/x"}, environ={}), "")

    def test_update_proton_env_sets_it_only_when_needed(self, _is_flatpak):
        with patch.dict(os.environ, LUTRIS_ENV, clear=True):
            plain = dict(LUTRIS_ENV)
            proton.update_proton_env("/wine", plain)
            self.assertNotIn("UMU_FOLDERS_PATH", plain)

            moved = dict(LUTRIS_ENV, XDG_DATA_HOME="/games/witcher/data")
            proton.update_proton_env("/wine", moved)
            self.assertEqual(moved["UMU_FOLDERS_PATH"], "/home/player/.local/share")
            # the game still sees the directories it asked for
            self.assertEqual(moved["XDG_DATA_HOME"], "/games/witcher/data")

    def test_an_explicit_setting_is_never_overwritten(self, _is_flatpak):
        with patch.dict(os.environ, LUTRIS_ENV, clear=True):
            env = dict(LUTRIS_ENV, XDG_DATA_HOME="/games/x", UMU_FOLDERS_PATH="/chosen")
            proton.update_proton_env("/wine", env)
            self.assertEqual(env["UMU_FOLDERS_PATH"], "/chosen")


class TestUmuFoldersPathInFlatpak(unittest.TestCase):
    @patch.object(proton.LINUX_SYSTEM, "is_flatpak", return_value=True)
    def test_flatpak_uses_the_host_data_home(self, _is_flatpak):
        environ = {"HOME": "/home/player", "HOST_XDG_DATA_HOME": "/home/player/.local/share"}
        with patch.dict(os.environ, environ, clear=True):
            # XDG_DATA_HOME inside the sandbox is not what Umu reads there
            self.assertEqual(proton.get_umu_folders_path({"XDG_DATA_HOME": "/games/x"}), "")
            moved = {"HOST_XDG_DATA_HOME": "/games/x"}
            self.assertEqual(proton.get_umu_folders_path(moved), "/home/player/.local/share")
