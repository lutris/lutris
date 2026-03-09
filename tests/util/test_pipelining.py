"""Tests for download pipelining in GOGDownloader."""

import os
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from lutris.util.download_progress import DownloadProgress
from lutris.util.gog_downloader import GOGDownloader


class TestWriteQueue:
    """Test the pipelining write queue setup."""

    def test_has_write_queue(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert isinstance(dl._write_queue, queue.Queue)

    def test_write_queue_maxsize(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert dl._write_queue.maxsize == 64

    def test_has_writer_error_event(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert isinstance(dl._writer_error_event, threading.Event)

    def test_writer_error_initially_none(self):
        dl = GOGDownloader("https://example.com/file.bin", "/tmp/test.bin")
        assert dl._writer_error is None


class TestWriterLoop:
    """Test the _writer_loop() writer thread."""

    def test_writes_data_correctly(self, tmp_path):
        """Writer thread should write data at the correct offset."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()

        # Pre-allocate file
        with open(dest, "wb") as f:
            f.truncate(100)

        # Enqueue some data
        dl._write_queue.put((0, b"AAAA", 0, None))
        dl._write_queue.put((50, b"BBBB", 50, None))
        dl._write_queue.put(None)  # Sentinel

        dl._writer_loop()

        with open(dest, "rb") as f:
            content = f.read()
        assert content[:4] == b"AAAA"
        assert content[50:54] == b"BBBB"

    def test_updates_downloaded_size(self, tmp_path):
        """Writer should increment downloaded_size after writing."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()

        with open(dest, "wb") as f:
            f.truncate(100)

        dl._write_queue.put((0, b"X" * 50, 0, None))
        dl._write_queue.put((50, b"Y" * 50, 50, None))
        dl._write_queue.put(None)

        dl._writer_loop()

        assert dl.downloaded_size == 100

    def test_marks_range_complete(self, tmp_path):
        """Writer marks range complete when range_end is set."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()

        with open(dest, "wb") as f:
            f.truncate(100)

        dl._progress = DownloadProgress(dest)
        dl._progress.create("https://example.com/file.bin", 100, [(0, 49), (50, 99)])

        # Last chunk of first range
        dl._write_queue.put((0, b"A" * 50, 0, 49))
        # Last chunk of second range
        dl._write_queue.put((50, b"B" * 50, 50, 99))
        dl._write_queue.put(None)

        dl._writer_loop()

        remaining = dl._progress.get_remaining_ranges()
        assert len(remaining) == 0

    def test_handles_stop_request(self, tmp_path):
        """Writer should exit when stop_request is set."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()
        dl.stop_request.set()  # Pre-cancel

        with open(dest, "wb") as f:
            f.truncate(100)

        # Even with data in queue, should exit due to stop_request
        dl._write_queue.put((0, b"data", 0, None))
        dl._write_queue.put(None)

        dl._writer_loop()  # Should not hang

    def test_sets_error_on_write_failure(self, tmp_path):
        """Writer should set error event on disk failure."""
        dest = str(tmp_path / "readonly_dir" / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()

        # Don't create the file — writer will fail to open it
        dl._write_queue.put((0, b"data", 0, None))
        dl._write_queue.put(None)

        dl._writer_loop()

        assert dl._writer_error is not None
        assert dl._writer_error_event.is_set()


class TestPipelineBackpressure:
    """Test that backpressure works correctly with bounded queue."""

    def test_queue_blocks_when_full(self, tmp_path):
        """Workers should block when queue is at maxsize."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest)

        # Fill the queue to capacity
        for i in range(64):
            dl._write_queue.put((i, b"x", 0, None))

        assert dl._write_queue.full()

        # Verify put would block (use put_nowait to test)
        with pytest.raises(queue.Full):
            dl._write_queue.put_nowait((99, b"overflow", 0, None))


class TestGOGDownloaderStallDetection:
    """Test stall detection in GOGDownloader._download_range()."""

    def test_stall_triggers_retry(self, tmp_path):
        """A stalled range should trigger retry via the existing retry mechanism."""
        dest = str(tmp_path / "output.bin")
        dl = GOGDownloader("https://example.com/file.bin", dest, num_workers=1)
        dl.stop_request = threading.Event()
        dl._writer_error_event = threading.Event()

        # Pre-allocate file
        with open(dest, "wb") as f:
            f.truncate(1000)

        # Create a mock response that simulates a stall then success
        call_count = [0]

        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            call_count[0] += 1
            mock_response = MagicMock()
            mock_response.status_code = 206

            if call_count[0] == 1:
                # First attempt: simulate stall by manipulating stall state
                def slow_iter(chunk_size=None):
                    dl._stall_start = time.monotonic() - 35  # 35 seconds ago
                    dl._stall_bytes_at_start = 0
                    yield b"x"  # Tiny chunk triggers stall check

                mock_response.iter_content = slow_iter
            else:
                # Retry: succeed
                def fast_iter(chunk_size=None):
                    yield b"A" * 1000

                mock_response.iter_content = fast_iter

            return mock_response

        dl._parallel_session.get = mock_get

        headers = dl._build_request_headers()

        with patch.object(dl._write_queue, "put"):
            dl._download_range("https://example.com/file.bin", headers, 0, 999)

        # Verify retry occurred
        assert call_count[0] >= 2


class TestPipelinedDownloadEndToEnd:
    """Integration test: full pipelined download with mock HTTP."""

    @patch.object(GOGDownloader, "_probe_server")
    def test_pipelined_download_completes(self, mock_probe, tmp_path):
        """Full download should complete with pipelining."""
        dest = str(tmp_path / "game.bin")
        file_size = 20 * 1024 * 1024  # 20 MB — above MIN_CHUNK_SIZE * 2

        dl = GOGDownloader("https://cdn.gog.com/game.bin", dest, num_workers=2)
        dl.stop_request = threading.Event()

        mock_probe.return_value = ("https://cdn.gog.com/game.bin", file_size, True)

        # Mock the parallel session for range requests
        def mock_get(url, headers=None, stream=None, timeout=None, cookies=None):
            response = MagicMock()
            response.status_code = 206

            # Parse the Range header to determine what data to return
            range_header = headers.get("Range", "")
            if range_header.startswith("bytes="):
                parts = range_header[6:].split("-")
                start, end = int(parts[0]), int(parts[1])
                size = end - start + 1
                # Generate deterministic data based on offset
                data = bytes([start % 256]) * size

                def iter_content(chunk_size=None):
                    remaining = size
                    while remaining > 0:
                        cs = min(chunk_size or 512 * 1024, remaining)
                        yield data[:cs]
                        remaining -= cs

                response.iter_content = iter_content
            return response

        dl._parallel_session = MagicMock()
        dl._parallel_session.get = mock_get
        dl._parallel_session.head.return_value = MagicMock(
            url="https://cdn.gog.com/game.bin",
            headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
            status_code=200,
        )

        dl.async_download()

        assert dl.state == dl.COMPLETED
        assert dl.downloaded_size == file_size
        assert os.path.isfile(dest)
        assert os.path.getsize(dest) == file_size

    @patch.object(GOGDownloader, "_probe_server")
    def test_small_file_skips_pipelining(self, mock_probe, tmp_path):
        """Files below MIN_CHUNK_SIZE * 2 should use single-stream."""
        dest = str(tmp_path / "small.bin")
        file_size = 1000  # Very small

        dl = GOGDownloader("https://cdn.gog.com/small.bin", dest, num_workers=4)
        dl.stop_request = threading.Event()

        mock_probe.return_value = ("https://cdn.gog.com/small.bin", file_size, True)

        # Mock single-stream response
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Content-Length": str(file_size)}

        def iter_content(chunk_size=None):
            yield b"X" * file_size

        response.iter_content = iter_content

        dl._parallel_session = MagicMock()
        dl._parallel_session.get.return_value = response
        dl._parallel_session.head.return_value = MagicMock(
            url="https://cdn.gog.com/small.bin",
            headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
            status_code=200,
        )

        dl.async_download()

        assert dl.state == dl.COMPLETED
        assert dl.downloaded_size == file_size
