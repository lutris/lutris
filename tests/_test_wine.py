from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import PropertyMock, patch

from lutris.exceptions import MissingGameExecutableError
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


class TestWineGameValidation(TestCase):
    def test_missing_game_executable_is_rejected(self):
        runner = wine.wine()

        with (
            patch.object(wine.wine, "game_exe", new_callable=PropertyMock, return_value="/missing/game.exe"),
            patch.object(wine.system, "path_exists", return_value=False),
            self.assertRaises(MissingGameExecutableError),
        ):
            runner.validate_game()

    def test_existing_game_executable_is_accepted(self):
        runner = wine.wine()

        with (
            patch.object(wine.wine, "game_exe", new_callable=PropertyMock, return_value="/games/game.exe"),
            patch.object(wine.system, "path_exists", return_value=True),
        ):
            runner.validate_game()
