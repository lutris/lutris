import builtins
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import lutris.util.path_cache as path_cache
from lutris import settings


class FakeGame:
    def __init__(self, game_id, path):
        self.id = game_id
        self._path = path

    def get_path_from_config(self):
        return self._path

    def __str__(self):
        return f"FakeGame({self.id})"


class TestPathCache(TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.original_cache_dir = settings.CACHE_DIR
        self.original_cache_path = path_cache.GAME_PATH_CACHE_PATH
        settings.CACHE_DIR = str(self.tmp_path)
        path_cache.GAME_PATH_CACHE_PATH = os.path.join(settings.CACHE_DIR, "game-paths.json")
        path_cache.get_path_cache.cache_clear()

    def tearDown(self):
        settings.CACHE_DIR = self.original_cache_dir
        path_cache.GAME_PATH_CACHE_PATH = self.original_cache_path
        path_cache.get_path_cache.cache_clear()
        self.tmp_dir.cleanup()

    def test_read_missing_cache_returns_empty(self):
        assert path_cache.read_path_cache() == {}

    def test_write_creates_parent_directory(self):
        nested = self.tmp_path / "nested" / "cache"
        settings.CACHE_DIR = str(nested)
        path_cache.GAME_PATH_CACHE_PATH = os.path.join(settings.CACHE_DIR, "game-paths.json")

        path_cache._write_path_cache({"1": "/path/to/game"})
        assert os.path.exists(path_cache.GAME_PATH_CACHE_PATH)
        with open(path_cache.GAME_PATH_CACHE_PATH, encoding="utf-8") as f:
            assert json.load(f) == {"1": "/path/to/game"}

    def test_preserve_and_update_valid_cache(self):
        path_cache._write_path_cache({"1": "/path/to/game"})
        path_cache.add_to_path_cache(FakeGame("2", "/path/to/second"))

        assert path_cache.get_path_cache() == {"1": "/path/to/game", "2": "/path/to/second"}

    def test_repeated_reads_writes_after_cache_directory_removed(self):
        path_cache._write_path_cache({"1": "/path/to/game"})
        os.remove(path_cache.GAME_PATH_CACHE_PATH)

        assert path_cache.read_path_cache() == {}

        path_cache.add_to_path_cache(FakeGame("2", "/path/to/second"))
        assert path_cache.get_path_cache() == {"2": "/path/to/second"}

    def test_written_cache_is_valid_json(self):
        path_cache._write_path_cache({"1": "/path/to/game"})
        with open(path_cache.GAME_PATH_CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"1": "/path/to/game"}

    def test_failed_write_does_not_replace_existing_cache(self):
        path_cache._write_path_cache({"1": "/path/to/game"})
        temp_path = path_cache.GAME_PATH_CACHE_PATH + ".tmp"

        def fail_open(path, *args, **kwargs):
            if path == temp_path:
                raise OSError("disk error")
            return builtins.open(path, *args, **kwargs)

        with patch("lutris.util.path_cache.open", side_effect=fail_open):
            try:
                path_cache._write_path_cache({"2": "/path/to/second"})
            except OSError:
                pass

        with open(path_cache.GAME_PATH_CACHE_PATH, encoding="utf-8") as f:
            assert json.load(f) == {"1": "/path/to/game"}
