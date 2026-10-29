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
