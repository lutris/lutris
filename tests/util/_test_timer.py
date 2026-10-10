from unittest import TestCase
from unittest.mock import patch

from lutris.util.timer import Timer


class TestTimer(TestCase):
    def test_duration_is_zero_before_start(self):
        self.assertEqual(Timer().duration, 0)

    def test_duration_while_running(self):
        timer = Timer()
        with patch("lutris.util.timer.time.monotonic", side_effect=[100.0, 105.5]):
            timer.start()
            self.assertEqual(timer.duration, 5.5)

    def test_duration_after_end(self):
        timer = Timer()
        with patch("lutris.util.timer.time.monotonic", side_effect=[100.0, 103.25]):
            timer.start()
            timer.end()
            self.assertEqual(timer.duration, 3.25)

    def test_start_discards_the_previous_end(self):
        timer = Timer()
        with patch("lutris.util.timer.time.monotonic", side_effect=[1.0, 2.0, 3.0, 4.0]):
            timer.start()
            timer.end()
            timer.start()
            self.assertFalse(timer.finished)
            self.assertEqual(timer.duration, 1.0)
