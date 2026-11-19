import json
import os
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.util import path_cache


class TestPathCache(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.cache_path = os.path.join(self.temp_dir.name, "deleted-cache", "game-paths.json")
        self.cache_path_patcher = patch.object(path_cache, "GAME_PATH_CACHE_PATH", self.cache_path)
        self.cache_path_patcher.start()
        self.addCleanup(self.cache_path_patcher.stop)

        path_cache.get_path_cache.cache_clear()
        self.addCleanup(path_cache.get_path_cache.cache_clear)

    def test_read_missing_path_cache_returns_empty_dict(self):
        self.assertFalse(os.path.exists(self.cache_path))

        self.assertEqual(path_cache.read_path_cache(), {})

    def test_read_invalid_path_cache_returns_empty_dict(self):
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as cache_file:
            cache_file.write("{invalid json")

        self.assertEqual(path_cache.read_path_cache(), {})

    def test_add_to_path_cache_recreates_deleted_cache_directory(self):
        game = MagicMock()
        game.id = "42"
        game.get_path_from_config.return_value = "/games/example"

        path_cache.add_to_path_cache(game)

        with open(self.cache_path, encoding="utf-8") as cache_file:
            self.assertEqual(json.load(cache_file), {"42": "/games/example"})

    def test_build_path_cache_recreates_deleted_cache_directory(self):
        with patch.object(
            path_cache,
            "get_game_paths",
            return_value={"42": "/games/example"},
        ):
            path_cache.build_path_cache()

        with open(self.cache_path, encoding="utf-8") as cache_file:
            self.assertEqual(json.load(cache_file), {"42": "/games/example"})

    def test_remove_from_path_cache_persists_updated_cache(self):
        path_cache.write_path_cache({"42": "/games/example", "84": "/games/other"})
        game = MagicMock()
        game.id = "42"

        path_cache.remove_from_path_cache(game)

        with open(self.cache_path, encoding="utf-8") as cache_file:
            self.assertEqual(json.load(cache_file), {"84": "/games/other"})
