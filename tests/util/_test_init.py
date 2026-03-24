import unittest

from lutris.util import cache_single


class TestCacheSingle(unittest.TestCase):
    def test_no_args(self):
        call_count = 0

        @cache_single
        def no_args():
            nonlocal call_count
            call_count += 1
            return call_count

        self.assertEqual(no_args(), 1)
        self.assertEqual(no_args(), 1)

        no_args.cache_clear()
        self.assertEqual(no_args(), 2)
        self.assertEqual(no_args(), 2)

    def test_with_args(self):
        @cache_single
        def with_args(return_value):
            return return_value

        self.assertEqual(with_args(1), 1)
        self.assertEqual(with_args(2), 2)

        with_args.cache_clear()
        self.assertEqual(with_args(3), 3)
