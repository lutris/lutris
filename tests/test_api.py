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

WINE_RUNNER_VERSIONS = [
    {
        "version": "wine-ge-8-26",
        "architecture": "x86_64",
        "url": "https://github.com/GloriousEggroll/wine-ge-custom/releases/download/GE-Proton8-26/wine-lutris-GE-Proton8-26-x86_64.tar.xz",
        "default": True,
    },
    {
        "version": "wine-ge-lol-8-27",
        "architecture": "x86_64",
        "url": "https://github.com/GloriousEggroll/wine-ge-custom/releases/download/GE-Proton8-27-LoL/wine-lutris-GE-Proton8-27-LoL-x86_64.tar.xz",
        "default": False,
    },
    {
        "version": "lutris-7.2",
        "architecture": "x86_64",
        "url": "https://github.com/lutris/wine/releases/download/lutris-wine-7.2/wine-lutris-7.2-x86_64.tar.xz",
        "default": False,
    },
    {
        "version": "lutris-7.2-1",
        "architecture": "x86_64",
        "url": "https://github.com/lutris/wine/releases/download/lutris-wine-7.2-2/wine-lutris-7.2-2-x86_64.tar.xz",
        "default": False,
    },
    {
        "version": "lutris-fshack-7.2",
        "architecture": "x86_64",
        "url": "https://github.com/lutris/wine/releases/download/lutris-wine-7.2/wine-lutris-fshack-7.2-x86_64.tar.xz",
        "default": False,
    },
]


class TestApi(unittest.TestCase):

    @patch("lutris.api.get_runtime_versions")
    @patch("lutris.api.download_runner_versions")
    def test_get_default_runner_version_info(self, mock_download_runner_versions, mock_get_runtime_versions):
        mock_get_runtime_versions.return_value = RUNTIME_VERSIONS
        mock_download_runner_versions.return_value = WINE_RUNNER_VERSIONS
        version_info = api.get_default_runner_version_info("wine")
        self.assertEqual(version_info["version"], "wine-ge-8-27")

        version_info = api.get_default_runner_version_info("wine", "lutris-7.2-1")
        self.assertEqual(version_info["version"], "lutris-7.2-1")

        version_info = api.get_default_runner_version_info("wine", "lutris-7.2-1-x86_64")
        self.assertEqual(version_info["version"], "lutris-7.2-1")
