import json
import os
import tempfile
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


INSTALLED_PROTONS = {
    "GE-Proton11-7-x86_64": "/compat/GE-Proton11-7-x86_64",
    "GE-Proton10-34": "/compat/GE-Proton10-34",
}


@patch.object(proton.LINUX_SYSTEM, "arch", "x86_64")
@patch.object(proton, "get_proton_versions", return_value=INSTALLED_PROTONS)
class TestFindProtonVersion(unittest.TestCase):
    """GE-Proton versions are normalized to the bare release tag, while GE-Proton 11
    and later install into '<tag>-<arch>' folders."""

    def test_bare_tag_matches_an_arch_suffixed_folder(self, _versions):
        self.assertEqual(proton.find_proton_version("GE-Proton11-7"), "GE-Proton11-7-x86_64")
        self.assertTrue(proton.is_proton_version("GE-Proton11-7"))

    def test_exact_folder_name_matches(self, _versions):
        self.assertEqual(proton.find_proton_version("GE-Proton10-34"), "GE-Proton10-34")
        self.assertEqual(proton.find_proton_version("GE-Proton11-7-x86_64"), "GE-Proton11-7-x86_64")

    def test_missing_versions_do_not_match(self, _versions):
        self.assertIsNone(proton.find_proton_version("GE-Proton11-8"))
        self.assertIsNone(proton.find_proton_version(""))
        self.assertIsNone(proton.find_proton_version(None))


class TestIsGeProtonRelease(unittest.TestCase):
    def test_release_tags(self):
        self.assertTrue(proton.is_ge_proton_release("GE-Proton11-7"))
        self.assertTrue(proton.is_ge_proton_release("GE-Proton9-26"))

    def test_sentinel_and_other_versions_are_not_releases(self):
        self.assertFalse(proton.is_ge_proton_release("ge-proton"))
        self.assertFalse(proton.is_ge_proton_release("wine-ge-8-26-x86_64"))
        self.assertFalse(proton.is_ge_proton_release("Proton 11.0"))
        self.assertFalse(proton.is_ge_proton_release(None))


class TestSteamCompatDir(unittest.TestCase):
    @patch.object(proton.LINUX_SYSTEM, "is_flatpak", return_value=False)
    def test_follows_xdg_data_home(self, _is_flatpak):
        with patch.dict(os.environ, {"HOME": "/home/player", "XDG_DATA_HOME": "/data"}, clear=True):
            self.assertEqual(proton.get_steam_compat_dir(), "/data/Steam/compatibilitytools.d")

    @patch.object(proton.LINUX_SYSTEM, "is_flatpak", return_value=True)
    def test_flatpak_uses_the_host_data_home(self, _is_flatpak):
        environ = {"HOME": "/home/player", "XDG_DATA_HOME": "/sandbox", "HOST_XDG_DATA_HOME": "/host"}
        with patch.dict(os.environ, environ, clear=True):
            self.assertEqual(proton.get_steam_compat_dir(), "/host/Steam/compatibilitytools.d")


def make_release(*names):
    return {"assets": [{"name": name, "browser_download_url": "https://dl/" + name} for name in names]}


@patch.object(proton.LINUX_SYSTEM, "arch", "x86_64")
class TestGeProtonReleaseUrls(unittest.TestCase):
    def get_urls(self, release):
        with patch.object(proton, "Request") as request:
            request.return_value.get.return_value.json = release
            return proton.get_ge_proton_release_urls("GE-Proton11-7")

    def test_picks_the_build_for_this_architecture(self):
        release = make_release(
            "GE-Proton11-7-aarch64.sha512sum",
            "GE-Proton11-7-aarch64.tar.gz",
            "GE-Proton11-7-x86_64.sha512sum",
            "GE-Proton11-7-x86_64.tar.gz",
        )
        self.assertEqual(
            self.get_urls(release),
            ("https://dl/GE-Proton11-7-x86_64.tar.gz", "https://dl/GE-Proton11-7-x86_64.sha512sum"),
        )

    def test_older_releases_have_no_arch_suffix(self):
        release = make_release("GE-Proton11-7.sha512sum", "GE-Proton11-7.tar.gz")
        self.assertEqual(
            self.get_urls(release), ("https://dl/GE-Proton11-7.tar.gz", "https://dl/GE-Proton11-7.sha512sum")
        )

    def test_no_build_without_a_checksum(self):
        self.assertIsNone(self.get_urls(make_release("GE-Proton11-7-x86_64.tar.gz")))
        self.assertIsNone(self.get_urls({}))


class TestGetUmuId(unittest.TestCase):
    """The umu GAMEID decides the window class Proton gives a game, so games without a
    store appid need one of their own rather than the shared umu-default."""

    def test_games_without_a_store_id_get_their_own_umu_id(self):
        self.assertEqual(proton.get_umu_id("35", None, None, {}), "umu-lutris_35")
        self.assertEqual(proton.get_wm_class(proton.get_umu_id("35", None, None, {})), "steam_app_lutris_35")

    def test_a_game_without_a_database_id_keeps_the_default(self):
        self.assertEqual(proton.get_umu_id(None, None, None, {}), proton.DEFAULT_GAMEID)

    def test_an_explicit_umu_id_wins(self):
        self.assertEqual(proton.get_umu_id("35", None, None, {"UMU_ID": "umu-15522"}), "umu-15522")

    def test_store_games_use_the_umu_games_mapping(self):
        with tempfile.TemporaryDirectory() as runtime_dir:
            games_dir = os.path.join(runtime_dir, "umu-games")
            os.makedirs(games_dir)
            with open(os.path.join(games_dir, "umu-games.json"), "w", encoding="utf-8") as games_file:
                json.dump([{"store": "steam", "appid": "15522", "umu_id": "umu-15522"}], games_file)

            with patch.object(proton.settings, "RUNTIME_DIR", runtime_dir):
                self.assertEqual(proton.get_umu_id("35", "steam", "15522", {}), "umu-15522")
                self.assertEqual(proton.get_umu_id("35", "steam", "99999", {}), "umu-lutris_35")
                # Humble's service is called 'humblebundle' in Lutris but 'humble' in umu.
                self.assertEqual(proton.get_umu_id("35", "humblebundle", "15522", {}), "umu-lutris_35")

            with open(os.path.join(games_dir, "umu-games.json"), "w", encoding="utf-8") as games_file:
                json.dump([{"store": "humble", "appid": "abc", "umu_id": "umu-humble_abc"}], games_file)

            with patch.object(proton.settings, "RUNTIME_DIR", runtime_dir):
                self.assertEqual(proton.get_umu_id("35", "humblebundle", "abc", {}), "umu-humble_abc")

    def test_a_missing_mapping_file_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as runtime_dir:
            with patch.object(proton.settings, "RUNTIME_DIR", runtime_dir):
                self.assertEqual(proton.get_umu_id("35", "steam", "15522", {}), "umu-lutris_35")


class TestGetWmClass(unittest.TestCase):
    """Proton only derives a window class from GAMEIDs that follow umu's scheme."""

    def test_umu_ids_map_to_proton_window_classes(self):
        self.assertEqual(proton.get_wm_class("umu-lutris_35"), "steam_app_lutris_35")
        self.assertEqual(proton.get_wm_class("umu-default"), "steam_app_default")
        self.assertEqual(proton.get_wm_class("umu-15522"), "steam_app_15522")

    def test_other_ids_have_no_window_class(self):
        self.assertIsNone(proton.get_wm_class("custom-id"))
        self.assertIsNone(proton.get_wm_class(""))
        self.assertIsNone(proton.get_wm_class(None))
