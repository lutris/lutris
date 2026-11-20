"""Tests for lutris.util.file_downloads: downloads that run without any UI.

The network is replaced by FakeDownloader, files are real ones in a temporary
directory, and the main loop is the hand-driven fake_main_loop fixture.
"""

import os
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest

from lutris.util.download_cache import CacheState, get_cache_state
from lutris.util.downloader import BaseDownloader
from lutris.util.file_downloads import (
    MAX_CONCURRENT_FILES,
    DownloadState,
    FileCollectionDownload,
    SingleFileDownload,
)


class FakeDownloader:
    """Stands in for SimpleDownloader; tests move it through its states by hand."""

    INIT = "init"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

    created: list["FakeDownloader"] = []

    def __init__(self, url, dest, referer=None, overwrite=False):
        self.url = url
        self.dest = dest
        self.state = self.INIT
        self.full_size = 100
        self.downloaded_size = 0
        self.average_speed = 0
        self.time_left = "0:00:00"
        self.error = None
        self.starts = 0
        FakeDownloader.created.append(self)

    def start(self):
        self.state = self.DOWNLOADING
        self.starts += 1

    def reset(self):
        self.state = self.INIT

    def cancel(self):
        self.state = self.CANCELLED

    def check_progress(self):
        return self.downloaded_size / self.full_size

    def finish(self, size=100):
        with open(self.dest, "wb") as dest_file:
            dest_file.write(b"x" * size)
        self.downloaded_size = size
        self.state = self.COMPLETED

    def fail(self, message="network failure"):
        self.error = RuntimeError(message)
        self.state = self.ERROR


@pytest.fixture(autouse=True)
def fresh_fake_downloaders():
    FakeDownloader.created = []


def make_file(tmp_path, name, size=100):
    return SimpleNamespace(
        filename=name,
        url=f"https://cdn.example.com/{name}",
        dest_file=str(tmp_path / name),
        referer=None,
        downloader_class=FakeDownloader,
        size=size,
    )


def make_collection(files):
    return SimpleNamespace(
        files_list=files,
        human_url="Test Collection",
        num_files=len(files),
        full_size=sum(file.size for file in files),
    )


def follow(download):
    """Record the (state, error) of each notification, as a frontend would see them."""
    seen = []
    download.changed.register(lambda state, status, error: seen.append((state, error)))
    return seen


def active(download):
    return [downloader for downloader in FakeDownloader.created if downloader.state == FakeDownloader.DOWNLOADING]


# ── Collections ──────────────────────────────────────────────────────


def test_collection_downloads_two_files_at_a_time(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin", "c.bin")]
    download = FileCollectionDownload(make_collection(files))

    download.start()

    assert MAX_CONCURRENT_FILES == 2
    assert len(active(download)) == 2
    assert download.state == DownloadState.DOWNLOADING


def test_collection_skips_files_already_downloaded(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    for file in files:
        with open(file.dest_file, "wb") as dest_file:
            dest_file.write(b"x" * 50)
    download = FileCollectionDownload(make_collection(files))
    seen = follow(download)

    download.start()
    fake_main_loop.run_pending()

    assert FakeDownloader.created == []
    assert download.num_files_downloaded == 2
    assert seen == [(DownloadState.COMPLETED, None)]


def test_finished_file_is_moved_into_place_and_the_next_one_starts(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin", "c.bin")]
    download = FileCollectionDownload(make_collection(files))
    download.start()
    first = FakeDownloader.created[0]

    first.finish()
    fake_main_loop.run_pending()

    finished_path = first.dest.removesuffix(".tmp")
    assert os.path.exists(finished_path) and not os.path.exists(first.dest)
    assert get_cache_state(finished_path) == CacheState.DOWNLOADED
    assert len(FakeDownloader.created) == 3
    assert len(active(download)) == 2


def test_collection_reports_aggregate_progress(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    download.start()
    first, second = FakeDownloader.created

    first.downloaded_size = 50
    second.downloaded_size = 25
    fake_main_loop.run_pending()

    assert download.status.downloaded_size == 75
    assert download.status.fraction == pytest.approx(75 / 200)
    assert sorted(download.status.current_files) == ["a.bin", "b.bin"]


def test_collection_completes_when_every_file_is_done(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    seen = follow(download)
    download.start()

    for downloader in list(FakeDownloader.created):
        downloader.finish()
    fake_main_loop.run_pending()
    fake_main_loop.run_pending()

    assert download.state == DownloadState.COMPLETED
    assert download.num_files_downloaded == 2
    assert seen[-1] == (DownloadState.COMPLETED, None)


def test_failed_file_is_retried_on_its_own(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    download.start()
    failing = FakeDownloader.created[0]

    failing.fail()
    fake_main_loop.run_pending()

    assert download.state == DownloadState.DOWNLOADING
    assert len(FakeDownloader.created) == 3  # A fresh downloader for the failed file
    assert FakeDownloader.created[2].url == failing.url
    assert FakeDownloader.created[2].starts == 1


def test_collection_fails_once_a_file_runs_out_of_retries(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    seen = follow(download)
    download.start()
    url = FakeDownloader.created[0].url

    for _attempt in range(FileCollectionDownload.max_retries + 1):
        [downloader for downloader in active(download) if downloader.url == url][0].fail("gone")
        fake_main_loop.run_pending()

    assert download.state == DownloadState.FAILED
    assert str(download.error) == "gone"
    assert active(download) == []  # The other file was cancelled
    assert seen[-1][0] == DownloadState.FAILED


def test_cancel_stops_every_file_and_is_reported_once(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    seen = follow(download)
    download.start()

    download.cancel()
    fake_main_loop.run_pending()
    fake_main_loop.run_pending()

    assert active(download) == []
    assert [state for state, _error in seen].count(DownloadState.CANCELLED) == 1


def test_retry_downloads_the_files_that_were_interrupted(tmp_path, fake_main_loop):
    files = [make_file(tmp_path, name) for name in ("a.bin", "b.bin")]
    download = FileCollectionDownload(make_collection(files))
    download.start()
    download.cancel()

    download.retry()

    restarted_urls = sorted(downloader.url for downloader in active(download))
    assert restarted_urls == sorted(file.url for file in files)


def test_retry_does_not_leave_a_second_poll_running(tmp_path, fake_main_loop):
    download = FileCollectionDownload(make_collection([make_file(tmp_path, "a.bin")]))
    download.start()
    download.cancel()
    download.retry()

    polls = [callback for callback, delay in fake_main_loop.scheduled.values() if delay > 0]
    assert len(polls) == 1


def test_collection_is_cancelled_when_a_downloader_cannot_be_created(tmp_path, fake_main_loop):
    file = make_file(tmp_path, "a.bin")
    file.downloader_class = None
    download = FileCollectionDownload(make_collection([file]))

    with patch("lutris.util.file_downloads.SimpleDownloader", side_effect=RuntimeError("no network")):
        download.start()

    assert download.state == DownloadState.CANCELLED
    assert str(download.error) == "no network"


# ── Single files ─────────────────────────────────────────────────────


def single_download(tmp_path):
    dest = str(tmp_path / "game.exe")
    downloader = FakeDownloader("https://example.com/game.exe", dest + ".tmp")
    download = SingleFileDownload("https://example.com/game.exe", dest, downloader=cast(BaseDownloader, downloader))
    return download, downloader


def test_single_download_moves_the_file_into_place(tmp_path, fake_main_loop):
    download, downloader = single_download(tmp_path)
    seen = follow(download)
    download.start()

    downloader.finish(size=10)
    fake_main_loop.run_pending()
    fake_main_loop.run_pending()

    assert download.state == DownloadState.COMPLETED
    assert os.path.getsize(download.dest) == 10
    assert get_cache_state(download.dest) == CacheState.DOWNLOADED
    assert seen[0][0] == DownloadState.DOWNLOADING
    assert seen[-1] == (DownloadState.COMPLETED, None)


def test_single_download_reports_failure(tmp_path, fake_main_loop):
    download, downloader = single_download(tmp_path)
    download.start()

    downloader.fail("timed out")
    fake_main_loop.run_pending()

    assert download.state == DownloadState.FAILED
    assert str(download.error) == "timed out"


def test_single_download_cancel_is_reported_once(tmp_path, fake_main_loop):
    download, downloader = single_download(tmp_path)
    seen = follow(download)
    download.start()

    download.cancel()
    fake_main_loop.run_pending()
    fake_main_loop.run_pending()

    assert downloader.state == FakeDownloader.CANCELLED
    assert [state for state, _error in seen] == [DownloadState.DOWNLOADING, DownloadState.CANCELLED]


def test_single_download_that_cannot_start_is_cancelled_with_the_error(tmp_path, fake_main_loop):
    download = SingleFileDownload("https://example.com/game.exe", str(tmp_path / "game.exe"))

    with patch("lutris.util.file_downloads.SimpleDownloader", side_effect=RuntimeError("bad url")):
        download.start()

    assert download.state == DownloadState.CANCELLED
    assert str(download.error) == "bad url"


def test_single_download_title_defaults_to_the_url(tmp_path):
    download = SingleFileDownload("https://example.com/files/game.exe?token=1", str(tmp_path / "game.exe"))
    assert download.title == "example.com/files/game.exe"
