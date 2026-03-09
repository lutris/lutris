"""Persistent download progress tracking for resumable downloads.

Stores completed byte ranges on disk so that large GOG downloads can
resume after interruptions — hibernation, crashes, network errors, or
Lutris restarts — without re-downloading already-completed portions.

The progress is stored as a JSON `.progress` file alongside the
download destination. Each file tracks the URL, total file size,
the planned byte ranges, and which ranges have completed. On
successful download completion the progress file is removed.

Writes are atomic (write-to-temp + rename) so that a crash during
a progress update never corrupts the file.
"""

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Tuple

from lutris.util.log import logger


class DownloadProgress:
    """Tracks byte-range download progress persistently on disk.

    Create one instance per download destination. The instance manages
    a `<dest>.progress` sidecar file that records which byte ranges
    have been flushed to disk. Workers call :meth:`mark_range_complete`
    after each range finishes; the orchestrator calls :meth:`cleanup`
    once the full file is verified.

    Thread-safety: :meth:`mark_range_complete` uses a file-level
    atomic-replace strategy. Multiple threads may call it concurrently
    as long as they pass non-overlapping (start, end) pairs, which is
    guaranteed by the range-splitting logic in GOGDownloader.
    """

    PROGRESS_SUFFIX = ".progress"

    def __init__(self, dest_path: str) -> None:
        self.dest_path: str = dest_path
        self.progress_path: str = dest_path + self.PROGRESS_SUFFIX
        self._data: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Factory / lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def progress_path_for(dest_path: str) -> str:
        """Return the progress file path for a given download destination."""
        return dest_path + DownloadProgress.PROGRESS_SUFFIX

    def create(
        self,
        url: str,
        file_size: int,
        ranges: List[Tuple[int, int]],
    ) -> None:
        """Create a fresh progress file for a new download.

        Args:
            url: The download URL (informational; may change between sessions
                 for CDN URLs so is not used for compatibility checks).
            file_size: Total expected file size in bytes.
            ranges: List of ``(start, end)`` inclusive byte-range tuples
                    that will be downloaded in parallel.
        """
        self._data = {
            "url": url,
            "file_size": file_size,
            "total_ranges": [[s, e] for s, e in ranges],
            "completed_ranges": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._save()

    def load(self) -> bool:
        """Load existing progress from disk.

        Returns:
            ``True`` if a valid progress file was found and loaded,
            ``False`` otherwise (missing, corrupt, or incomplete).
        """
        if not os.path.exists(self.progress_path):
            return False
        try:
            with open(self.progress_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            required = ("url", "file_size", "total_ranges", "completed_ranges")
            if not all(k in self._data for k in required):
                logger.warning(
                    "Progress file missing required fields: %s",
                    self.progress_path,
                )
                return False
            return True
        except (OSError, json.JSONDecodeError, ValueError) as ex:
            logger.warning(
                "Failed to load progress file %s: %s",
                self.progress_path,
                ex,
            )
            return False

    # ------------------------------------------------------------------
    # Progress updates
    # ------------------------------------------------------------------

    def mark_range_complete(self, start: int, end: int) -> None:
        """Record a completed byte range and persist to disk.

        This is called by each download worker after it has finished
        writing its assigned range to the destination file.

        Args:
            start: Inclusive start byte offset.
            end: Inclusive end byte offset.
        """
        completed = self._data.get("completed_ranges", [])
        pair = [start, end]
        if pair not in completed:
            completed.append(pair)
            self._data["completed_ranges"] = completed
            self._data["updated_at"] = time.time()
            self._save()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_remaining_ranges(self) -> List[Tuple[int, int]]:
        """Return byte ranges that have not yet been downloaded.

        Returns:
            List of ``(start, end)`` tuples for ranges still pending.
        """
        total = [tuple(r) for r in self._data.get("total_ranges", [])]
        completed = {tuple(r) for r in self._data.get("completed_ranges", [])}
        return [r for r in total if r not in completed]

    def get_completed_size(self) -> int:
        """Return total bytes across all completed ranges."""
        total = 0
        for start, end in self._data.get("completed_ranges", []):
            total += end - start + 1
        return total

    @property
    def url(self) -> str:
        """The URL stored in the progress file (informational)."""
        return self._data.get("url", "")

    @property
    def file_size(self) -> int:
        """Expected total file size in bytes."""
        return self._data.get("file_size", 0)

    @property
    def completed_ranges(self) -> List[Tuple[int, int]]:
        """List of completed ``(start, end)`` range tuples."""
        return [tuple(r) for r in self._data.get("completed_ranges", [])]

    @property
    def total_ranges(self) -> List[Tuple[int, int]]:
        """List of all planned ``(start, end)`` range tuples."""
        return [tuple(r) for r in self._data.get("total_ranges", [])]

    def is_compatible(self, file_size: int) -> bool:
        """Check whether existing progress can be reused for the current download.

        Compatibility is determined solely by file size — CDN URLs
        frequently rotate across sessions, so the URL is not compared.

        Args:
            file_size: The file size reported by the current server probe.

        Returns:
            ``True`` if the progress file's file size matches and is > 0.
        """
        return self.file_size == file_size and file_size > 0

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove the progress file (called on successful completion)."""
        try:
            if os.path.exists(self.progress_path):
                os.remove(self.progress_path)
                logger.debug("Removed download progress file: %s", self.progress_path)
        except OSError as ex:
            logger.warning(
                "Failed to remove progress file %s: %s",
                self.progress_path,
                ex,
            )
        self._data = {}

    # ------------------------------------------------------------------
    # Persistence (atomic writes)
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Atomically write progress data to disk.

        Uses write-to-temp + ``os.replace`` so that a crash mid-write
        never leaves a corrupted progress file.
        """
        try:
            dir_path = os.path.dirname(self.progress_path) or "."
            os.makedirs(dir_path, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".progress.tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                os.replace(tmp_path, self.progress_path)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as ex:
            logger.warning(
                "Failed to save progress file %s: %s",
                self.progress_path,
                ex,
            )
