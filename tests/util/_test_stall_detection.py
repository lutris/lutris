"""Tests for stall detection and retry logic in the download system."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from lutris.util.downloader import BaseDownloader, DownloadStallError, SimpleDownloader, StallMonitor, get_time


class TestDownloadStallError:
    """Test the DownloadStallError exception class."""

    def test_carries_throughput(self):
        err = DownloadStallError(throughput=150.5, duration=30.0)
        assert err.throughput == 150.5

    def test_carries_duration(self):
        err = DownloadStallError(throughput=100.0, duration=35.2)
        assert err.duration == 35.2

    def test_message_contains_throughput(self):
        err = DownloadStallError(throughput=42.3, duration=30.0)
        assert "42.3" in str(err)

    def test_message_contains_duration(self):
        err = DownloadStallError(throughput=100.0, duration=31.5)
        assert "31.5" in str(err)

    def test_is_exception(self):
        err = DownloadStallError(throughput=0.0, duration=30.0)
        assert isinstance(err, Exception)


class TestCheckStall:
    """Test the throughput-window logic in StallMonitor."""

    def _make_monitor(self):
        return StallMonitor(BaseDownloader.LOW_SPEED_LIMIT, BaseDownloader.LOW_SPEED_TIME)

    def test_first_call_initializes_window(self):
        """First call should set the stall window start, not raise."""
        monitor = self._make_monitor()
        # Should not raise
        monitor.check(1000)
        assert monitor.window_start is not None
        assert monitor.bytes_at_window_start == 1000

    def test_good_throughput_resets_window(self):
        """When throughput is above threshold, the stall window resets."""
        monitor = self._make_monitor()
        monitor.window_start = get_time() - 5.0  # 5 seconds ago
        monitor.bytes_at_window_start = 0
        # 10000 bytes in 5 seconds = 2000 B/s — well above 200 B/s
        monitor.check(10000)
        # Window should have been reset
        assert monitor.bytes_at_window_start == 10000

    def test_low_throughput_does_not_raise_immediately(self):
        """Low throughput within the time window should not raise."""
        monitor = self._make_monitor()
        monitor.window_start = get_time() - 10.0  # 10 seconds ago
        monitor.bytes_at_window_start = 0
        # 100 bytes in 10 seconds = 10 B/s — below threshold but only 10s elapsed
        monitor.check(100)
        # Should not raise because LOW_SPEED_TIME (30s) not exceeded

    def test_stall_raises_after_timeout(self):
        """Low throughput exceeding LOW_SPEED_TIME should raise."""
        monitor = self._make_monitor()
        monitor.window_start = get_time() - 31.0  # 31 seconds ago
        monitor.bytes_at_window_start = 0
        # 100 bytes in 31 seconds = ~3.2 B/s — below 200 B/s for > 30s
        with pytest.raises(DownloadStallError) as exc_info:
            monitor.check(100)
        assert exc_info.value.duration >= 30.0
        assert exc_info.value.throughput < 200.0

    def test_zero_bytes_triggers_stall(self):
        """Zero bytes received should eventually trigger stall."""
        monitor = self._make_monitor()
        monitor.window_start = get_time() - 35.0
        monitor.bytes_at_window_start = 0
        with pytest.raises(DownloadStallError):
            monitor.check(0)

    def test_recovery_resets_timer(self):
        """If throughput recovers within the window, timer resets."""
        monitor = self._make_monitor()
        monitor.window_start = get_time() - 20.0  # 20 seconds of slow speed
        monitor.bytes_at_window_start = 100
        # Now deliver a burst: enough bytes to push throughput above threshold
        # Need > 200 B/s over 20 seconds = 4000 bytes
        monitor.check(100 + 5000)
        # Window should have reset (not raised)
        assert monitor.bytes_at_window_start == 5100


class TestStallMonitorIsolation:
    """Each download stream must own its StallMonitor.

    Regression tests for the parallel-download stall race: GOGDownloader runs
    several workers concurrently, each with its own byte counter. When they
    shared a single window, one worker's counter polluted another's, producing
    nonsensical (negative) throughput and spurious stalls on healthy downloads.
    """

    def test_separate_monitors_do_not_interfere(self):
        """Two interleaved streams with independent counters never stall."""
        fast = StallMonitor(BaseDownloader.LOW_SPEED_LIMIT, BaseDownloader.LOW_SPEED_TIME)
        slow = StallMonitor(BaseDownloader.LOW_SPEED_LIMIT, BaseDownloader.LOW_SPEED_TIME)
        # 'fast' streams huge byte counts, 'slow' streams small ones. If they
        # shared a window, slow.check() would read fast's large start value and
        # compute a negative throughput. With separate monitors, both are healthy.
        fast_bytes = 0
        slow_bytes = 0
        for _ in range(50):
            fast_bytes += 10_000_000
            slow_bytes += 1_000_000
            fast.check(fast_bytes)  # ~10 MB between calls — healthy
            slow.check(slow_bytes)  # ~1 MB between calls — healthy
        # No DownloadStallError raised: both windows reset on good throughput.

    def test_shared_window_would_go_negative(self):
        """Document the bug: one shared window across mismatched counters
        yields negative throughput. This is what separate monitors prevent."""
        shared = StallMonitor(BaseDownloader.LOW_SPEED_LIMIT, BaseDownloader.LOW_SPEED_TIME)
        # Worker A opens the window at a high byte count.
        shared.check(8_000_000)
        # Worker B then reports its own, smaller counter into the same window.
        shared.window_start = get_time() - 1.0  # 1s elapsed
        bytes_in_window = 2_000_000 - shared.bytes_at_window_start
        assert bytes_in_window < 0  # negative => bogus "stall" on a healthy stream

    def test_monitor_raises_on_genuine_stall(self):
        """A single monitor still detects a real stall (feature preserved)."""
        monitor = StallMonitor(BaseDownloader.LOW_SPEED_LIMIT, BaseDownloader.LOW_SPEED_TIME)
        monitor.check(0)  # open window
        monitor.window_start = get_time() - 31.0  # 31s elapsed, no progress
        with pytest.raises(DownloadStallError):
            monitor.check(100)  # ~3 B/s for >30s


class TestDownloaderRetry:
    """Test retry logic in SimpleDownloader."""

    def _make_downloader(self, tmp_path):
        dest = str(tmp_path / "test.bin")
        dl = SimpleDownloader("https://example.com/file.bin", dest)
        dl.stop_request = threading.Event()
        return dl

    @patch.object(SimpleDownloader, "on_download_completed")
    @patch.object(SimpleDownloader, "_do_download")
    def test_success_on_first_try(self, mock_do, mock_complete, tmp_path):
        """Successful download should not retry."""
        dl = self._make_downloader(tmp_path)
        mock_do.return_value = None  # Success

        dl.async_download()

        assert mock_do.call_count == 1
        mock_complete.assert_called_once()

    @patch.object(SimpleDownloader, "on_download_completed")
    @patch.object(SimpleDownloader, "_do_download")
    def test_retries_on_stall_error(self, mock_do, mock_complete, tmp_path):
        """DownloadStallError should trigger retry."""
        dl = self._make_downloader(tmp_path)
        # Fail twice with stall, succeed on third
        mock_do.side_effect = [
            DownloadStallError(throughput=50.0, duration=31.0),
            DownloadStallError(throughput=30.0, duration=32.0),
            None,  # Success
        ]

        with patch.object(dl, "_prepare_retry"):
            with patch("lutris.util.downloader.time") as mock_time:
                mock_time.monotonic = time.monotonic
                mock_time.sleep = MagicMock()
                dl.async_download()

        assert mock_do.call_count == 3
        mock_complete.assert_called_once()

    @patch.object(SimpleDownloader, "_do_download")
    def test_fails_after_max_retries(self, mock_do, tmp_path):
        """Should fail after RETRY_ATTEMPTS exhausted."""
        dl = self._make_downloader(tmp_path)
        stall_err = DownloadStallError(throughput=10.0, duration=30.0)
        mock_do.side_effect = stall_err

        with patch.object(dl, "_prepare_retry"):
            with patch("lutris.util.downloader.time") as mock_time:
                mock_time.monotonic = time.monotonic
                mock_time.sleep = MagicMock()
                dl.async_download()

        assert mock_do.call_count == dl.RETRY_ATTEMPTS
        assert dl.state == dl.ERROR
        assert dl.error is stall_err

    @patch.object(SimpleDownloader, "_do_download")
    def test_no_retry_on_404(self, mock_do, tmp_path):
        """HTTP 404 should not retry."""
        dl = self._make_downloader(tmp_path)
        response = MagicMock()
        response.status_code = 404
        http_err = requests.HTTPError(response=response)
        mock_do.side_effect = http_err

        dl.async_download()

        assert mock_do.call_count == 1
        assert dl.state == dl.ERROR

    @patch.object(SimpleDownloader, "on_download_completed")
    @patch.object(SimpleDownloader, "_do_download")
    def test_retry_on_500(self, mock_do, mock_complete, tmp_path):
        """HTTP 500 should trigger retry."""
        dl = self._make_downloader(tmp_path)
        response = MagicMock()
        response.status_code = 500
        http_err = requests.HTTPError(response=response)
        mock_do.side_effect = [http_err, None]

        with patch.object(dl, "_prepare_retry"):
            with patch("lutris.util.downloader.time") as mock_time:
                mock_time.monotonic = time.monotonic
                mock_time.sleep = MagicMock()
                dl.async_download()

        assert mock_do.call_count == 2
        mock_complete.assert_called_once()

    @patch.object(SimpleDownloader, "on_download_completed")
    @patch.object(SimpleDownloader, "_do_download")
    def test_retry_on_429(self, mock_do, mock_complete, tmp_path):
        """HTTP 429 (rate limit) should trigger retry."""
        dl = self._make_downloader(tmp_path)
        response = MagicMock()
        response.status_code = 429
        http_err = requests.HTTPError(response=response)
        mock_do.side_effect = [http_err, None]

        with patch.object(dl, "_prepare_retry"):
            with patch("lutris.util.downloader.time") as mock_time:
                mock_time.monotonic = time.monotonic
                mock_time.sleep = MagicMock()
                dl.async_download()

        assert mock_do.call_count == 2
        mock_complete.assert_called_once()

    def test_is_retryable_http_error_no_response(self):
        """HTTP error with no response should be retryable."""
        err = requests.HTTPError(response=None)
        assert SimpleDownloader._is_retryable_http_error(err) is True

    def test_is_retryable_http_error_403(self):
        """HTTP 403 should not be retryable."""
        response = MagicMock()
        response.status_code = 403
        err = requests.HTTPError(response=response)
        assert SimpleDownloader._is_retryable_http_error(err) is False
