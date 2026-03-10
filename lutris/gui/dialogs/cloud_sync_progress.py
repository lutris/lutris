"""Cloud sync progress adapter for the sidebar DownloadQueue.

Provides a thread-safe bridge between the GOG cloud sync's
progress_callback(current, total, filename) and the ProgressInfo
polling used by ProgressBox in the sidebar download queue.
"""

import threading
from gettext import gettext as _
from typing import TYPE_CHECKING, Callable, List, Optional

from lutris.gui.widgets.progress_box import ProgressInfo
from lutris.services.gog_cloud import SyncResult
from lutris.util.log import logger
from lutris.util.strings import gtk_safe

if TYPE_CHECKING:
    from lutris.game import Game


class CloudSyncCancelled(Exception):
    """Raised when the user skips/cancels cloud sync via the stop button."""


class CloudSyncProgressAdapter:
    """Thread-safe adapter that bridges GOG cloud sync progress to ProgressBox polling.

    The sync worker thread calls ``progress_callback(current, total, filename)``
    to update shared state.  The main thread polls ``get_progress()`` which
    returns a ``ProgressInfo`` for the sidebar ``ProgressBox``.

    The stop button in the ProgressBox triggers cancellation: the next
    progress_callback call on the worker thread raises ``CloudSyncCancelled``
    to abort the sync cleanly.

    Usage::

        adapter = CloudSyncProgressAdapter(game, sync_func, "pre-launch")
        download_queue.start(
            operation=adapter.run,
            progress_function=adapter.get_progress,
            completion_function=on_done,
        )
    """

    def __init__(
        self,
        game: "Game",
        sync_func: Callable[["Game", Optional[Callable[[int, int, str], None]]], List[SyncResult]],
        direction: str = "pre-launch",
    ) -> None:
        self.game = game
        self._sync_func = sync_func
        self._direction = direction
        self.results: List[SyncResult] = []

        self._lock = threading.Lock()
        self._current = 0
        self._total = 0
        self._filename = ""
        self._finished = False
        self._cancelled = False
        self._error: Optional[str] = None

        if direction == "pre-launch":
            self._label = _("Syncing cloud saves for %s") % gtk_safe(game.name)
        else:
            self._label = _("Uploading cloud saves for %s") % gtk_safe(game.name)

    def cancel(self) -> None:
        """Called from the main thread when the user clicks the stop button."""
        with self._lock:
            self._cancelled = True
        if self._direction == "pre-launch":
            self.game.skip_cloud_sync = True
        logger.info("User skipped cloud sync (%s) for %s", self._direction, self.game.name)

    def progress_callback(self, current: int, total: int, filename: str) -> None:
        """Called from the worker thread to report progress.

        Raises CloudSyncCancelled if the user has clicked the stop button.
        """
        with self._lock:
            if self._cancelled:
                raise CloudSyncCancelled()
            self._current = current
            self._total = total
            self._filename = filename

    def get_progress(self) -> ProgressInfo:
        """Polled from the main thread by ProgressBox."""
        with self._lock:
            if self._finished:
                if self._error:
                    return ProgressInfo.ended(_("Cloud sync failed: %s") % self._error)
                return ProgressInfo.ended(self._label)

            if self._total > 0:
                fraction = (self._current + 1) / self._total
                label = "%s (%s)" % (self._label, self._filename)
            else:
                fraction = 0.0
                label = self._label

            stop_fn = self.cancel if not self._cancelled else None

        return ProgressInfo(fraction, label, stop_fn)

    def run(self) -> List[SyncResult]:
        """Run on a worker thread — performs the actual sync."""
        try:
            self.results = self._sync_func(self.game, self.progress_callback)
            return self.results
        except CloudSyncCancelled:
            logger.info("Cloud sync (%s) cancelled for %s", self._direction, self.game.name)
            return self.results
        except Exception as ex:
            logger.warning("GOG cloud sync (%s) failed: %s", self._direction, ex)
            with self._lock:
                self._error = str(ex)
            raise
        finally:
            with self._lock:
                self._finished = True
