"""Tests for the download cache protection module."""

import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lutris.util.download_cache import (
    CacheState,
    create_cache_lock,
    get_cache_state,
    is_safe_to_delete,
    remove_cache_lock,
    safe_delete_folder,
    update_cache_lock,
)


def temp_file(temp_dir):
    """Create a temporary file for testing."""
    path = os.path.join(temp_dir, "test_game_installer.bin")
    with open(path, "w") as f:
        f.write("test data")
    return path


class TestCacheState(TestCase):
    """Test CacheState enum values."""

    def test_state_values(self):
        assert CacheState.DOWNLOADING.value == "downloading"
        assert CacheState.DOWNLOADED.value == "downloaded"
        assert CacheState.INSTALLING.value == "installing"
        assert CacheState.INSTALLED.value == "installed"
        assert CacheState.FAILED.value == "failed"

    def test_state_from_string(self):
        assert CacheState("downloading") == CacheState.DOWNLOADING
        assert CacheState("installed") == CacheState.INSTALLED


class TestCreateCacheLock(TestCase):
    """Test cache lock file creation."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.tmp_file = temp_file(self.tmp_path)

    def test_creates_lock_file(self):
        create_cache_lock(self.tmp_file)
        lock_path = self.tmp_file + ".cache_lock"
        assert os.path.exists(lock_path)

    def test_lock_contains_correct_state(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADING)
        lock_path = self.tmp_file + ".cache_lock"
        with open(lock_path) as f:
            data = json.load(f)
        assert data["state"] == "downloading"
        assert data["file_path"] == self.tmp_file
        assert "created_at" in data
        assert "updated_at" in data

    def test_lock_with_custom_state(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADED)
        assert get_cache_state(self.tmp_file) == CacheState.DOWNLOADED

    def test_creates_directory_if_needed(self):
        nested_path = os.path.join(self.tmp_path, "subdir", "file.bin")
        create_cache_lock(nested_path)
        assert os.path.exists(nested_path + ".cache_lock")


class TestUpdateCacheLock(TestCase):
    """Test cache lock state updates."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.tmp_file = temp_file(self.tmp_path)

    def test_updates_state(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADING)
        update_cache_lock(self.tmp_file, CacheState.DOWNLOADED)
        assert get_cache_state(self.tmp_file) == CacheState.DOWNLOADED

    def test_updates_timestamp(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADING)
        lock_path = self.tmp_file + ".cache_lock"
        with open(lock_path) as f:
            data1 = json.load(f)

        time.sleep(0.1)
        update_cache_lock(self.tmp_file, CacheState.INSTALLED)
        with open(lock_path) as f:
            data2 = json.load(f)

        assert data2["updated_at"] >= data1["updated_at"]

    def test_update_nonexistent_lock(self):
        """Update should create the lock if it doesn't exist."""
        update_cache_lock(self.tmp_file, CacheState.INSTALLED)
        assert get_cache_state(self.tmp_file) == CacheState.INSTALLED

    def test_full_lifecycle(self):
        """Test transition through all states."""
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADING)
        assert get_cache_state(self.tmp_file) == CacheState.DOWNLOADING

        update_cache_lock(self.tmp_file, CacheState.DOWNLOADED)
        assert get_cache_state(self.tmp_file) == CacheState.DOWNLOADED

        update_cache_lock(self.tmp_file, CacheState.INSTALLING)
        assert get_cache_state(self.tmp_file) == CacheState.INSTALLING

        update_cache_lock(self.tmp_file, CacheState.INSTALLED)
        assert get_cache_state(self.tmp_file) == CacheState.INSTALLED


class TestGetCacheState(TestCase):
    """Test reading cache state."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.tmp_file = temp_file(self.tmp_path)

    def test_returns_none_for_no_lock(self):
        assert get_cache_state(self.tmp_file) is None

    def test_returns_correct_state(self):
        create_cache_lock(self.tmp_file, CacheState.INSTALLING)
        assert get_cache_state(self.tmp_file) == CacheState.INSTALLING

    def test_handles_corrupted_lock(self):
        lock_path = self.tmp_file + ".cache_lock"
        with open(lock_path, "w") as f:
            f.write("not valid json{{{")
        assert get_cache_state(self.tmp_file) is None


class TestRemoveCacheLock(TestCase):
    """Test cache lock removal."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.tmp_file = temp_file(self.tmp_path)

    def test_removes_lock(self):
        create_cache_lock(self.tmp_file)
        remove_cache_lock(self.tmp_file)
        assert not os.path.exists(self.tmp_file + ".cache_lock")

    def test_no_error_for_nonexistent_lock(self):
        remove_cache_lock(self.tmp_file)  # Should not raise


class TestIsSafeToDelete(TestCase):
    """Test deletion safety checks."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.tmp_file = temp_file(self.tmp_path)

    def test_no_lock_is_safe(self):
        """Legacy files without locks can be deleted."""
        assert is_safe_to_delete(self.tmp_file) is True

    def test_installed_is_safe(self):
        create_cache_lock(self.tmp_file, CacheState.INSTALLED)
        assert is_safe_to_delete(self.tmp_file) is True

    def test_downloading_is_not_safe(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADING)
        assert is_safe_to_delete(self.tmp_file) is False

    def test_downloaded_is_not_safe(self):
        create_cache_lock(self.tmp_file, CacheState.DOWNLOADED)
        assert is_safe_to_delete(self.tmp_file) is False

    def test_installing_is_not_safe(self):
        create_cache_lock(self.tmp_file, CacheState.INSTALLING)
        assert is_safe_to_delete(self.tmp_file) is False

    def test_failed_recent_is_not_safe(self):
        """Failed installations less than 7 days old should be preserved."""
        create_cache_lock(self.tmp_file, CacheState.FAILED)
        assert is_safe_to_delete(self.tmp_file) is False

    def test_failed_old_is_safe(self):
        """Failed installations older than 7 days can be cleaned."""
        create_cache_lock(self.tmp_file, CacheState.FAILED)
        lock_path = self.tmp_file + ".cache_lock"
        with open(lock_path) as f:
            data = json.load(f)
        # Set updated_at to 8 days ago
        data["updated_at"] = time.time() - (8 * 86400)
        with open(lock_path, "w") as f:
            json.dump(data, f)
        assert is_safe_to_delete(self.tmp_file) is True


class TestSafeDeleteFolder(TestCase):
    """Test cache-aware folder deletion."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def test_deletes_unlocked_files(self):
        """Files without locks should be deleted."""
        file1 = os.path.join(self.tmp_path, "file1.bin")
        file2 = os.path.join(self.tmp_path, "file2.bin")
        with open(file1, "w") as f:
            f.write("data1")
        with open(file2, "w") as f:
            f.write("data2")

        result = safe_delete_folder(str(self.tmp_path))
        assert result is True
        assert not os.path.exists(self.tmp_path)

    def test_preserves_locked_files(self):
        """Files with active cache locks should be preserved."""
        safe_file = os.path.join(self.tmp_path, "safe.bin")
        locked_file = os.path.join(self.tmp_path, "locked.bin")
        with open(safe_file, "w") as f:
            f.write("safe")
        with open(locked_file, "w") as f:
            f.write("locked")

        create_cache_lock(locked_file, CacheState.DOWNLOADED)

        result = safe_delete_folder(str(self.tmp_path))
        assert result is False  # Not fully cleaned
        assert not os.path.exists(safe_file)
        assert os.path.exists(locked_file)

    def test_deletes_installed_files(self):
        """Files marked as installed can be deleted."""
        file1 = os.path.join(self.tmp_path, "game.bin")
        with open(file1, "w") as f:
            f.write("data")

        create_cache_lock(file1, CacheState.INSTALLED)

        result = safe_delete_folder(str(self.tmp_path))
        assert result is True

    def test_nonexistent_folder(self):
        """Non-existent folder should return True."""
        result = safe_delete_folder(os.path.join(self.tmp_path, "nonexistent"))
        assert result is True

    def test_mixed_states(self):
        """Mix of safe and unsafe files."""
        installed = os.path.join(self.tmp_path, "installed.bin")
        downloading = os.path.join(self.tmp_path, "downloading.bin")
        no_lock = os.path.join(self.tmp_path, "no_lock.bin")

        for f in [installed, downloading, no_lock]:
            with open(f, "w") as fp:
                fp.write("data")

        create_cache_lock(installed, CacheState.INSTALLED)
        create_cache_lock(downloading, CacheState.DOWNLOADING)

        result = safe_delete_folder(str(self.tmp_path))
        assert result is False
        assert not os.path.exists(installed)
        assert os.path.exists(downloading)
        assert not os.path.exists(no_lock)


class TestDownloaderChunkSize(TestCase):
    """Test that the Downloader uses the new chunk size."""

    def test_default_chunk_size(self):
        from lutris.util.downloader import DEFAULT_CHUNK_SIZE, SimpleDownloader

        d = SimpleDownloader("http://example.com/test", "/tmp/test")
        assert d.chunk_size == DEFAULT_CHUNK_SIZE
        assert d.chunk_size == 524288  # 512KB

    def test_custom_chunk_size(self):
        from lutris.util.downloader import SimpleDownloader

        d = SimpleDownloader("http://example.com/test", "/tmp/test", chunk_size=1024)
        assert d.chunk_size == 1024

    def test_session_parameter(self):
        import requests

        from lutris.util.downloader import SimpleDownloader

        session = requests.Session()
        d = SimpleDownloader("http://example.com/test", "/tmp/test", session=session)
        assert d.session is session

    def test_no_session_by_default(self):
        from lutris.util.downloader import SimpleDownloader

        d = SimpleDownloader("http://example.com/test", "/tmp/test")
        assert d.session is None
