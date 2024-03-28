import unittest
from unittest.mock import patch

from lutris import api

RUNTIME_VERSIONS = {
    "client_version": "0.5.17",
    "runners": {
        "wine": [
            {
                "name": "wine",
                "version": "wine-ge-8-27",
                "url": "https://github.com/GloriousEggroll/wine-ge-custom/releases/download/GE-Proton8-26/wine-lutris-GE-Proton8-26-x86_64.tar.xz",
                "architecture": "x86_64",
            }
        ],
    },
}


class TestApi(unittest.TestCase):
    @patch("lutris.api.get_runtime_versions")
    def test_get_default_runner_version_info(self, mock_get_runtime_versions):
        mock_get_runtime_versions.return_value = RUNTIME_VERSIONS
        version_info = api.get_default_runner_version_info("wine")
        self.assertEqual(version_info["version"], "wine-ge-8-27")

        version_info = api.get_default_runner_version_info("wine", "lutris-7.2-2")
        self.assertEqual(version_info["version"], "lutris-7.2-2")

        version_info = api.get_default_runner_version_info("wine", "lutris-7.2-2-x86_64")
        self.assertEqual(version_info["version"], "lutris-7.2-2")
