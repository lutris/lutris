import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lutris.util.upstream import ReleaseSource
from lutris.util.wine import dll_manager
from lutris.util.wine.dll_manager import DLLManager


class FakeManager(DLLManager):
    name = "fake"
    human_name = "Fake"
    managed_dlls = ("fake",)
    release_source = ReleaseSource("example/fake", r"^fake-[\d.]+\.tar\.gz$")


class TestGetDownloadUrl(unittest.TestCase):
    """get_download_url() looks up a version in the release list saved by fetch_versions()."""

    def _manager(self, releases, version="1.0"):
        runtime_dir = tempfile.TemporaryDirectory()
        self.addCleanup(runtime_dir.cleanup)
        base_dir = os.path.join(runtime_dir.name, FakeManager.name)
        os.makedirs(base_dir)
        versions_path = os.path.join(base_dir, f"{FakeManager.name}_versions.json")
        with open(versions_path, "w", encoding="utf-8") as versions_file:
            json.dump(releases, versions_file)
        fake_settings = patch.object(dll_manager, "settings", SimpleNamespace(RUNTIME_DIR=runtime_dir.name))
        fake_settings.start()
        self.addCleanup(fake_settings.stop)
        return FakeManager(version=version)

    def test_returns_the_url_of_the_matching_asset(self):
        manager = self._manager(
            [
                {
                    "tag_name": "1.0",
                    "assets": [
                        {"name": "fake-1.0.tar.gz", "browser_download_url": "https://example.com/fake-1.0.tar.gz"}
                    ],
                }
            ]
        )

        self.assertEqual(manager.get_download_url(), "https://example.com/fake-1.0.tar.gz")

    def test_returns_none_when_no_release_matches_the_version(self):
        manager = self._manager(
            [
                {
                    "tag_name": "0.9",
                    "assets": [
                        {"name": "fake-0.9.tar.gz", "browser_download_url": "https://example.com/fake-0.9.tar.gz"}
                    ],
                }
            ]
        )

        self.assertIsNone(manager.get_download_url())

    def test_returns_none_for_a_release_without_assets(self):
        manager = self._manager([{"tag_name": "1.0", "assets": []}])

        self.assertIsNone(manager.get_download_url())

    def test_returns_none_when_a_release_has_no_assets_key(self):
        manager = self._manager([{"tag_name": "1.0"}])

        self.assertIsNone(manager.get_download_url())

    def test_returns_none_when_a_release_has_no_tag_name(self):
        manager = self._manager(
            [{"assets": [{"name": "fake-1.0.tar.gz", "browser_download_url": "https://example.com/fake-1.0.tar.gz"}]}]
        )

        self.assertIsNone(manager.get_download_url())

    def test_returns_none_when_the_asset_has_no_url(self):
        manager = self._manager([{"tag_name": "1.0", "assets": [{"name": "fake-1.0.tar.gz"}]}])

        self.assertIsNone(manager.get_download_url())
