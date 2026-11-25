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


class NoFileDownloader(SimpleDownloader):
    """A downloader that writes nothing, for testing its state machine."""

    def _prepare_destination(self):
        pass


class TestJoinWakesUp(TestCase):
    """join() waits on the progress event; every way a download ends must set it."""

    def make_downloader(self):
        return NoFileDownloader("https://example.com/game.zip", "/nonexistent/game.zip")

    def test_completion_failure_and_cancel_all_set_the_event(self):
        for finish in (
            lambda dl: dl.on_download_completed(),
            lambda dl: dl.on_download_failed(RuntimeError("broken")),
            lambda dl: dl.cancel(),
        ):
            downloader = self.make_downloader()
            downloader.state = downloader.DOWNLOADING
            finish(downloader)
            self.assertTrue(downloader.progress_event.is_set())

    def test_join_raises_when_the_download_fails_before_any_data(self):
        join_is_waiting = threading.Event()

        class SignallingEvent(threading.Event):
            def wait(self, timeout=None):
                join_is_waiting.set()
                return super().wait(timeout)

        def fail_once_join_waits(_downloader):
            join_is_waiting.wait()
            raise RuntimeError("404 Not Found")

        downloader = self.make_downloader()
        downloader.RETRY_ATTEMPTS = 1
        downloader.progress_event = SignallingEvent()
        outcome = {}

        def run_join():
            try:
                downloader.join()
            except RuntimeError as ex:
                outcome["raised"] = str(ex)

        with patch.object(NoFileDownloader, "_do_download", fail_once_join_waits):
            downloader.start()
            joiner = threading.Thread(target=run_join, daemon=True)
            joiner.start()
            joiner.join(timeout=10)
        self.assertFalse(joiner.is_alive(), "join() never returned")
        self.assertEqual(outcome.get("raised"), "404 Not Found")
