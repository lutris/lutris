"""Run GOG cloud save syncs around a game's sessions, and publish their progress.

A GOG game syncs its saves down from the cloud before it launches and up after it
quits (lutris.services.gog_cloud_hooks does the syncing). start_cloud_sync() runs
one of those on a worker thread as a CloudSyncOperation, and announces it with
CLOUD_SYNC_STARTED and CLOUD_SYNC_ENDED, so that a frontend can display its
progress (get_progress()) and let the user skip it (cancel()).
"""

import threading
from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING, Any, Literal

from lutris.services.gog_cloud import SyncResult
from lutris.services.gog_cloud_hooks import ConflictResolver, sync_after_quit, sync_before_launch
from lutris.util.jobs import AsyncCall
from lutris.util.log import logger
from lutris.util.notifications import NotificationSource
from lutris.util.progress_info import ProgressInfo
from lutris.util.strings import gtk_safe

if TYPE_CHECKING:
    from lutris.game import Game

# Fired with the CloudSyncOperation when its sync starts, and when it ends however it ends
CLOUD_SYNC_STARTED = NotificationSource()
CLOUD_SYNC_ENDED = NotificationSource()

SyncDirection = Literal["pre-launch", "post-exit"]
ProgressCallback = Callable[[int, int, str], None]
SyncFunction = Callable[["Game", ProgressCallback | None, ConflictResolver | None], list[SyncResult]]

# The operations started and not yet ended, by game id and direction
_operations: dict[tuple[str, SyncDirection], "CloudSyncOperation"] = {}


class CloudSyncCancelled(Exception):
    """Raised when the user skips/cancels cloud sync via the stop button."""


class CloudSyncOperation:
    """One cloud sync of a game's saves, with its progress.

    The sync worker thread calls ``progress_callback(current, total, filename)``
    to update shared state.  The main thread polls ``get_progress()`` which
    returns a ``ProgressInfo``.

    Calling cancel() (the progress' stop function) skips the rest of the sync: the
    next progress_callback call on the worker thread raises ``CloudSyncCancelled``
    to abort the sync cleanly.
    """

    def __init__(
        self,
        game: "Game",
        sync_func: SyncFunction,
        direction: SyncDirection = "pre-launch",
        resolve_conflict: ConflictResolver | None = None,
    ) -> None:
        self.game = game
        self.direction = direction
        self._sync_func = sync_func
        self._resolve_conflict = resolve_conflict
        self.results: list[SyncResult] = []

        self._lock = threading.Lock()
        self._current = 0
        self._total = 0
        self._filename = ""
        self._finished = False
        self._cancelled = False
        self._error: str | None = None

        if direction == "pre-launch":
            self._label = _("Syncing cloud saves for %s") % gtk_safe(game.name)
        else:
            self._label = _("Uploading cloud saves for %s") % gtk_safe(game.name)

    def cancel(self) -> None:
        """Called from the main thread when the user clicks the stop button."""
        with self._lock:
            self._cancelled = True
        if self.direction == "pre-launch":
            self.game.skip_cloud_sync = True
        logger.info("User skipped cloud sync (%s) for %s", self.direction, self.game.name)

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
        """Polled from the main thread to display the progress."""
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

    def run(self) -> list[SyncResult]:
        """Run on a worker thread — performs the actual sync."""
        try:
            self.results = self._sync_func(self.game, self.progress_callback, self._resolve_conflict)
            return self.results
        except CloudSyncCancelled:
            logger.info("Cloud sync (%s) cancelled for %s", self.direction, self.game.name)
            return self.results
        except Exception as ex:
            logger.warning("GOG cloud sync (%s) failed: %s", self.direction, ex)
            with self._lock:
                self._error = str(ex)
            raise
        finally:
            with self._lock:
                self._finished = True


def is_cloud_sync_running() -> bool:
    """True if any cloud sync has started, or is waiting to start, and hasn't ended."""
    return bool(_operations)


def start_cloud_sync(
    game: "Game",
    direction: SyncDirection,
    resolve_conflict: ConflictResolver | None = None,
    on_done: Callable[[], None] | None = None,
) -> bool:
    """Sync a game's saves with the cloud on a worker thread: down from it before the game
    launches ("pre-launch"), or up to it after the game quits ("post-exit").

    A pre-launch sync waits for the game's post-exit sync to end, if one is running, so
    that it gets the saves just uploaded. on_done is called on the main loop once the sync
    ends, whether it succeeded, failed or was cancelled. If the same sync is running for
    the game already, this starts nothing and returns False; otherwise, True.
    """
    key = (game.id, direction)
    if key in _operations:
        logger.warning("Cloud sync (%s) for %s is running already", direction, game.name)
        return False

    sync_func = sync_before_launch if direction == "pre-launch" else sync_after_quit
    operation = CloudSyncOperation(game, sync_func, direction, resolve_conflict)
    blocker = _operations.get((game.id, "post-exit")) if direction == "pre-launch" else None
    _operations[key] = operation

    def on_finished(_result: Any, _error: BaseException | None) -> None:
        # The operation logged any error already
        del _operations[key]
        CLOUD_SYNC_ENDED.fire(operation)
        if on_done:
            on_done()

    def begin() -> None:
        CLOUD_SYNC_STARTED.fire(operation)
        AsyncCall(operation.run, on_finished)

    if blocker:

        def on_sync_ended(ended: CloudSyncOperation) -> None:
            if ended is blocker:
                registration.unregister()
                begin()

        registration = CLOUD_SYNC_ENDED.register(on_sync_ended)
    else:
        begin()
    return True
