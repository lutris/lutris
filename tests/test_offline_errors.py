"""Offline helpers: connection errors get a friendly message, not a traceback."""

import unittest

from lutris.util.http import HTTPError, UnauthorizedAccessError, is_connection_error


class TestIsConnectionError(unittest.TestCase):
    def test_connection_error_is_detected(self):
        err = HTTPError(
            "Unable to connect to server https://lutris.net/api/installers/undertail: "
            "<urlopen error [Errno -3] Temporary failure in name resolution>"
        )
        self.assertTrue(is_connection_error(err))

    def test_other_http_errors_are_not_connection_errors(self):
        self.assertFalse(is_connection_error(HTTPError("404 Not Found", code=404)))
        self.assertFalse(is_connection_error(HTTPError("Request timed out")))

    def test_non_http_errors_are_not_connection_errors(self):
        self.assertFalse(is_connection_error(ValueError("bad value")))
        self.assertFalse(is_connection_error(UnauthorizedAccessError("Access denied")))


if __name__ == "__main__":
    unittest.main()
