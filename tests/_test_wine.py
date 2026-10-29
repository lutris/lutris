import hashlib
import os
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lutris.runners import wine
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
