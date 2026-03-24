"""Tests for persistent download progress tracking (download_progress.py)."""

import json
import os
import threading

import pytest

from lutris.util.download_progress import DownloadProgress


@pytest.fixture
def tmp_dest(tmp_path):
    """Return a temporary download destination path."""
    return str(tmp_path / "installer.exe")


@pytest.fixture
def progress(tmp_dest):
    """Return a fresh DownloadProgress instance."""
    return DownloadProgress(tmp_dest)


# ------------------------------------------------------------------
# Initialisation
# ------------------------------------------------------------------


class TestInit:
    def test_progress_path_derived_from_dest(self, tmp_dest):
        dp = DownloadProgress(tmp_dest)
        assert dp.progress_path == tmp_dest + ".progress"

    def test_progress_path_for_static_helper(self, tmp_dest):
        assert DownloadProgress.progress_path_for(tmp_dest) == tmp_dest + ".progress"

    def test_initial_data_is_empty(self, progress):
        assert progress.file_size == 0
        assert progress.url == ""
        assert progress.completed_ranges == []
        assert progress.total_ranges == []


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------


class TestCreate:
    def test_create_writes_progress_file(self, progress, tmp_dest):
        ranges = [(0, 99), (100, 199)]
        progress.create("https://example.com/file", 200, ranges)
        assert os.path.exists(tmp_dest + ".progress")

    def test_create_stores_expected_fields(self, progress):
        ranges = [(0, 49), (50, 99)]
        progress.create("https://cdn.gog.com/game.bin", 100, ranges)

        with open(progress.progress_path, "r") as f:
            data = json.load(f)
        assert data["url"] == "https://cdn.gog.com/game.bin"
        assert data["file_size"] == 100
        assert data["total_ranges"] == [[0, 49], [50, 99]]
        assert data["completed_ranges"] == []
        assert "created_at" in data
        assert "updated_at" in data

    def test_properties_after_create(self, progress):
        ranges = [(0, 999), (1000, 1999)]
        progress.create("https://example.com/f", 2000, ranges)
        assert progress.url == "https://example.com/f"
        assert progress.file_size == 2000
        assert progress.total_ranges == [(0, 999), (1000, 1999)]
        assert progress.completed_ranges == []


# ------------------------------------------------------------------
# Load
# ------------------------------------------------------------------


class TestLoad:
    def test_load_returns_false_when_no_file(self, progress):
        assert progress.load() is False

    def test_load_returns_true_for_valid_progress(self, progress):
        progress.create("https://example.com", 500, [(0, 499)])
        fresh = DownloadProgress(progress.dest_path)
        assert fresh.load() is True
        assert fresh.file_size == 500

    def test_load_returns_false_for_corrupt_json(self, progress, tmp_dest):
        path = tmp_dest + ".progress"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{invalid json!!!")
        assert progress.load() is False

    def test_load_returns_false_for_missing_fields(self, progress, tmp_dest):
        path = tmp_dest + ".progress"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"url": "x"}, f)  # missing required fields
        assert progress.load() is False

    def test_load_restores_completed_ranges(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        progress.mark_range_complete(0, 99)
        progress.mark_range_complete(200, 299)

        fresh = DownloadProgress(progress.dest_path)
        assert fresh.load() is True
        assert (0, 99) in fresh.completed_ranges
        assert (200, 299) in fresh.completed_ranges
        assert (100, 199) not in fresh.completed_ranges


# ------------------------------------------------------------------
# mark_range_complete
# ------------------------------------------------------------------


class TestMarkRangeComplete:
    def test_marks_single_range(self, progress):
        progress.create("https://example.com", 200, [(0, 99), (100, 199)])
        progress.mark_range_complete(0, 99)
        assert progress.completed_ranges == [(0, 99)]

    def test_marks_multiple_ranges(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        progress.mark_range_complete(100, 199)
        progress.mark_range_complete(0, 99)
        assert (0, 99) in progress.completed_ranges
        assert (100, 199) in progress.completed_ranges

    def test_duplicate_mark_is_idempotent(self, progress):
        progress.create("https://example.com", 100, [(0, 99)])
        progress.mark_range_complete(0, 99)
        progress.mark_range_complete(0, 99)
        assert progress.completed_ranges.count((0, 99)) == 1

    def test_persists_to_disk_after_mark(self, progress):
        progress.create("https://example.com", 100, [(0, 99)])
        progress.mark_range_complete(0, 99)

        fresh = DownloadProgress(progress.dest_path)
        fresh.load()
        assert (0, 99) in fresh.completed_ranges


# ------------------------------------------------------------------
# get_remaining_ranges
# ------------------------------------------------------------------


class TestGetRemainingRanges:
    def test_all_remaining_when_none_completed(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        remaining = progress.get_remaining_ranges()
        assert remaining == [(0, 99), (100, 199), (200, 299)]

    def test_some_remaining(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        progress.mark_range_complete(0, 99)
        progress.mark_range_complete(200, 299)
        remaining = progress.get_remaining_ranges()
        assert remaining == [(100, 199)]

    def test_none_remaining_when_all_complete(self, progress):
        progress.create("https://example.com", 200, [(0, 99), (100, 199)])
        progress.mark_range_complete(0, 99)
        progress.mark_range_complete(100, 199)
        assert progress.get_remaining_ranges() == []


# ------------------------------------------------------------------
# get_completed_size
# ------------------------------------------------------------------


class TestGetCompletedSize:
    def test_zero_when_none_completed(self, progress):
        progress.create("https://example.com", 200, [(0, 99), (100, 199)])
        assert progress.get_completed_size() == 0

    def test_partial_completed_size(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        progress.mark_range_complete(0, 99)
        # Range 0-99 is 100 bytes
        assert progress.get_completed_size() == 100

    def test_full_completed_size(self, progress):
        progress.create("https://example.com", 300, [(0, 99), (100, 199), (200, 299)])
        progress.mark_range_complete(0, 99)
        progress.mark_range_complete(100, 199)
        progress.mark_range_complete(200, 299)
        assert progress.get_completed_size() == 300


# ------------------------------------------------------------------
# is_compatible
# ------------------------------------------------------------------


class TestIsCompatible:
    def test_compatible_when_sizes_match(self, progress):
        progress.create("https://old-cdn.com/file", 5000, [(0, 4999)])
        assert progress.is_compatible(5000) is True

    def test_incompatible_when_sizes_differ(self, progress):
        progress.create("https://example.com", 5000, [(0, 4999)])
        assert progress.is_compatible(6000) is False

    def test_incompatible_when_size_is_zero(self, progress):
        progress.create("https://example.com", 0, [])
        assert progress.is_compatible(0) is False

    def test_compatible_ignores_url_differences(self, progress):
        """CDN URLs rotate between sessions; only size matters."""
        progress.create("https://old-cdn.com/tokenA/file", 10000, [(0, 9999)])
        assert progress.is_compatible(10000) is True


# ------------------------------------------------------------------
# cleanup
# ------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_progress_file(self, progress):
        progress.create("https://example.com", 100, [(0, 99)])
        assert os.path.exists(progress.progress_path)
        progress.cleanup()
        assert not os.path.exists(progress.progress_path)

    def test_cleanup_resets_internal_data(self, progress):
        progress.create("https://example.com", 100, [(0, 99)])
        progress.cleanup()
        assert progress.file_size == 0
        assert progress.completed_ranges == []

    def test_cleanup_is_safe_when_no_file(self, progress):
        # Should not raise
        progress.cleanup()


# ------------------------------------------------------------------
# Atomic writes
# ------------------------------------------------------------------


class TestAtomicWrites:
    def test_progress_file_not_corrupted_by_concurrent_marks(self, progress):
        """Simulate concurrent range completions from multiple threads."""
        num_ranges = 20
        ranges = [(i * 100, (i + 1) * 100 - 1) for i in range(num_ranges)]
        progress.create("https://example.com", num_ranges * 100, ranges)

        errors = []

        def mark(start, end):
            try:
                progress.mark_range_complete(start, end)
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=mark, args=(s, e)) for s, e in ranges]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All ranges should be marked — even if ordering varied
        fresh = DownloadProgress(progress.dest_path)
        fresh.load()
        assert len(fresh.completed_ranges) == num_ranges

    def test_save_creates_directories(self, tmp_path):
        deep = str(tmp_path / "a" / "b" / "c" / "file.bin")
        dp = DownloadProgress(deep)
        dp.create("https://example.com", 100, [(0, 99)])
        assert os.path.exists(deep + ".progress")


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_single_range_covers_full_file(self, progress):
        progress.create("https://example.com", 1000, [(0, 999)])
        progress.mark_range_complete(0, 999)
        assert progress.get_remaining_ranges() == []
        assert progress.get_completed_size() == 1000

    def test_many_small_ranges(self, progress):
        ranges = [(i, i) for i in range(100)]  # 1 byte each
        progress.create("https://example.com", 100, ranges)
        for s, e in ranges[:50]:
            progress.mark_range_complete(s, e)
        assert len(progress.get_remaining_ranges()) == 50
        assert progress.get_completed_size() == 50

    def test_load_after_process_restart(self, tmp_dest):
        """Simulate a process restart by creating a new instance."""
        dp1 = DownloadProgress(tmp_dest)
        dp1.create("https://example.com", 400, [(0, 99), (100, 199), (200, 299), (300, 399)])
        dp1.mark_range_complete(0, 99)
        dp1.mark_range_complete(100, 199)

        # Simulate restart: new instance, same path
        dp2 = DownloadProgress(tmp_dest)
        assert dp2.load() is True
        assert dp2.get_completed_size() == 200
        remaining = dp2.get_remaining_ranges()
        assert remaining == [(200, 299), (300, 399)]
