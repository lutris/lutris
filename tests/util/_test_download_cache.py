"""Tests for the download cache protection module."""

import json
import os
import tempfile
import time

import pytest

from lutris.util.download_cache import (
    CacheState,
    create_cache_lock,
    get_cache_state,
    is_safe_to_delete,
    remove_cache_lock,
    safe_delete_folder,
    update_cache_lock,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file for testing."""
    path = os.path.join(temp_dir, "test_game_installer.bin")
    with open(path, "w") as f:
        f.write("test data")
    return path


class TestCacheState:
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


class TestCreateCacheLock:
    """Test cache lock file creation."""

    def test_creates_lock_file(self, temp_file):
        create_cache_lock(temp_file)
        lock_path = temp_file + ".cache_lock"
        assert os.path.exists(lock_path)

    def test_lock_contains_correct_state(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADING)
        lock_path = temp_file + ".cache_lock"
        with open(lock_path) as f:
            data = json.load(f)
        assert data["state"] == "downloading"
        assert data["file_path"] == temp_file
        assert "created_at" in data
        assert "updated_at" in data

    def test_lock_with_custom_state(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADED)
        assert get_cache_state(temp_file) == CacheState.DOWNLOADED

    def test_creates_directory_if_needed(self, temp_dir):
        nested_path = os.path.join(temp_dir, "subdir", "file.bin")
        create_cache_lock(nested_path)
        assert os.path.exists(nested_path + ".cache_lock")


class TestUpdateCacheLock:
    """Test cache lock state updates."""

    def test_updates_state(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADING)
        update_cache_lock(temp_file, CacheState.DOWNLOADED)
        assert get_cache_state(temp_file) == CacheState.DOWNLOADED

    def test_updates_timestamp(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADING)
        lock_path = temp_file + ".cache_lock"
        with open(lock_path) as f:
            data1 = json.load(f)

        time.sleep(0.1)
        update_cache_lock(temp_file, CacheState.INSTALLED)
        with open(lock_path) as f:
            data2 = json.load(f)

        assert data2["updated_at"] >= data1["updated_at"]

    def test_update_nonexistent_lock(self, temp_file):
        """Update should create the lock if it doesn't exist."""
        update_cache_lock(temp_file, CacheState.INSTALLED)
        assert get_cache_state(temp_file) == CacheState.INSTALLED

    def test_full_lifecycle(self, temp_file):
        """Test transition through all states."""
        create_cache_lock(temp_file, CacheState.DOWNLOADING)
        assert get_cache_state(temp_file) == CacheState.DOWNLOADING

        update_cache_lock(temp_file, CacheState.DOWNLOADED)
        assert get_cache_state(temp_file) == CacheState.DOWNLOADED

        update_cache_lock(temp_file, CacheState.INSTALLING)
        assert get_cache_state(temp_file) == CacheState.INSTALLING

        update_cache_lock(temp_file, CacheState.INSTALLED)
        assert get_cache_state(temp_file) == CacheState.INSTALLED


class TestGetCacheState:
    """Test reading cache state."""

    def test_returns_none_for_no_lock(self, temp_file):
        assert get_cache_state(temp_file) is None

    def test_returns_correct_state(self, temp_file):
        create_cache_lock(temp_file, CacheState.INSTALLING)
        assert get_cache_state(temp_file) == CacheState.INSTALLING

    def test_handles_corrupted_lock(self, temp_file):
        lock_path = temp_file + ".cache_lock"
        with open(lock_path, "w") as f:
            f.write("not valid json{{{")
        assert get_cache_state(temp_file) is None


class TestRemoveCacheLock:
    """Test cache lock removal."""

    def test_removes_lock(self, temp_file):
        create_cache_lock(temp_file)
        remove_cache_lock(temp_file)
        assert not os.path.exists(temp_file + ".cache_lock")

    def test_no_error_for_nonexistent_lock(self, temp_file):
        remove_cache_lock(temp_file)  # Should not raise


class TestIsSafeToDelete:
    """Test deletion safety checks."""

    def test_no_lock_is_safe(self, temp_file):
        """Legacy files without locks can be deleted."""
        assert is_safe_to_delete(temp_file) is True

    def test_installed_is_safe(self, temp_file):
        create_cache_lock(temp_file, CacheState.INSTALLED)
        assert is_safe_to_delete(temp_file) is True

    def test_downloading_is_not_safe(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADING)
        assert is_safe_to_delete(temp_file) is False

    def test_downloaded_is_not_safe(self, temp_file):
        create_cache_lock(temp_file, CacheState.DOWNLOADED)
        assert is_safe_to_delete(temp_file) is False

    def test_installing_is_not_safe(self, temp_file):
        create_cache_lock(temp_file, CacheState.INSTALLING)
        assert is_safe_to_delete(temp_file) is False

    def test_failed_recent_is_not_safe(self, temp_file):
        """Failed installations less than 7 days old should be preserved."""
        create_cache_lock(temp_file, CacheState.FAILED)
        assert is_safe_to_delete(temp_file) is False

    def test_failed_old_is_safe(self, temp_file):
        """Failed installations older than 7 days can be cleaned."""
        create_cache_lock(temp_file, CacheState.FAILED)
        lock_path = temp_file + ".cache_lock"
        with open(lock_path) as f:
            data = json.load(f)
        # Set updated_at to 8 days ago
        data["updated_at"] = time.time() - (8 * 86400)
        with open(lock_path, "w") as f:
            json.dump(data, f)
        assert is_safe_to_delete(temp_file) is True


class TestSafeDeleteFolder:
    """Test cache-aware folder deletion."""

    def test_deletes_unlocked_files(self, temp_dir):
        """Files without locks should be deleted."""
        file1 = os.path.join(temp_dir, "file1.bin")
        file2 = os.path.join(temp_dir, "file2.bin")
        with open(file1, "w") as f:
            f.write("data1")
        with open(file2, "w") as f:
            f.write("data2")

        result = safe_delete_folder(temp_dir)
        assert result is True
        assert not os.path.exists(temp_dir)

    def test_preserves_locked_files(self, temp_dir):
        """Files with active cache locks should be preserved."""
        safe_file = os.path.join(temp_dir, "safe.bin")
        locked_file = os.path.join(temp_dir, "locked.bin")
        with open(safe_file, "w") as f:
            f.write("safe")
        with open(locked_file, "w") as f:
            f.write("locked")

        create_cache_lock(locked_file, CacheState.DOWNLOADED)

        result = safe_delete_folder(temp_dir)
        assert result is False  # Not fully cleaned
        assert not os.path.exists(safe_file)
        assert os.path.exists(locked_file)

    def test_deletes_installed_files(self, temp_dir):
        """Files marked as installed can be deleted."""
        file1 = os.path.join(temp_dir, "game.bin")
        with open(file1, "w") as f:
            f.write("data")

        create_cache_lock(file1, CacheState.INSTALLED)

        result = safe_delete_folder(temp_dir)
        assert result is True

    def test_nonexistent_folder(self, temp_dir):
        """Non-existent folder should return True."""
        result = safe_delete_folder(os.path.join(temp_dir, "nonexistent"))
        assert result is True

    def test_mixed_states(self, temp_dir):
        """Mix of safe and unsafe files."""
        installed = os.path.join(temp_dir, "installed.bin")
        downloading = os.path.join(temp_dir, "downloading.bin")
        no_lock = os.path.join(temp_dir, "no_lock.bin")

        for f in [installed, downloading, no_lock]:
            with open(f, "w") as fp:
                fp.write("data")

        create_cache_lock(installed, CacheState.INSTALLED)
        create_cache_lock(downloading, CacheState.DOWNLOADING)

        result = safe_delete_folder(temp_dir)
        assert result is False
        assert not os.path.exists(installed)
        assert os.path.exists(downloading)
        assert not os.path.exists(no_lock)


class TestDownloaderChunkSize:
    """Test that the Downloader uses the new chunk size."""

    def test_default_chunk_size(self):
        from lutris.util.downloader import DEFAULT_CHUNK_SIZE, Downloader

        d = Downloader("http://example.com/test", "/tmp/test")
        assert d.chunk_size == DEFAULT_CHUNK_SIZE
        assert d.chunk_size == 524288  # 512KB

    def test_custom_chunk_size(self):
        from lutris.util.downloader import Downloader

        d = Downloader("http://example.com/test", "/tmp/test", chunk_size=1024)
        assert d.chunk_size == 1024

    def test_session_parameter(self):
        import requests

        from lutris.util.downloader import Downloader

        session = requests.Session()
        d = Downloader("http://example.com/test", "/tmp/test", session=session)
        assert d.session is session

    def test_no_session_by_default(self):
        from lutris.util.downloader import Downloader

        d = Downloader("http://example.com/test", "/tmp/test")
        assert d.session is None
