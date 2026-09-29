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
