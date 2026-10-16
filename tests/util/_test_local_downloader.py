"""Tests for installer files named as local paths, which become `file:` URLs."""

import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from lutris.util.downloader import SimpleDownloader


class TestLocalFileDownload(TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.dest = str(self.tmp_path / "dest.bin")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _download(self, url, chunk_size=None):
        """Run a download synchronously, skipping the background thread."""
        kwargs = {"chunk_size": chunk_size} if chunk_size else {}
        downloader = SimpleDownloader(url, self.dest, overwrite=True, **kwargs)
        downloader._prepare_destination()
        # Don't sit through the retry backoff when we are testing a failure.
        with patch.object(SimpleDownloader, "RETRY_DELAY", 0):
            downloader.async_download()
        return downloader

    def test_copies_file_contents(self):
        source = self.tmp_path / "source.bin"
        source.write_bytes(b"lutris" * 1000)

        downloader = self._download(source.as_uri())

        assert downloader.state == downloader.COMPLETED
        assert Path(self.dest).read_bytes() == b"lutris" * 1000
        assert downloader.full_size == 6000
        assert downloader.downloaded_size == 6000

    def test_leaves_the_source_in_place(self):
        source = self.tmp_path / "source.bin"
        source.write_bytes(b"lutris")

        self._download(source.as_uri())

        assert source.exists()

    def test_copies_an_empty_file(self):
        source = self.tmp_path / "empty.bin"
        source.touch()

        downloader = self._download(source.as_uri())

        assert downloader.state == downloader.COMPLETED
        assert downloader.progress_fraction == 1.0
        assert os.path.getsize(self.dest) == 0

    def test_copies_in_several_chunks(self):
        source = self.tmp_path / "source.bin"
        source.write_bytes(b"x" * 100)

        downloader = self._download(source.as_uri(), chunk_size=10)

        assert downloader.state == downloader.COMPLETED
        assert downloader.downloaded_size == 100

    def test_path_with_spaces(self):
        """A path built by InstallerFile is not percent-encoded."""
        source = self.tmp_path / "My Game.bin"
        source.write_bytes(b"lutris")

        downloader = self._download("file://%s" % source)

        assert downloader.state == downloader.COMPLETED
        assert Path(self.dest).read_bytes() == b"lutris"

    def test_percent_encoded_path(self):
        """A `file:` URL written out by hand may be encoded; urlopen decodes it."""
        source = self.tmp_path / "My Game.bin"
        source.write_bytes(b"lutris")

        downloader = self._download(source.as_uri())

        assert "%20" in source.as_uri()
        assert downloader.state == downloader.COMPLETED
        assert Path(self.dest).read_bytes() == b"lutris"

    @contextmanager
    def _spy_on_urlopen(self):
        """Collect the responses urlopen hands back, so we can check they got closed."""
        opened = []
        real_urlopen = urllib.request.urlopen

        def spy(*args, **kwargs):
            response = real_urlopen(*args, **kwargs)
            opened.append(response)
            return response

        with patch("urllib.request.urlopen", spy):
            yield opened

    def test_closes_the_source_on_success(self):
        source = self.tmp_path / "source.bin"
        source.write_bytes(b"lutris")

        with self._spy_on_urlopen() as opened:
            self._download(source.as_uri())

        assert opened
        assert all(response.closed for response in opened)

    def test_closes_the_source_when_the_write_fails(self):
        """A failure is stored in downloader.error, whose traceback keeps this frame -- and so
        the open file -- alive, so the handle has to be closed explicitly rather than by GC."""
        source = self.tmp_path / "source.bin"
        source.write_bytes(b"lutris")

        with self._spy_on_urlopen() as opened:
            with patch.object(SimpleDownloader, "_write_chunks", side_effect=OSError("disk full")):
                downloader = self._download(source.as_uri())

        assert downloader.state == downloader.ERROR
        assert opened
        assert all(response.closed for response in opened)

    def test_missing_source_fails(self):
        downloader = self._download((self.tmp_path / "nope.bin").as_uri())

        assert downloader.state == downloader.ERROR
        assert isinstance(downloader.error, urllib.error.URLError)

    def test_directory_source_fails(self):
        source = self.tmp_path / "a-folder"
        source.mkdir()

        downloader = self._download(source.as_uri())

        assert downloader.state == downloader.ERROR
        assert isinstance(downloader.error, urllib.error.URLError)
