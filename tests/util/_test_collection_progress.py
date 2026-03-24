"""Tests for DownloadCollectionProgressBox multi-file parallel downloads.

These tests verify the prefetch-one concurrent download model, aggregate
progress, per-file error handling, cancel-all, and edge cases — all
without a running GTK display (GTK widgets are mocked).

The module is loaded via importlib to avoid the normal lutris.gui package
chain that requires a real GTK installation / display.
"""

import importlib
import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ── Load the target module in isolation ──────────────────────────────
#
# We can't ``import lutris.gui.widgets.download_collection_progress_box``
# normally because the package __init__.py files pull in real GTK /
# GObject, which requires a display.  Instead we:
#
#  1. Temporarily inject ``gi`` / ``gi.repository`` stubs into
#     sys.modules (only if they are NOT already loaded — if real gi is
#     present we leave it).
#  2. Load the single .py file via importlib.util.spec_from_file_location
#     under its fully qualified name so that ``patch()`` calls work.
#  3. After loading, remove temporary stubs (but keep the target module
#     and its own ``gi.repository`` references alive — they are already
#     bound in the module's global namespace).

_SRC_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_MOD_NAME = "lutris.gui.widgets.download_collection_progress_box"
_MOD_PATH = os.path.join(_SRC_ROOT, "lutris", "gui", "widgets", "download_collection_progress_box.py")


def _load_module() -> types.ModuleType:
    """Load the target module, stubbing GTK if necessary."""
    # If the module was already loaded (e.g. in a previous test-collection
    # pass), just reuse it.
    if _MOD_NAME in sys.modules:
        return sys.modules[_MOD_NAME]

    # Track what we add so we can clean up only our additions.
    # We use setdefault so we NEVER overwrite a real module — this avoids
    # poisoning sys.modules["gi"] when real GTK is installed.
    added: list[str] = []

    def _ensure(name: str, mod: types.ModuleType) -> None:
        if name not in sys.modules:
            sys.modules[name] = mod
            added.append(name)

    # gi / gi.repository stubs — only if not already present
    _gi = types.ModuleType("gi")
    _gi.require_version = lambda *a, **kw: None  # type: ignore[attr-defined]
    _ensure("gi", _gi)

    _mock_gtk = MagicMock()
    _mock_gtk.Box = type("Box", (), {"__init__": lambda self, **kw: None})
    _mock_gtk.Orientation.VERTICAL = 0

    _mock_gobject = MagicMock()
    _mock_gobject.SignalFlags.RUN_LAST = 1
    _mock_gobject.TYPE_PYOBJECT = object

    _gi_repo = types.ModuleType("gi.repository")
    _gi_repo.Gtk = _mock_gtk  # type: ignore[attr-defined]
    _gi_repo.GLib = MagicMock()  # type: ignore[attr-defined]
    _gi_repo.GObject = _mock_gobject  # type: ignore[attr-defined]
    _gi_repo.Pango = MagicMock()  # type: ignore[attr-defined]
    _ensure("gi.repository", _gi_repo)

    # Ensure parent package stubs so importlib can place our module
    for pkg in ("lutris.gui", "lutris.gui.widgets", "lutris.gui.dialogs"):
        stub = types.ModuleType(pkg)
        stub.__path__ = []  # type: ignore[attr-defined]
        _ensure(pkg, stub)

    # The module imports display_error from lutris.gui.dialogs
    sys.modules["lutris.gui.dialogs"].display_error = MagicMock()  # type: ignore[attr-defined]

    # Load the module
    spec = importlib.util.spec_from_file_location(_MOD_NAME, _MOD_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)

    # Clean up ALL stubs we added — the loaded module's globals already
    # captured their references to Gtk, GObject, etc., so removing the
    # sys.modules entries doesn't break the module.
    for key in added:
        sys.modules.pop(key, None)

    return mod


_mod = _load_module()

MAX_CONCURRENT_FILES = _mod.MAX_CONCURRENT_FILES
DownloadCollectionProgressBox = _mod.DownloadCollectionProgressBox
_ActiveDownload = _mod._ActiveDownload


# ── Helpers ──────────────────────────────────────────────────────────


def _make_file(
    filename="game.bin",
    url="https://cdn.example.com/game.bin",
    dest="/tmp/downloads/game.bin",
    size=1000,
    downloader_class=None,
    referer=None,
):
    """Create a mock InstallerFile."""
    f = MagicMock()
    f.filename = filename
    f.url = url
    f.dest_file = dest
    f.tmp_file = None
    f.referer = referer
    if downloader_class:
        f.downloader_class = downloader_class
    else:
        # Simulate no downloader_class attribute: getattr returns None
        del f.downloader_class
    return f


def _make_collection(files, human_url="Test Collection"):
    """Create a mock InstallerFileCollection."""
    coll = MagicMock()
    coll.files_list = files
    coll.human_url = human_url
    coll.num_files = len(files)
    coll.full_size = sum(getattr(f, "_size", 1000) for f in files)
    return coll


def _make_downloader(state="DOWNLOADING", downloaded_size=0):
    """Create a mock Downloader with state constants."""
    dl = MagicMock()
    dl.DOWNLOADING = "DOWNLOADING"
    dl.COMPLETED = "COMPLETED"
    dl.CANCELLED = "CANCELLED"
    dl.ERROR = "ERROR"
    dl.state = state
    dl.downloaded_size = downloaded_size
    dl.error = None
    dl.dest = "/tmp/test.tmp"
    return dl


# ── Fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def two_files():
    """Two files for typical multi-file test."""
    return [
        _make_file("part1.bin", dest="/tmp/dl/part1.bin"),
        _make_file("part2.bin", dest="/tmp/dl/part2.bin"),
    ]


@pytest.fixture
def three_files():
    """Three files for prefetch boundary test."""
    return [
        _make_file("a.bin", dest="/tmp/dl/a.bin"),
        _make_file("b.bin", dest="/tmp/dl/b.bin"),
        _make_file("c.bin", dest="/tmp/dl/c.bin"),
    ]


# ── Tests: _ActiveDownload ───────────────────────────────────────────


class TestActiveDownload:
    def test_init_sets_fields(self):
        f = _make_file()
        dl = _make_downloader()
        ad = _ActiveDownload(f, dl)
        assert ad.file is f
        assert ad.downloader is dl
        assert ad.num_retries == 0

    def test_retry_count_increments(self):
        ad = _ActiveDownload(_make_file(), _make_downloader())
        ad.num_retries += 1
        assert ad.num_retries == 1


# ── Tests: Initialisation ───────────────────────────────────────────


class TestInit:
    def test_active_downloads_initially_empty(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._active_downloads = []
        assert box._active_downloads == []

    def test_completed_sizes_initially_empty(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._completed_sizes = {}
        assert box._completed_sizes == {}

    def test_max_concurrent_files_is_two(self):
        assert MAX_CONCURRENT_FILES == 2


# ── Tests: _create_downloader ───────────────────────────────────────


class TestCreateDownloader:
    @patch("lutris.gui.widgets.download_collection_progress_box.create_cache_lock")
    @patch("lutris.gui.widgets.download_collection_progress_box.Downloader")
    @patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", return_value=False)
    def test_creates_downloader_with_correct_args(self, mock_exists, MockDL, mock_lock):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        f = _make_file(url="https://cdn.example.com/f.bin", dest="/tmp/dl/f.bin")

        box._create_downloader(f)

        MockDL.assert_called_once_with(
            "https://cdn.example.com/f.bin",
            "/tmp/dl/f.bin.tmp",
            referer=None,
            overwrite=True,
        )
        assert f.tmp_file == "/tmp/dl/f.bin.tmp"

    @patch("lutris.gui.widgets.download_collection_progress_box.create_cache_lock")
    @patch("lutris.gui.widgets.download_collection_progress_box.Downloader")
    @patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", return_value=True)
    @patch("lutris.gui.widgets.download_collection_progress_box.os.remove")
    def test_removes_existing_tmp_file(self, mock_remove, mock_exists, MockDL, mock_lock):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        f = _make_file(dest="/tmp/dl/f.bin")

        box._create_downloader(f)
        mock_remove.assert_called_once_with("/tmp/dl/f.bin.tmp")

    @patch("lutris.gui.widgets.download_collection_progress_box.create_cache_lock")
    @patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", return_value=False)
    def test_uses_custom_downloader_class(self, mock_exists, mock_lock):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        custom_dl_cls = MagicMock()
        f = _make_file(dest="/tmp/dl/f.bin")
        f.downloader_class = custom_dl_cls

        box._create_downloader(f)
        custom_dl_cls.assert_called_once()

    @patch("lutris.gui.widgets.download_collection_progress_box.display_error")
    @patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", return_value=False)
    def test_returns_none_on_runtime_error(self, mock_exists, mock_display):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box.get_toplevel = MagicMock(return_value=None)
        f = _make_file(dest="/tmp/dl/f.bin")
        # Simulate no downloader_class → use default Downloader which will fail
        with patch(
            "lutris.gui.widgets.download_collection_progress_box.Downloader",
            side_effect=RuntimeError("oops"),
        ):
            result = box._create_downloader(f)
        assert result is None
        mock_display.assert_called_once()


# ── Tests: _pop_next_downloadable_file ───────────────────────────────


class TestPopNextDownloadableFile:
    def test_returns_file_when_not_cached(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        f = _make_file(dest="/tmp/dl/notexist.bin")
        box._file_queue = [f]
        box.num_files_downloaded = 0
        box._completed_sizes = {}

        with patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", return_value=False):
            result = box._pop_next_downloadable_file()
        assert result is f

    def test_skips_cached_file(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        cached = _make_file("cached.bin", dest="/tmp/dl/cached.bin")
        fresh = _make_file("fresh.bin", dest="/tmp/dl/fresh.bin")
        box._file_queue = [fresh, cached]  # pop() takes from end
        box.num_files_downloaded = 0
        box._completed_sizes = {}

        def exists_side(path):
            return path == "/tmp/dl/cached.bin"

        with patch("lutris.gui.widgets.download_collection_progress_box.os.path.exists", side_effect=exists_side):
            with patch("lutris.gui.widgets.download_collection_progress_box.os.path.getsize", return_value=500):
                result = box._pop_next_downloadable_file()

        assert result is fresh
        assert box.num_files_downloaded == 1
        assert box._completed_sizes["/tmp/dl/cached.bin"] == 500

    def test_returns_none_when_empty(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._file_queue = []
        box.num_files_downloaded = 0
        box._completed_sizes = {}
        assert box._pop_next_downloadable_file() is None


# ── Tests: Aggregate progress ────────────────────────────────────────


class TestAggregateDownloadedSize:
    def test_sums_completed_and_active(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._completed_sizes = {"/a": 100, "/b": 200}

        dl1 = _make_downloader(downloaded_size=50)
        dl2 = _make_downloader(downloaded_size=75)
        ad1 = _ActiveDownload(_make_file(), dl1)
        ad2 = _ActiveDownload(_make_file(), dl2)
        box._active_downloads = [ad1, ad2]

        assert box._aggregate_downloaded_size() == 100 + 200 + 50 + 75

    def test_empty_state(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._completed_sizes = {}
        box._active_downloads = []
        assert box._aggregate_downloaded_size() == 0


# ── Tests: File labels ───────────────────────────────────────────────


class TestUpdateActiveFileLabels:
    def test_comma_separated_names(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box.file_name_label = MagicMock()

        f1 = _make_file("part1.bin")
        f2 = _make_file("part2.bin")
        box._active_downloads = [
            _ActiveDownload(f1, _make_downloader()),
            _ActiveDownload(f2, _make_downloader()),
        ]

        box._update_active_file_labels()
        box.file_name_label.set_text.assert_called_once_with("part1.bin, part2.bin")

    def test_single_name(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box.file_name_label = MagicMock()

        f = _make_file("only.bin")
        box._active_downloads = [_ActiveDownload(f, _make_downloader())]

        box._update_active_file_labels()
        box.file_name_label.set_text.assert_called_once_with("only.bin")

    def test_empty_when_no_active(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box.file_name_label = MagicMock()
        box._active_downloads = []

        box._update_active_file_labels()
        box.file_name_label.set_text.assert_called_once_with("")


# ── Tests: Start / prefetch ──────────────────────────────────────────


class TestStartPrefetch:
    def test_start_launches_two_downloads(self, three_files):
        """start() should launch primary + prefetch = 2 concurrent downloads."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._file_queue = three_files.copy()
        box.downloader = None
        box.is_complete = False
        box.num_files_downloaded = 0
        box._active_downloads = []
        box._completed_sizes = {}
        box.cancel_button = MagicMock()
        box.file_name_label = MagicMock()
        box.emit = MagicMock()

        mock_dl = _make_downloader()
        with patch.object(box, "_create_downloader", return_value=mock_dl):
            with patch("lutris.gui.widgets.download_collection_progress_box.schedule_repeating_at_idle"):
                box.start()

        assert len(box._active_downloads) == 2
        # One file left in queue
        assert len(box._file_queue) == 1

    def test_start_emits_complete_when_no_files(self):
        """start() with empty queue should emit complete."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._file_queue = []
        box.downloader = None
        box.is_complete = False
        box._active_downloads = []
        box._completed_sizes = {}
        box.cancel_button = MagicMock()
        box.emit = MagicMock()

        with patch.object(box, "_pop_next_downloadable_file", return_value=None):
            box.start()

        box.emit.assert_called_once_with("complete", {})
        assert box.is_complete is True

    def test_prefetch_respects_max_concurrent(self):
        """_start_prefetch() should not exceed MAX_CONCURRENT_FILES."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._file_queue = [_make_file(), _make_file()]
        box._active_downloads = [
            _ActiveDownload(_make_file(), _make_downloader()),
            _ActiveDownload(_make_file(), _make_downloader()),
        ]
        box.file_name_label = MagicMock()

        box._start_prefetch()
        # Should NOT have added more
        assert len(box._active_downloads) == 2

    def test_prefetch_starts_when_room(self):
        """_start_prefetch() launches download when under limit."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        f = _make_file(dest="/tmp/dl/next.bin")
        box._file_queue = [f]
        box._active_downloads = [_ActiveDownload(_make_file(), _make_downloader())]
        box.file_name_label = MagicMock()
        box.num_files_downloaded = 0
        box._completed_sizes = {}

        mock_dl = _make_downloader()
        with patch.object(box, "_create_downloader", return_value=mock_dl):
            with patch(
                "lutris.gui.widgets.download_collection_progress_box.os.path.exists",
                return_value=False,
            ):
                box._start_prefetch()

        assert len(box._active_downloads) == 2


# ── Tests: Progress callback ─────────────────────────────────────────


class TestProgress:
    def _setup_box(self):
        """Create a box ready for _progress() calls."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._active_downloads = []
        box._completed_sizes = {}
        box._file_queue = []
        box.full_size = 2000
        box.num_files_downloaded = 0
        box.is_complete = False
        box.downloader = None
        box.progressbar = MagicMock()
        box.progress_label = MagicMock()
        box.cancel_button = MagicMock()
        box.file_name_label = MagicMock()
        box.emit = MagicMock()
        box.time_left = "00:00:00"
        box.time_left_check_time = 0
        box.last_size = 0
        box.avg_speed = 0
        box.speed_list = []
        return box

    def test_returns_false_when_no_active(self):
        box = self._setup_box()
        assert box._progress() is False

    def test_returns_true_when_downloading(self):
        box = self._setup_box()
        dl = _make_downloader(state="DOWNLOADING", downloaded_size=500)
        ad = _ActiveDownload(_make_file(), dl)
        box._active_downloads = [ad]
        box._file_queue = [_make_file()]  # still more to do

        result = box._progress()
        assert result is True

    def test_completed_file_moves_to_completed_sizes(self):
        box = self._setup_box()
        dl = _make_downloader(state="COMPLETED", downloaded_size=1000)
        f = _make_file(dest="/tmp/dl/done.bin")
        f.tmp_file = "/tmp/dl/done.bin.tmp"
        ad = _ActiveDownload(f, dl)
        box._active_downloads = [ad]

        with patch("lutris.gui.widgets.download_collection_progress_box.os.rename") as mock_rename:
            with patch("lutris.gui.widgets.download_collection_progress_box.update_cache_lock"):
                box._progress()

        assert box._completed_sizes["/tmp/dl/done.bin"] == 1000
        assert box.num_files_downloaded == 1
        mock_rename.assert_called_once_with("/tmp/dl/done.bin.tmp", "/tmp/dl/done.bin")

    def test_completion_triggers_prefetch(self):
        box = self._setup_box()
        dl = _make_downloader(state="COMPLETED", downloaded_size=500)
        f = _make_file(dest="/tmp/dl/done.bin")
        f.tmp_file = "/tmp/dl/done.bin.tmp"
        ad = _ActiveDownload(f, dl)
        box._active_downloads = [ad]
        box._file_queue = [_make_file()]  # one more in queue

        with patch("lutris.gui.widgets.download_collection_progress_box.os.rename"):
            with patch("lutris.gui.widgets.download_collection_progress_box.update_cache_lock"):
                with patch.object(box, "_start_prefetch") as mock_prefetch:
                    box._progress()

        mock_prefetch.assert_called_once()

    def test_all_done_emits_complete(self):
        box = self._setup_box()
        dl = _make_downloader(state="COMPLETED", downloaded_size=1000)
        f = _make_file(dest="/tmp/dl/last.bin")
        f.tmp_file = "/tmp/dl/last.bin.tmp"
        ad = _ActiveDownload(f, dl)
        box._active_downloads = [ad]
        box._file_queue = []  # nothing left

        with patch("lutris.gui.widgets.download_collection_progress_box.os.rename"):
            with patch("lutris.gui.widgets.download_collection_progress_box.update_cache_lock"):
                result = box._progress()

        assert result is False
        box.emit.assert_called_with("complete", {})
        assert box.is_complete is True

    def test_cancelled_state_cancels_all(self):
        box = self._setup_box()
        dl1 = _make_downloader(state="CANCELLED")
        dl2 = _make_downloader(state="DOWNLOADING")
        box._active_downloads = [
            _ActiveDownload(_make_file(), dl1),
            _ActiveDownload(_make_file(), dl2),
        ]

        result = box._progress()
        assert result is False
        # Should cancel remaining downloads
        dl2.cancel.assert_called()

    def test_error_retries_independently(self):
        box = self._setup_box()
        dl = _make_downloader(state="ERROR")
        dl.error = RuntimeError("network failure")
        f = _make_file(dest="/tmp/dl/fail.bin")
        ad = _ActiveDownload(f, dl)
        ad.num_retries = 0
        box._active_downloads = [ad]
        box._file_queue = [_make_file()]  # keep loop going

        new_dl = _make_downloader(state="DOWNLOADING")
        with patch.object(box, "_create_downloader", return_value=new_dl):
            box._progress()

        assert ad.num_retries == 1
        assert ad.downloader is new_dl
        new_dl.start.assert_called_once()

    def test_error_exhausts_retries_emits_error(self):
        box = self._setup_box()
        dl = _make_downloader(state="ERROR")
        dl.error = RuntimeError("permanent failure")
        f = _make_file(dest="/tmp/dl/fail.bin")
        ad = _ActiveDownload(f, dl)
        ad.num_retries = 3  # equals max_retries
        box._active_downloads = [ad]

        result = box._progress()
        assert result is False
        box.emit.assert_called_with("error", dl.error)


# ── Tests: Cancel ────────────────────────────────────────────────────


class TestCancel:
    def test_cancel_stops_all_active(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        dl1 = _make_downloader()
        dl2 = _make_downloader()
        box._active_downloads = [
            _ActiveDownload(_make_file(), dl1),
            _ActiveDownload(_make_file(), dl2),
        ]
        box.downloader = MagicMock()
        box.cancel_button = MagicMock()
        box.emit = MagicMock()

        box.on_cancel_clicked()

        dl1.cancel.assert_called_once()
        dl2.cancel.assert_called_once()
        assert box._active_downloads == []
        assert box.downloader is None
        box.emit.assert_called_once_with("cancel")

    def test_cancel_all_internal(self):
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        dl = _make_downloader()
        box._active_downloads = [_ActiveDownload(_make_file(), dl)]
        box.cancel_button = MagicMock()
        box.downloader = MagicMock()

        box._cancel_all()

        dl.cancel.assert_called_once()
        assert box._active_downloads == []
        assert box.downloader is None


# ── Tests: Edge cases ────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_file_collection(self):
        """A single-file collection should work normally without prefetch."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        f = _make_file(dest="/tmp/dl/only.bin")
        box._file_queue = [f]
        box.downloader = None
        box.is_complete = False
        box.num_files_downloaded = 0
        box._active_downloads = []
        box._completed_sizes = {}
        box.cancel_button = MagicMock()
        box.file_name_label = MagicMock()
        box.emit = MagicMock()

        mock_dl = _make_downloader()
        with patch.object(box, "_create_downloader", return_value=mock_dl):
            with patch(
                "lutris.gui.widgets.download_collection_progress_box.os.path.exists",
                return_value=False,
            ):
                with patch("lutris.gui.widgets.download_collection_progress_box.schedule_repeating_at_idle"):
                    box.start()

        # Only 1 active (no prefetch since queue is empty)
        assert len(box._active_downloads) == 1

    def test_all_cached_emits_complete(self):
        """When all files exist in cache, should immediately complete."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box.downloader = None
        box.is_complete = False
        box.num_files_downloaded = 0
        box._active_downloads = []
        box._completed_sizes = {}
        box.cancel_button = MagicMock()
        box.file_name_label = MagicMock()
        box.emit = MagicMock()

        f1 = _make_file(dest="/tmp/dl/cached1.bin")
        f2 = _make_file(dest="/tmp/dl/cached2.bin")
        box._file_queue = [f1, f2]

        with patch(
            "lutris.gui.widgets.download_collection_progress_box.os.path.exists",
            return_value=True,
        ):
            with patch(
                "lutris.gui.widgets.download_collection_progress_box.os.path.getsize",
                return_value=500,
            ):
                box.start()

        box.emit.assert_called_with("complete", {})
        assert box.is_complete is True
        assert box.num_files_downloaded == 2

    def test_retry_button_clears_active_downloads(self):
        """on_retry_clicked should clear active downloads and restart."""
        box = DownloadCollectionProgressBox.__new__(DownloadCollectionProgressBox)
        box._active_downloads = [
            _ActiveDownload(_make_file(), _make_downloader()),
        ]
        box.downloader = _make_downloader()
        box.cancel_cb_id = 123
        box.cancel_button = MagicMock()
        box._file_queue = [_make_file()]
        box.is_complete = False
        box.num_files_downloaded = 0
        box._completed_sizes = {}
        box.file_name_label = MagicMock()
        box.emit = MagicMock()

        mock_dl = _make_downloader()
        button = MagicMock()
        button.connect = MagicMock(return_value=456)

        with patch.object(box, "_create_downloader", return_value=mock_dl):
            with patch(
                "lutris.gui.widgets.download_collection_progress_box.os.path.exists",
                return_value=False,
            ):
                with patch("lutris.gui.widgets.download_collection_progress_box.schedule_repeating_at_idle"):
                    box.on_retry_clicked(button)

        # Active downloads should have been cleared before restart
        assert len(box._active_downloads) >= 1  # re-populated by start()
