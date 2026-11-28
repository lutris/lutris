import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from lutris.runners import mame as mame_module
from lutris.runners.mame import mame
from lutris.util.test_config import setup_test_environment

setup_test_environment()

SYSTEMS = {"a2600": {"manufacturer": "Atari", "description": "Atari 2600 (NTSC)", "year": "1977"}}


class TestMachinePlatform(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.systems_path = os.path.join(temp_dir.name, "systems.json")
        for patcher in (
            patch.object(mame, "SYSTEMS_PATH", self.systems_path),
            patch.object(mame_module, "get_supported_systems", return_value=SYSTEMS),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        mame_module._get_machine_mapping.cache_clear()
        self.addCleanup(mame_module._get_machine_mapping.cache_clear)

    def get_platform(self, machine):
        runner = mame()
        runner.config = MagicMock()
        runner.config.game_config = {"machine": machine}
        return runner.get_platform()

    def test_platform_found_after_systems_cache_is_built(self):
        """A lookup made before the systems cache exists must not hide it once it is built."""
        with patch("lutris.util.jobs.AsyncCall") as async_call:
            self.assertEqual(self.get_platform("a2600"), "")
        # The background build finishes: systems.json now exists, and the completion callback fires.
        with open(self.systems_path, "w", encoding="utf-8") as systems_file:
            systems_file.write("{}")
        on_loaded = async_call.call_args.args[1]
        on_loaded(True, None)
        self.assertEqual(self.get_platform("a2600"), "Atari 2600 (NTSC)")
