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
