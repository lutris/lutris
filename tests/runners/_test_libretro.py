import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from lutris.runners import libretro as libretro_module
from lutris.runners.libretro import _download_libretro_info, get_libretro_cores, libretro
from lutris.util.test_config import setup_test_environment

setup_test_environment()


class TestLibretroCoreInfo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.retroarch_dir = os.path.join(self.temp_dir.name, "retroarch")
        patcher = patch.object(libretro_module, "RETROARCH_DIR", self.retroarch_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        get_libretro_cores.cache_clear()
        self.addCleanup(get_libretro_cores.cache_clear)
        self.addCleanup(self.temp_dir.cleanup)

    @patch("lutris.runners.libretro.requests.get")
    def test_init_does_not_download_core_info(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Read timed out.")
        runner = libretro()
        self.assertEqual(runner.platform_dict, {})
        mock_get.assert_not_called()

    def write_core_info(self, core, systemname):
        info_path = os.path.join(self.retroarch_dir, "info")
        os.makedirs(info_path, exist_ok=True)
        with open(os.path.join(info_path, "%s_libretro.info" % core), "w", encoding="utf-8") as info_file:
            info_file.write('display_name = "%s"\n' % core)
            info_file.write('categories = "Emulator"\n')
            info_file.write('systemname = "%s"\n' % systemname)

    def test_init_reads_downloaded_core_info(self):
        self.write_core_info("mgba", "Game Boy Advance")
        runner = libretro()
        self.assertEqual(runner.platform_dict, {"Nintendo Game Boy Advance": "Game Boy Advance"})

    @patch("lutris.runners.libretro.requests.get")
    def test_download_failure_returns_false(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Read timed out.")
        self.assertFalse(_download_libretro_info())
        self.assertEqual(get_libretro_cores(), [])

    @patch("lutris.runners.libretro.requests.get")
    def test_get_platform_after_core_info_arrives(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Read timed out.")
        runner = libretro()
        self.write_core_info("puae", "Amiga")
        get_libretro_cores.cache_clear()
        runner.config = MagicMock()
        runner.config.game_config = {"core": "puae"}
        self.assertEqual(runner.get_platform(), "Amiga")
