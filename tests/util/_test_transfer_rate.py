"""Tests for how download speeds are measured and smoothed."""

from unittest import TestCase
from unittest.mock import patch

from lutris.util import downloader
from lutris.util.downloader import DEFAULT_CHUNK_SIZE, SPEED_WINDOW_SECONDS, SimpleDownloader, TransferRateMeter

MEGABYTE = 1024 * 1024


class TestTransferRateMeter(TestCase):
    def test_no_rate_before_two_samples(self):
        meter = TransferRateMeter()
        meter.add_sample(0, now=0)
        self.assertEqual(meter.rate, 0)

    def test_steady_rate(self):
        meter = TransferRateMeter()
        for second in range(10):
            meter.add_sample(second * MEGABYTE, now=second)
        self.assertEqual(meter.rate, MEGABYTE)

    def test_burst_is_spread_over_the_window(self):
        meter = TransferRateMeter()
        for second in range(10):
            meter.add_sample(second * MEGABYTE, now=second)
        # 100 MB arrive in a tenth of a second, e.g. a chunk from a cache
        meter.add_sample(109 * MEGABYTE, now=9.1)
        self.assertLess(meter.rate, 30 * MEGABYTE)

    def test_burst_ages_out_of_the_window(self):
        meter = TransferRateMeter()
        meter.add_sample(0, now=0)
        meter.add_sample(100 * MEGABYTE, now=0.1)
        for second in range(1, 20):
            meter.add_sample(100 * MEGABYTE + second * MEGABYTE, now=second)
        self.assertAlmostEqual(meter.rate, MEGABYTE, delta=MEGABYTE * 0.25)

    def test_old_samples_are_dropped(self):
        meter = TransferRateMeter()
        for second in range(100):
            meter.add_sample(second * MEGABYTE, now=second)
        self.assertLessEqual(len(meter.samples), SPEED_WINDOW_SECONDS + 2)

    def test_reset_forgets_samples(self):
        meter = TransferRateMeter()
        meter.add_sample(0, now=0)
        meter.add_sample(MEGABYTE, now=1)
        meter.reset()
        self.assertEqual(meter.rate, 0)


class TestDownloaderSpeed(TestCase):
    """The speed shown by a downloader follows the current speed."""

    def test_speed_matches_chunked_progress(self):
        """Data lands in whole chunks, so most polls see either a chunk or
        nothing; the speed must reflect the average, not the chunk bursts."""
        dl = SimpleDownloader("https://example.com/file", "/tmp/file")
        clock = [0.0]
        with patch.object(downloader, "get_time", lambda: clock[0]):
            # Polled every 100 ms, a chunk lands every 500 ms: 1 MB/s
            for tick in range(1, 301):
                clock[0] = tick / 10
                if tick % 5 == 0:
                    dl.downloaded_size += DEFAULT_CHUNK_SIZE
                dl.get_stats()
        self.assertAlmostEqual(dl.average_speed, MEGABYTE, delta=MEGABYTE * 0.25)
