import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lutris.util.egs.egs_launcher import EGSLauncher


class TestEGSLauncher(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.launcher = EGSLauncher(directory.name)
        self.manifests_path = Path(directory.name, "drive_c", EGSLauncher.manifests_paths)
        self.manifests_path.mkdir(parents=True)

    def write_manifest(self, manifest, filename="game.item"):
        (self.manifests_path / filename).write_text(json.dumps(manifest), encoding="utf-8")

    def test_base_game_with_empty_parent_is_included(self):
        manifest = {"AppName": "caravan-sandwitch", "MainGameAppName": "", "DisplayName": "Caravan SandWitch"}
        self.write_manifest(manifest)

        self.assertEqual(list(self.launcher.iter_manifests()), [manifest])

    def test_base_game_with_matching_parent_is_included(self):
        manifest = {"AppName": "base-game", "MainGameAppName": "base-game"}
        self.write_manifest(manifest)

        self.assertEqual(list(self.launcher.iter_manifests()), [manifest])

    def test_dlc_with_different_parent_is_excluded(self):
        self.write_manifest({"AppName": "dlc", "MainGameAppName": "base-game"})

        self.assertEqual(list(self.launcher.iter_manifests()), [])

    def test_null_parent_is_excluded(self):
        self.write_manifest({"AppName": "base-game", "MainGameAppName": None})

        self.assertEqual(list(self.launcher.iter_manifests()), [])

    def test_non_manifest_files_are_ignored(self):
        (self.manifests_path / "ignored.txt").write_text("not json", encoding="utf-8")

        self.assertEqual(list(self.launcher.iter_manifests()), [])
