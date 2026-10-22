"""Tests for SimpleDownloader's handling of the streaming response."""

import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lutris.util.downloader import SimpleDownloader


class FakeResponse:
    """Minimal stand-in for a streaming requests.Response."""

    def __init__(self, chunks, raise_after=None):
        self.chunks = chunks
        self.raise_after = raise_after
        self.status_code = 200
        self.headers = {"Content-Length": str(sum(len(chunk) for chunk in chunks))}
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        self.close()

    def close(self):
        self.closed = True

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=None):  # noqa: ARG002
        for index, chunk in enumerate(self.chunks):
            if self.raise_after is not None and index == self.raise_after:
                raise OSError("connection reset")
            yield chunk


class TestResponseIsClosed(TestCase):
    """An abandoned stream holds its connection out of the pool, so the response
    has to be closed on every exit path, not just on a completed download."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.dest = str(Path(self.tmp_dir.name) / "dest.bin")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _run(self, response, stop_request=None):
        downloader = SimpleDownloader("https://example.com/game.bin", self.dest, overwrite=True)
        downloader._prepare_destination()
        downloader.stop_request = stop_request
        with patch("lutris.util.downloader.requests.get", return_value=response):
            try:
                downloader._do_download()
            except OSError:
                pass
        return downloader

    def test_closed_after_a_completed_download(self):
        response = FakeResponse([b"a" * 10, b"b" * 10])

        self._run(response)

        assert response.closed

    def test_closed_when_cancelled_part_way(self):
        response = FakeResponse([b"a" * 10, b"b" * 10])
        stop_request = threading.Event()
        stop_request.set()

        self._run(response, stop_request=stop_request)

        assert response.closed

    def test_closed_when_the_stream_fails(self):
        response = FakeResponse([b"a" * 10, b"b" * 10], raise_after=1)

        self._run(response)

        assert response.closed
