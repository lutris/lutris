"""Tests for the GOG multi-connection parallel downloader."""

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from lutris.util.download_progress import DownloadProgress
from lutris.util.downloader import DEFAULT_CHUNK_SIZE, Downloader
from lutris.util.gog_downloader import GOGDownloader


class TestGOGDownloaderInit:
    """Test GOGDownloader initialization."""

    def test_inherits_from_downloader(self):
        """GOGDownloader must be a Downloader subclass for API compat."""
        assert issubclass(GOGDownloader, Downloader)

    def test_default_workers(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert dl.num_workers == GOGDownloader.DEFAULT_WORKERS

    def test_custom_workers(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=8)
        assert dl.num_workers == 8

    def test_min_workers_clamped(self):
        """Workers should be at least 1."""
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=0)
        assert dl.num_workers == 1

    def test_negative_workers_clamped(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=-5)
        assert dl.num_workers == 1

    def test_has_parallel_session(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert dl._parallel_session is not None

    def test_has_download_lock(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert isinstance(dl._download_lock, type(threading.Lock()))

    def test_default_chunk_size(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert dl.chunk_size == DEFAULT_CHUNK_SIZE

    def test_repr(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=4)
        assert "GOG parallel downloader" in repr(dl)
        assert "4 workers" in repr(dl)

    def test_passes_params_to_parent(self):
        dl = GOGDownloader(
            "https://example.com/file.bin",
            "/tmp/test.bin",
            overwrite=True,
            referer="https://gog.com",
        )
        assert dl.url == "https://example.com/file.bin"
        assert dl.dest == "/tmp/test.bin"
        assert dl.overwrite is True
        assert dl.referer == "https://gog.com"


class TestBuildRequestHeaders:
    """Test HTTP header construction."""

    def test_basic_headers(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        headers = dl._build_request_headers()
        assert "User-Agent" in headers
        assert "Lutris/" in headers["User-Agent"]

    def test_referer_header(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", referer="https://gog.com")
        headers = dl._build_request_headers()
        assert headers["Referer"] == "https://gog.com"

    def test_custom_headers(self):
        dl = GOGDownloader(
            "https://example.com/file.bin",
            "/tmp/test.bin",
            headers={"X-Custom": "value"},
        )
        headers = dl._build_request_headers()
        assert headers["X-Custom"] == "value"


class TestCalculateRanges:
    """Test byte range calculation for parallel downloads."""

    def test_even_split(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=4)
        ranges = dl._calculate_ranges(1000)
        assert len(ranges) == 4
        assert ranges[0] == (0, 249)
        assert ranges[1] == (250, 499)
        assert ranges[2] == (500, 749)
        assert ranges[3] == (750, 999)

    def test_uneven_split(self):
        """Last worker gets the remainder."""
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=3)
        ranges = dl._calculate_ranges(100)
        assert len(ranges) == 3
        assert ranges[0] == (0, 32)
        assert ranges[1] == (33, 65)
        assert ranges[2] == (66, 99)  # Last worker gets remainder

    def test_single_worker(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=1)
        ranges = dl._calculate_ranges(1000)
        assert len(ranges) == 1
        assert ranges[0] == (0, 999)

    def test_covers_entire_file(self):
        """All byte ranges together should cover the entire file."""
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=7)
        file_size = 10_000_000
        ranges = dl._calculate_ranges(file_size)
        total = sum(end - start + 1 for start, end in ranges)
        assert total == file_size

    def test_no_gaps_or_overlaps(self):
        """Byte ranges must be contiguous with no gaps or overlaps."""
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin", num_workers=5)
        ranges = dl._calculate_ranges(123456)
        for i in range(len(ranges) - 1):
            assert ranges[i][1] + 1 == ranges[i + 1][0], f"Gap between range {i} and {i + 1}"


class TestProbeServer:
    """Test server probing for capabilities."""

    def test_probe_with_range_support(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")

        mock_resp = MagicMock()
        mock_resp.url = "https://cdn.gog.com/resolved/file.bin"
        mock_resp.headers = {"Content-Length": "104857600", "Accept-Ranges": "bytes"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(dl._parallel_session, "head", return_value=mock_resp):
            url, size, supports = dl._probe_server({})

        assert url == "https://cdn.gog.com/resolved/file.bin"
        assert size == 104857600
        assert supports is True

    def test_probe_without_range_header_but_206_response(self):
        """Test fallback Range probe when Accept-Ranges header is missing."""
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {"Content-Length": "50000000"}
        mock_head_resp.raise_for_status = MagicMock()

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 206

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", return_value=mock_get_resp):
                _url, _size, supports = dl._probe_server({})

        assert supports is True

    def test_probe_no_range_support(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {"Content-Length": "50000000", "Accept-Ranges": "none"}
        mock_head_resp.raise_for_status = MagicMock()

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            _url, _size, supports = dl._probe_server({})

        assert supports is False

    def test_probe_no_content_length(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")

        mock_resp = MagicMock()
        mock_resp.url = "https://cdn.gog.com/file.bin"
        mock_resp.headers = {}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(dl._parallel_session, "head", return_value=mock_resp):
            _url, size, supports = dl._probe_server({})

        assert size == 0
        assert supports is False


class TestFallbackToSingleStream:
    """Test cases where parallel download falls back to single-stream."""

    def test_fallback_when_no_range_support(self, tmp_path):
        dest = str(tmp_path / "file.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)

        test_data = b"Hello, World!"

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {"Content-Length": str(len(test_data)), "Accept-Ranges": "none"}
        mock_head_resp.raise_for_status = MagicMock()

        mock_get_resp = MagicMock()
        mock_get_resp.headers = {"Content-Length": str(len(test_data))}
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.iter_content = MagicMock(return_value=[test_data])

        dl.stop_request = threading.Event()

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", return_value=mock_get_resp):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == test_data

    def test_fallback_when_file_too_small(self, tmp_path):
        dest = str(tmp_path / "small.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)

        # File smaller than MIN_CHUNK_SIZE * 2
        small_size = GOGDownloader.MIN_CHUNK_SIZE - 1
        test_data = b"x" * 100

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {
            "Content-Length": str(small_size),
            "Accept-Ranges": "bytes",
        }
        mock_head_resp.raise_for_status = MagicMock()

        mock_get_resp = MagicMock()
        mock_get_resp.headers = {"Content-Length": str(len(test_data))}
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.iter_content = MagicMock(return_value=[test_data])

        dl.stop_request = threading.Event()

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", return_value=mock_get_resp):
                dl.async_download()

        assert dl.state == dl.COMPLETED


class TestParallelDownload:
    """Test multi-connection parallel download."""

    def test_parallel_download_writes_correct_data(self, tmp_path):
        """Verify parallel download correctly assembles a file from ranges."""
        dest = str(tmp_path / "parallel.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)

        file_size = 2000  # 2000 bytes, split into 2x 1000-byte chunks
        data = bytes(range(256)) * (file_size // 256 + 1)
        data = data[:file_size]

        # Probe returns Range support
        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/resolved.bin"
        mock_head_resp.headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        mock_head_resp.raise_for_status = MagicMock()

        # Worker responses return the correct byte range
        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            range_header = headers.get("Range", "")
            if range_header:
                parts = range_header.replace("bytes=", "").split("-")
                start, end = int(parts[0]), int(parts[1])
                chunk = data[start : end + 1]
                resp.status_code = 206
                resp.iter_content = MagicMock(return_value=[chunk])
            else:
                resp.status_code = 200
                resp.iter_content = MagicMock(return_value=[data])
            return resp

        dl.stop_request = threading.Event()
        dl.MIN_CHUNK_SIZE = 100  # Lower threshold for testing

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        with open(dest, "rb") as f:
            result = f.read()
        assert result == data
        assert dl.downloaded_size == file_size

    def test_parallel_download_with_four_workers(self, tmp_path):
        """Test 4 workers downloading a file."""
        dest = str(tmp_path / "four_workers.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=4)

        file_size = 4000
        data = b"A" * 1000 + b"B" * 1000 + b"C" * 1000 + b"D" * 1000

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        mock_head_resp.raise_for_status = MagicMock()

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            range_header = headers.get("Range", "")
            parts = range_header.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            chunk = data[start : end + 1]
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[chunk])
            return resp

        dl.stop_request = threading.Event()
        dl.MIN_CHUNK_SIZE = 100

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        with open(dest, "rb") as f:
            result = f.read()
        assert result == data


class TestDownloadRange:
    """Test individual range download worker."""

    def test_download_range_writes_to_correct_offset(self, tmp_path):
        dest = str(tmp_path / "range_test.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()

        file_size = 1000
        with open(dest, "wb") as f:
            f.truncate(file_size)

        chunk_data = b"X" * 500
        mock_resp = MagicMock()
        mock_resp.status_code = 206
        mock_resp.iter_content = MagicMock(return_value=[chunk_data])

        with patch.object(dl._parallel_session, "get", return_value=mock_resp):
            dl._download_range("https://cdn.gog.com/file.bin", {}, 500, 999)

        # Drain the write queue via writer loop (pipelining)
        dl._write_queue.put(None)  # Sentinel to stop writer
        dl._writer_loop()

        with open(dest, "rb") as f:
            f.seek(500)
            assert f.read(500) == chunk_data

        assert dl.downloaded_size == 500

    def test_download_range_retries_on_failure(self, tmp_path):
        dest = str(tmp_path / "retry_test.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.RETRY_DELAY = 0  # No delay in tests

        file_size = 100
        with open(dest, "wb") as f:
            f.truncate(file_size)

        chunk_data = b"Y" * 100
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_resp_fail.iter_content = MagicMock()

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 206
        mock_resp_ok.iter_content = MagicMock(return_value=[chunk_data])

        # Fail twice, succeed on third attempt
        with patch.object(dl._parallel_session, "get", side_effect=[mock_resp_fail, mock_resp_fail, mock_resp_ok]):
            dl._download_range("https://cdn.gog.com/file.bin", {}, 0, 99)

        # Drain the write queue via writer loop (pipelining)
        dl._write_queue.put(None)  # Sentinel to stop writer
        dl._writer_loop()

        assert dl.downloaded_size == 100

    def test_download_range_cancellation(self, tmp_path):
        dest = str(tmp_path / "cancel_test.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.stop_request.set()  # Pre-cancelled

        file_size = 100
        with open(dest, "wb") as f:
            f.truncate(file_size)

        mock_resp = MagicMock()
        mock_resp.status_code = 206
        mock_resp.iter_content = MagicMock(return_value=[b"Z" * 100])

        with patch.object(dl._parallel_session, "get", return_value=mock_resp):
            dl._download_range("https://cdn.gog.com/file.bin", {}, 0, 99)

        # Should not have downloaded anything since cancelled
        assert dl.downloaded_size == 0


class TestCancelAndStates:
    """Test cancel and state management."""

    def test_cancel_sets_state(self, tmp_path):
        dest = str(tmp_path / "cancel.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.cancel()
        assert dl.state == dl.CANCELLED

    def test_cancel_sets_stop_request(self, tmp_path):
        dest = str(tmp_path / "cancel.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.cancel()
        assert dl.stop_request.is_set()

    def test_cancel_removes_file(self, tmp_path):
        dest = str(tmp_path / "cancel.bin")
        with open(dest, "w") as f:
            f.write("test")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.cancel()
        assert not os.path.isfile(dest)

    def test_on_download_completed_sets_state(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")
        dl.downloaded_size = 1000
        dl.full_size = 1000
        dl.on_download_completed()
        assert dl.state == dl.COMPLETED

    def test_on_download_completed_ignores_cancelled(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")
        dl.state = dl.CANCELLED
        dl.on_download_completed()
        assert dl.state == dl.CANCELLED

    def test_on_download_failed_sets_error(self):
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")
        error = Exception("test error")
        dl.on_download_failed(error)
        assert dl.state == dl.ERROR
        assert dl.error is error


class TestInstallerFileIntegration:
    """Test GOGDownloader integration with InstallerFile."""

    @pytest.fixture(autouse=True)
    def _setup_gi(self):
        """Ensure GTK version is required before importing InstallerFile."""
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
        except (ValueError, ImportError):
            pytest.skip("GTK 3.0 not available")

    def test_installer_file_downloader_class(self):
        """InstallerFile should expose downloader_class from file_meta."""
        from lutris.installer.installer_file import InstallerFile

        file = InstallerFile(
            "test-game",
            "test-file",
            {
                "url": "https://cdn.gog.com/file.bin",
                "filename": "file.bin",
                "downloader_class": GOGDownloader,
            },
        )
        assert file.downloader_class is GOGDownloader

    def test_installer_file_no_downloader_class(self):
        """InstallerFile without downloader_class should return None."""
        from lutris.installer.installer_file import InstallerFile

        file = InstallerFile(
            "test-game",
            "test-file",
            {
                "url": "https://example.com/file.bin",
                "filename": "file.bin",
            },
        )
        assert file.downloader_class is None

    def test_installer_file_string_meta_no_class(self):
        """InstallerFile with string meta should return None for downloader_class."""
        from lutris.installer.installer_file import InstallerFile

        file = InstallerFile(
            "test-game",
            "test-file",
            "https://example.com/file.bin",
        )
        assert file.downloader_class is None


class TestGOGServiceIntegration:
    """Test that the GOG service injects GOGDownloader into InstallerFile."""

    @pytest.fixture(autouse=True)
    def _setup_gi(self):
        """Ensure GTK version is required before importing GOG service."""
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            gi.require_version("Gdk", "3.0")
        except (ValueError, ImportError):
            pytest.skip("GTK 3.0 not available")

    def test_gog_format_links_includes_downloader_class(self):
        """_format_links should inject GOGDownloader as downloader_class."""
        from unittest.mock import MagicMock

        from lutris.services.gog import GOGService

        service = GOGService()
        installer = MagicMock()
        installer.game_slug = "test-game"

        links = [
            {
                "filename": "setup_test_game.exe",
                "url": "https://cdn.gog.com/setup_test_game.exe",
                "alternate_filenames": [],
                "total_size": 100000,
                "id": "1",
            },
        ]

        files = service._format_links(installer, "goginstaller", links)
        assert len(files) == 1
        assert files[0].downloader_class is GOGDownloader


class TestProgressTracking:
    """Test that progress tracking works with parallel downloads."""

    def test_downloaded_size_thread_safe(self, tmp_path):
        """Verify downloaded_size is correctly accumulated from multiple threads."""
        dest = str(tmp_path / "progress.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=4)
        dl.stop_request = threading.Event()
        dl.progress_event = threading.Event()

        # Simulate 4 workers each adding 250 bytes
        def add_bytes(amount):
            for _ in range(amount):
                with dl._download_lock:
                    dl.downloaded_size += 1

        threads = [threading.Thread(target=add_bytes, args=(250,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert dl.downloaded_size == 1000

    def test_check_progress_returns_fraction(self):
        """check_progress should work normally with parallel downloader."""
        dl = GOGDownloader("https://cdn.gog.com/file.bin", "/tmp/test.bin")
        dl.full_size = 1000
        dl.downloaded_size = 500
        dl.state = dl.DOWNLOADING
        dl.last_check_time = time.monotonic() - 1

        progress = dl.check_progress()
        assert 0.4 <= progress <= 0.6  # Approximately 50%


# ==================================================================
# Phase 3: Download resume tests
# ==================================================================


class TestResumeProgressCreation:
    """Test that parallel downloads create progress files."""

    def test_fresh_download_creates_progress_file(self, tmp_path):
        """A parallel download should create a .progress sidecar file."""
        dest = str(tmp_path / "fresh.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)

        file_size = 2000
        data = b"X" * file_size

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        mock_head_resp.raise_for_status = MagicMock()

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[data[start : end + 1]])
            return resp

        dl.stop_request = threading.Event()
        dl.MIN_CHUNK_SIZE = 100

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        # Progress file should be cleaned up on success
        assert not os.path.exists(dest + ".progress")

    def test_progress_file_records_completed_ranges(self, tmp_path):
        """Ranges that finish should be persisted in the progress file."""
        dest = str(tmp_path / "track.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)

        file_size = 2000
        data = b"A" * 1000 + b"B" * 1000

        mock_head_resp = MagicMock()
        mock_head_resp.url = "https://cdn.gog.com/file.bin"
        mock_head_resp.headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        mock_head_resp.raise_for_status = MagicMock()

        call_count = [0]

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            call_count[0] += 1
            # First range succeeds, second fails
            if start == 0:
                resp.status_code = 206
                resp.iter_content = MagicMock(return_value=[data[start : end + 1]])
            else:
                raise ConnectionError("Network down")
            return resp

        dl.stop_request = threading.Event()
        dl.MIN_CHUNK_SIZE = 100

        with patch.object(dl._parallel_session, "head", return_value=mock_head_resp):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.RETRY_ATTEMPTS = 1  # Don't retry in test
                dl.async_download()

        # Download should have failed
        assert dl.state == dl.ERROR
        # But progress file should exist with completed range
        progress = DownloadProgress(dest)
        assert progress.load() is True
        # At least the first range should be recorded
        assert len(progress.completed_ranges) >= 1


class TestResumeFromProgress:
    """Test resuming downloads from existing progress files."""

    def _make_head_resp(self, url, file_size):
        resp = MagicMock()
        resp.url = url
        resp.headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        resp.raise_for_status = MagicMock()
        return resp

    def test_resume_downloads_only_remaining_ranges(self, tmp_path):
        """Resume should only download ranges not yet completed."""
        dest = str(tmp_path / "resume.bin")
        file_size = 4000
        data = b"A" * 1000 + b"B" * 1000 + b"C" * 1000 + b"D" * 1000

        # Pre-create destination file (simulating a previous partial download)
        with open(dest, "wb") as f:
            f.truncate(file_size)
            # Write the first two ranges
            f.seek(0)
            f.write(data[0:1000])
            f.seek(1000)
            f.write(data[1000:2000])

        # Pre-create progress file showing ranges 0-1 complete
        progress = DownloadProgress(dest)
        all_ranges = [(0, 999), (1000, 1999), (2000, 2999), (3000, 3999)]
        progress.create("https://cdn.gog.com/file.bin", file_size, all_ranges)
        progress.mark_range_complete(0, 999)
        progress.mark_range_complete(1000, 1999)

        # Now create a downloader that should resume
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=4)
        dl.MIN_CHUNK_SIZE = 100
        dl.stop_request = threading.Event()

        downloaded_ranges = []

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            downloaded_ranges.append((start, end))
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[data[start : end + 1]])
            return resp

        mock_head = self._make_head_resp("https://cdn.gog.com/file.bin", file_size)

        with patch.object(dl._parallel_session, "head", return_value=mock_head):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        # Only ranges 2 and 3 should have been downloaded
        assert (0, 999) not in downloaded_ranges
        assert (1000, 1999) not in downloaded_ranges
        assert (2000, 2999) in downloaded_ranges
        assert (3000, 3999) in downloaded_ranges

        # File should be complete
        with open(dest, "rb") as f:
            result = f.read()
        assert result == data

        # Progress file should be cleaned up
        assert not os.path.exists(dest + ".progress")

    def test_resume_credits_already_downloaded_bytes(self, tmp_path):
        """Resume should credit bytes from completed ranges to downloaded_size."""
        dest = str(tmp_path / "credit.bin")
        file_size = 2000

        with open(dest, "wb") as f:
            f.truncate(file_size)
            f.write(b"X" * 1000)

        progress = DownloadProgress(dest)
        progress.create("https://cdn.gog.com/file.bin", file_size, [(0, 999), (1000, 1999)])
        progress.mark_range_complete(0, 999)

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)
        dl.MIN_CHUNK_SIZE = 100
        dl.stop_request = threading.Event()

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[b"Y" * (end - start + 1)])
            return resp

        mock_head = self._make_head_resp("https://cdn.gog.com/file.bin", file_size)

        with patch.object(dl._parallel_session, "head", return_value=mock_head):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        # Total downloaded = 1000 (already on disk) + 1000 (newly downloaded)
        assert dl.downloaded_size == 2000

    def test_resume_with_incompatible_file_size_starts_fresh(self, tmp_path):
        """If file size changed, progress is discarded and we start fresh."""
        dest = str(tmp_path / "incompat.bin")
        old_size = 3000

        with open(dest, "wb") as f:
            f.truncate(old_size)

        # Create progress with old file size
        progress = DownloadProgress(dest)
        progress.create("https://cdn.gog.com/file.bin", old_size, [(0, 2999)])
        progress.mark_range_complete(0, 2999)

        new_size = 4000  # File size changed on server
        data = b"N" * new_size

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)
        dl.MIN_CHUNK_SIZE = 100
        dl.stop_request = threading.Event()

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[data[start : end + 1]])
            return resp

        mock_head = self._make_head_resp("https://cdn.gog.com/file.bin", new_size)

        with patch.object(dl._parallel_session, "head", return_value=mock_head):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        assert dl.downloaded_size == new_size

    def test_resume_with_missing_dest_starts_fresh(self, tmp_path):
        """If dest file is gone but progress exists, start fresh."""
        dest = str(tmp_path / "missing.bin")
        file_size = 2000

        # Create progress without the actual file
        progress = DownloadProgress(dest)
        progress.create("https://cdn.gog.com/file.bin", file_size, [(0, 999), (1000, 1999)])
        progress.mark_range_complete(0, 999)

        data = b"F" * file_size
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)
        dl.MIN_CHUNK_SIZE = 100
        dl.stop_request = threading.Event()

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            resp = MagicMock()
            rng = headers.get("Range", "")
            parts = rng.replace("bytes=", "").split("-")
            start, end = int(parts[0]), int(parts[1])
            resp.status_code = 206
            resp.iter_content = MagicMock(return_value=[data[start : end + 1]])
            return resp

        mock_head = self._make_head_resp("https://cdn.gog.com/file.bin", file_size)

        with patch.object(dl._parallel_session, "head", return_value=mock_head):
            with patch.object(dl._parallel_session, "get", side_effect=mock_get):
                dl.async_download()

        assert dl.state == dl.COMPLETED
        # Fresh download, should have downloaded full size
        assert dl.downloaded_size == file_size

    def test_resume_skips_when_all_ranges_already_done(self, tmp_path):
        """If all ranges complete and file exists, skip download entirely."""
        dest = str(tmp_path / "skip.bin")
        file_size = 2000
        data = b"D" * file_size

        with open(dest, "wb") as f:
            f.write(data)

        progress = DownloadProgress(dest)
        progress.create("https://cdn.gog.com/file.bin", file_size, [(0, 999), (1000, 1999)])
        progress.mark_range_complete(0, 999)
        progress.mark_range_complete(1000, 1999)

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, num_workers=2)
        dl.MIN_CHUNK_SIZE = 100
        dl.stop_request = threading.Event()

        mock_head = self._make_head_resp("https://cdn.gog.com/file.bin", file_size)

        with patch.object(dl._parallel_session, "head", return_value=mock_head):
            with patch.object(dl._parallel_session, "get") as get_mock:
                dl.async_download()

        assert dl.state == dl.COMPLETED
        assert dl.downloaded_size == file_size
        # GET should not have been called — all ranges already done
        get_mock.assert_not_called()
        # Progress file should be cleaned up
        assert not os.path.exists(dest + ".progress")


class TestResumeStartMethod:
    """Test that start() preserves files when resume is possible."""

    def test_start_preserves_file_when_progress_exists(self, tmp_path):
        """start() should not delete dest if resumable progress is found."""
        dest = str(tmp_path / "preserve.bin")
        data = b"P" * 1000

        with open(dest, "wb") as f:
            f.write(data)

        progress = DownloadProgress(dest)
        progress.create("https://cdn.gog.com/file.bin", 2000, [(0, 999), (1000, 1999)])
        progress.mark_range_complete(0, 999)

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, overwrite=True, num_workers=2)

        # Patch AsyncCall so start() doesn't actually launch a thread
        with patch("lutris.util.gog_downloader.jobs.AsyncCall") as mock_async:
            mock_thread = MagicMock()
            mock_thread.stop_request = threading.Event()
            mock_async.return_value = mock_thread
            dl.start()

        # File should still exist
        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == data

    def test_start_deletes_file_when_no_progress(self, tmp_path):
        """start() should delete dest if no resumable progress exists."""
        dest = str(tmp_path / "delete.bin")
        with open(dest, "wb") as f:
            f.write(b"old data")

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest, overwrite=True, num_workers=2)

        with patch("lutris.util.gog_downloader.jobs.AsyncCall") as mock_async:
            mock_thread = MagicMock()
            mock_thread.stop_request = threading.Event()
            mock_async.return_value = mock_thread
            dl.start()

        assert not os.path.isfile(dest)


class TestCancelCleansProgress:
    """Test that cancel() removes progress files."""

    def test_cancel_removes_progress_file(self, tmp_path):
        dest = str(tmp_path / "cancel.bin")
        with open(dest, "wb") as f:
            f.write(b"data")

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()

        # Simulate active progress
        dl._progress = DownloadProgress(dest)
        dl._progress.create("https://cdn.gog.com/file.bin", 1000, [(0, 999)])

        dl.cancel()

        assert not os.path.isfile(dest)
        assert not os.path.exists(dest + ".progress")
        assert dl._progress is None

    def test_cancel_without_progress(self, tmp_path):
        """Cancel should work even if no progress was created."""
        dest = str(tmp_path / "nocancel.bin")
        with open(dest, "wb") as f:
            f.write(b"data")

        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.cancel()

        assert not os.path.isfile(dest)


class TestCompletionCleansProgress:
    """Test that on_download_completed() removes progress files."""

    def test_completed_removes_progress(self, tmp_path):
        dest = str(tmp_path / "done.bin")
        dl = GOGDownloader("https://cdn.gog.com/file.bin", dest)
        dl.downloaded_size = 1000
        dl.full_size = 1000

        dl._progress = DownloadProgress(dest)
        dl._progress.create("https://cdn.gog.com/file.bin", 1000, [(0, 999)])
        dl._progress.mark_range_complete(0, 999)

        dl.on_download_completed()

        assert dl.state == dl.COMPLETED
        assert not os.path.exists(dest + ".progress")
        assert dl._progress is None
