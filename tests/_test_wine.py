import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.runners import wine
from lutris.settings import WINE_DIR
from lutris.util.test_config import setup_test_environment
from lutris.util.wine.dll_manager import DLLManager

setup_test_environment()


class TestDllOverrides(TestCase):
    def test_env_format(self):
        overrides = {
            "d3dcompiler_43": "native,builtin",
            "d3dcompiler_47": "native,builtin",
            "dnsapi": " builtin",
            "dwrite": " disabled",
            "winemenubuilder": "disabled",
            "rasapi32": " native",
        }
        env_string = wine.get_overrides_env(overrides)
        self.assertEqual(env_string, "d3dcompiler_43,d3dcompiler_47=n,b;dnsapi=b;rasapi32=n;dwrite,winemenubuilder=")


class TestDllManager(TestCase):
    def test_numeric_version_is_normalized(self):
        manager = DLLManager(version=2.6)
        self.assertEqual(manager.version, "2.6")


class TestDxvkVersionWarning(TestCase):
    def test_numeric_version_does_not_raise(self):
        config = SimpleNamespace(runner_config={"dxvk": True, "dxvk_version": 2.6})
        with (
            patch.object(wine.LINUX_SYSTEM, "is_vulkan_supported", return_value=True),
            patch.object(wine.vkquery, "get_vulkan_api_version", return_value=None),
        ):
            self.assertIsNone(wine._get_dxvk_version_warning("dxvk_version", config))


class TestInstallerRunnerVersion(TestCase):
    """A fresh install with no Wine version anywhere must use the umu default and
    never ask the API, whose 'latest' build would be downloaded for nothing."""

    def get_installer(self, script):
        return SimpleNamespace(runner="wine", script=script, requires=None)

    @patch.object(wine.wine, "get_runner_version_and_config", side_effect=wine.UnspecifiedVersionError("unset"))
    def test_unspecified_version_uses_default(self, _get_config):
        runner = wine.wine()
        with patch.object(runner, "get_runner_version") as get_runner_version:
            version = runner.get_installer_runner_version(self.get_installer({}), use_default=True)
        self.assertEqual(version, wine.get_default_wine_version())
        get_runner_version.assert_not_called()

    @patch.object(wine.wine, "get_runner_version_and_config", side_effect=wine.UnspecifiedVersionError("unset"))
    def test_unspecified_version_needs_no_runner_install(self, _get_config):
        runner = wine.wine()
        interpreter = SimpleNamespace(installer=self.get_installer({}))
        with patch.object(runner, "get_runner_version") as get_runner_version:
            self.assertTrue(runner.is_installed_for(interpreter))
        get_runner_version.assert_not_called()

    def test_script_version_is_kept(self):
        runner = wine.wine()
        installer = self.get_installer({"wine": {"version": "wine-ge-8-26-x86_64"}})
        self.assertEqual(runner.get_installer_runner_version(installer, use_default=True), "wine-ge-8-26-x86_64")

    @patch.object(
        wine.proton, "get_proton_versions", return_value={"GE-Proton11-7-x86_64": "/compat/GE-Proton11-7-x86_64"}
    )
    def test_pinned_ge_proton_tag_is_kept(self, _versions):
        runner = wine.wine()
        installer = self.get_installer({"wine": {"version": "GE-Proton11-7"}})
        self.assertEqual(runner.get_installer_runner_version(installer, use_default=True), "GE-Proton11-7")


class TestPinnedGeProton(TestCase):
    """A pinned GE-Proton release must come from GitHub into compatibilitytools.d:
    umu only downloads the latest GE-Proton, and the Lutris API doesn't serve them."""

    def get_interpreter(self, version):
        return SimpleNamespace(
            installer=SimpleNamespace(runner="wine", script={"wine": {"version": version}}, requires=None)
        )

    @patch.object(
        wine.proton, "get_proton_versions", return_value={"GE-Proton11-7-x86_64": "/compat/GE-Proton11-7-x86_64"}
    )
    def test_installed_release_needs_no_install(self, _versions):
        self.assertTrue(wine.wine().is_installed_for(self.get_interpreter("GE-Proton11-7")))

    @patch.object(wine.proton, "get_proton_versions", return_value={})
    def test_missing_release_needs_an_install(self, _versions):
        self.assertFalse(wine.wine().is_installed_for(self.get_interpreter("GE-Proton11-7")))

    @patch.object(wine.proton, "get_proton_versions", return_value={})
    def test_missing_release_is_downloaded_from_github(self, _versions):
        runner = wine.wine()
        with (
            patch.object(runner, "install_ge_proton") as install_ge_proton,
            patch.object(runner, "get_runner_version") as get_runner_version,
        ):
            runner.install(None, version="GE-Proton11-7")
        install_ge_proton.assert_called_once_with(None, "GE-Proton11-7", callback=None)
        get_runner_version.assert_not_called()

    @patch.object(wine.proton, "get_steam_compat_dir")
    @patch.object(wine.proton, "get_ge_proton_checksum")
    @patch.object(
        wine.proton,
        "get_ge_proton_release_urls",
        return_value=("https://dl/GE-Proton11-7-x86_64.tar.gz", "https://dl/GE-Proton11-7-x86_64.sha512sum"),
    )
    def test_download_is_verified_and_extracted_to_compat_dir(self, _urls, get_checksum, get_compat_dir):
        with tempfile.TemporaryDirectory() as temp_dir:
            compat_dir = os.path.join(temp_dir, "compatibilitytools.d")
            get_compat_dir.return_value = compat_dir
            payload = b"GE-Proton build"
            get_checksum.return_value = hashlib.sha512(payload).hexdigest()

            def download(_url, destination):
                with open(destination, "wb") as archive:
                    archive.write(payload)
                return True

            delegate = SimpleNamespace(download_install_file=download)
            runner = wine.wine()
            with (
                patch.object(wine.settings, "CACHE_DIR", temp_dir),
                patch.object(runner, "extract") as extract,
            ):
                runner.install_ge_proton(delegate, "GE-Proton11-7")
            extract.assert_called_once_with(
                archive=os.path.join(temp_dir, "GE-Proton11-7-x86_64.tar.gz"),
                dest=compat_dir,
                merge_single=False,
                callback=None,
            )

    @patch.object(wine.proton, "get_ge_proton_checksum", return_value="0" * 128)
    @patch.object(
        wine.proton,
        "get_ge_proton_release_urls",
        return_value=("https://dl/GE-Proton11-7-x86_64.tar.gz", "https://dl/GE-Proton11-7-x86_64.sha512sum"),
    )
    def test_corrupt_download_is_rejected(self, _urls, _checksum):
        with tempfile.TemporaryDirectory() as temp_dir:

            def download(_url, destination):
                with open(destination, "wb") as archive:
                    archive.write(b"truncated")
                return True

            runner = wine.wine()
            with (
                patch.object(wine.settings, "CACHE_DIR", temp_dir),
                patch.object(runner, "extract") as extract,
                self.assertRaises(wine.RunnerInstallationError),
            ):
                runner.install_ge_proton(SimpleNamespace(download_install_file=download), "GE-Proton11-7")
            extract.assert_not_called()
            self.assertEqual(os.listdir(temp_dir), [])

    @patch.object(wine.proton, "get_ge_proton_release_urls", return_value=None)
    def test_release_without_a_build_fails_cleanly(self, _urls):
        with self.assertRaises(wine.RunnerInstallationError):
            wine.wine().install_ge_proton(SimpleNamespace(), "GE-Proton11-7")


class TestMissingWineVersion(TestCase):
    """A missing Wine version falls back to GE-Proton through umu, which would upgrade
    a plain Wine prefix to Proton for good."""

    def setUp(self):
        self.game_config = {}
        self.game_version = "wine-test-missing-1"
        for patcher in (
            patch("lutris.config.read_yaml_from_file", side_effect=self.read_yaml),
            patch.dict(os.environ, {"WINEPREFIX": ""}),
            patch.object(wine.proton, "get_umu_path", return_value="/umu/umu-run"),
            patch.object(
                wine.system,
                "path_exists",
                side_effect=lambda path, *args, **kwargs: path == "/umu/umu-run" or os.path.exists(path),
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def read_yaml(self, path):
        if path.endswith("game.yml"):
            if not self.game_version:
                return {"game": self.game_config}
            return {"game": self.game_config, "wine": {"version": self.game_version}}
        if path.endswith("wine.yml"):
            return {"wine": {"version": "wine-test-missing-1"}}
        return {}

    def make_prefix(self, *files):
        prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, prefix)
        for name in ("user.reg",) + files:
            open(os.path.join(prefix, name), "w", encoding="utf-8").close()
        self.game_config = {"prefix": prefix}

    def get_runner(self):
        return wine.wine(wine.LutrisConfig(runner_slug="wine", game_config_id="game"))

    def test_wine_prefix_is_not_switched_to_proton(self):
        self.make_prefix()
        with self.assertRaises(wine.MissingExecutableError) as error:
            self.get_runner().get_executable()
        self.assertIn("wine-test-missing-1", str(error.exception))

    def test_wine_prefix_inheriting_a_missing_runner_version_is_not_switched(self):
        self.game_version = None
        self.make_prefix()
        with self.assertRaises(wine.MissingExecutableError):
            self.get_runner().get_executable()

    def test_wine_terminal_on_a_wine_prefix_is_not_opened(self):
        self.make_prefix()
        runner = self.get_runner()
        with (
            patch.object(runner, "get_env", return_value={}),
            patch.object(wine, "open_wine_terminal") as open_wine_terminal,
            self.assertRaises(wine.MissingExecutableError),
        ):
            runner.run_wine_terminal()
        open_wine_terminal.assert_not_called()

    def test_proton_prefix_falls_back_to_the_default(self):
        for marker in ("tracked_files", "version"):
            with self.subTest(marker=marker):
                self.make_prefix(marker)
                self.assertEqual(self.get_runner().get_executable(), "/umu/umu-run")

    def test_game_set_to_ge_proton_falls_back(self):
        self.game_version = wine.GE_PROTON_LATEST
        self.make_prefix()
        self.assertEqual(self.get_runner().get_executable(), "/umu/umu-run")

    def test_new_prefix_falls_back_to_the_default(self):
        parent = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, parent)
        self.game_config = {"prefix": os.path.join(parent, "prefix")}
        self.assertEqual(self.get_runner().get_executable(), "/umu/umu-run")

    def test_installed_version_is_used(self):
        self.make_prefix()
        with patch.object(
            wine.system, "path_exists", side_effect=lambda path, *args, **kwargs: Path(path) != Path(WINE_DIR)
        ):
            self.assertIn("wine-test-missing-1", self.get_runner().get_executable())
