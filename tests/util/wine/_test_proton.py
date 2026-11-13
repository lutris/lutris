import os
import tempfile
import time
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


class FakeGame:
    """Stands in for Game: the parser only sets these two attributes."""

    def __init__(self):
        self.launch_status = ""
        self.launch_progress_text_function = None


class TestUmuLaunchStatusParser(unittest.TestCase):
    """umu's setup messages become the game's launch status; while umu is
    downloading, the UI is also given a way to read the bytes received so far."""

    def feed(self, game, *lines):
        parser = proton.UmuLaunchStatusParser(game)
        for line in lines:
            parser(line + "\n")

    def test_download_sets_status_and_progress_text_function(self):
        game = FakeGame()
        self.feed(game, "[umu.umu_proton:414] INFO: Downloading GE-Proton10-34.tar.gz...")
        self.assertEqual(game.launch_status, "Downloading GE-Proton10-34.tar.gz...")
        self.assertIs(game.launch_progress_text_function, proton.get_umu_download_progress_text)

    def test_extracting_drops_progress_text_function(self):
        game = FakeGame()
        self.feed(
            game,
            "[umu.umu_runtime:163] INFO: Downloading steamrt4 (latest), please wait...",
            "[umu.umu_proton:610] INFO: Extracting GE-Proton10-34.tar.gz...",
        )
        self.assertEqual(game.launch_status, "Extracting GE-Proton10-34.tar.gz...")
        self.assertIsNone(game.launch_progress_text_function)


class TestGetUmuDownloadSize(unittest.TestCase):
    """umu downloads into '<name>.parts' inside a mkdtemp() directory, in the
    temp dir or under $XDG_CACHE_HOME/umu; the newest recent one is the download."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp_dir = os.path.join(temp.name, "tmp")
        self.cache_home = os.path.join(temp.name, "cache")
        os.makedirs(self.tmp_dir)
        os.makedirs(os.path.join(self.cache_home, "umu"))
        for patcher in (
            patch.object(proton.tempfile, "gettempdir", return_value=self.tmp_dir),
            patch.dict(os.environ, {"XDG_CACHE_HOME": self.cache_home}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_parts(self, directory, name, size, age=0.0):
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "wb") as parts_file:
            parts_file.write(b"x" * size)
        mtime = time.time() - age
        os.utime(path, (mtime, mtime))
        return path

    def test_nothing_downloading(self):
        self.assertIsNone(proton.get_umu_download_size())
        self.assertEqual(proton.get_umu_download_progress_text(), "")

    def test_download_on_tmpfs(self):
        self.make_parts(os.path.join(self.tmp_dir, "tmpab12"), "GE-Proton10-34.tar.gz.parts", 2048)
        self.assertEqual(proton.get_umu_download_size(), 2048)
        self.assertEqual(proton.get_umu_download_progress_text(), "2.0 kB")

    def test_download_in_hidden_cache_dir(self):
        hidden_dir = os.path.join(self.cache_home, "umu", ".tmpcd34")
        self.make_parts(hidden_dir, "SteamLinuxRuntime_4.tar.xz.123.parts", 4096)
        self.assertEqual(proton.get_umu_download_size(), 4096)

    def test_newest_download_wins(self):
        self.make_parts(os.path.join(self.tmp_dir, "tmpold"), "old.parts", 100, age=10)
        self.make_parts(os.path.join(self.cache_home, "umu", "tmpnew"), "new.parts", 200)
        self.assertEqual(proton.get_umu_download_size(), 200)

    def test_stale_partial_is_ignored(self):
        self.make_parts(os.path.join(self.tmp_dir, "tmpdead"), "old.parts", 100, age=300)
        self.assertIsNone(proton.get_umu_download_size())

    def test_other_files_are_ignored(self):
        self.make_parts(os.path.join(self.tmp_dir, "tmpab12"), "GE-Proton10-34.tar.gz", 100)
        self.make_parts(self.tmp_dir, "loose.parts", 100)
        self.assertIsNone(proton.get_umu_download_size())
