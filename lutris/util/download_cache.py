"""Download cache protection module.

Provides mechanisms to protect downloaded installer files from being
deleted before installation completes. This is critical for large game
downloads (e.g., 40GB+ GOG games) where re-downloading after a failed
installation is extremely time-consuming.

The module introduces a "cache lock" system:
- When a download starts, a lock file is created alongside the download
- The lock tracks download state (downloading, completed, installed)
- Cleanup routines check the lock before deleting cached files
- Failed installations preserve cached files for retry
"""

import json
import os
import time
from enum import Enum
from typing import Optional

from lutris.util.log import logger


class CacheState(Enum):
    """State of a cached download file."""

    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"  # Download complete, not yet installed
    INSTALLING = "installing"  # Installation in progress
    INSTALLED = "installed"  # Installation successful, safe to clean
    FAILED = "failed"  # Installation failed, preserve for retry


def _lock_path(file_path: str) -> str:
    """Return the path to the lock file for a cached download."""
    return file_path + ".cache_lock"


def create_cache_lock(file_path: str, state: CacheState = CacheState.DOWNLOADING) -> None:
    """Create a cache lock file to protect a download from premature deletion.

    Args:
        file_path: Path to the downloaded file being protected.
        state: Initial state of the cached file.
    """
    lock_file = _lock_path(file_path)
    lock_data = {
        "state": state.value,
        "created_at": time.time(),
        "updated_at": time.time(),
        "file_path": file_path,
    }
    try:
        lock_dir = os.path.dirname(lock_file)
        os.makedirs(lock_dir, exist_ok=True)
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
    except OSError as ex:
        logger.warning("Failed to create cache lock for %s: %s", file_path, ex)


def update_cache_lock(file_path: str, state: CacheState) -> None:
    """Update the state of an existing cache lock.

    Args:
        file_path: Path to the downloaded file.
        state: New state to set.
    """
    lock_file = _lock_path(file_path)
    try:
        lock_data = {}
        if os.path.exists(lock_file):
            with open(lock_file, "r", encoding="utf-8") as f:
                lock_data = json.load(f)
        lock_data["state"] = state.value
        lock_data["updated_at"] = time.time()
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
    except (OSError, json.JSONDecodeError) as ex:
        logger.warning("Failed to update cache lock for %s: %s", file_path, ex)


def get_cache_state(file_path: str) -> Optional[CacheState]:
    """Read the current state from a cache lock file.

    Args:
        file_path: Path to the downloaded file.

    Returns:
        The CacheState if a lock exists, None otherwise.
    """
    lock_file = _lock_path(file_path)
    if not os.path.exists(lock_file):
        return None
    try:
        with open(lock_file, "r", encoding="utf-8") as f:
            lock_data = json.load(f)
        return CacheState(lock_data.get("state", "downloading"))
    except (OSError, json.JSONDecodeError, ValueError) as ex:
        logger.warning("Failed to read cache lock for %s: %s", file_path, ex)
        return None


def remove_cache_lock(file_path: str) -> None:
    """Remove the cache lock file for a download.

    Args:
        file_path: Path to the downloaded file.
    """
    lock_file = _lock_path(file_path)
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except OSError as ex:
        logger.warning("Failed to remove cache lock for %s: %s", file_path, ex)


def is_safe_to_delete(file_path: str) -> bool:
    """Check if a cached file is safe to delete.

    A file is safe to delete if:
    - No cache lock exists (legacy behavior, always safe)
    - The cache lock state is INSTALLED (installation succeeded)
    - The cache lock is older than 7 days and in FAILED state (stale)

    A file is NOT safe to delete if:
    - State is DOWNLOADING (download in progress)
    - State is DOWNLOADED (download complete, waiting for install)
    - State is INSTALLING (installation in progress)
    - State is FAILED and less than 7 days old (preserve for retry)

    Args:
        file_path: Path to the cached file.

    Returns:
        True if the file can be safely deleted, False otherwise.
    """
    state = get_cache_state(file_path)

    # No lock = legacy behavior, allow deletion
    if state is None:
        return True

    # Installation succeeded, safe to clean up
    if state == CacheState.INSTALLED:
        return True

    # Active states - never delete
    if state in (CacheState.DOWNLOADING, CacheState.DOWNLOADING, CacheState.INSTALLING):
        logger.info(
            "Cache protection: preserving %s (state: %s)",
            os.path.basename(file_path),
            state.value,
        )
        return False

    # Downloaded but not yet installed - preserve
    if state == CacheState.DOWNLOADED:
        logger.info(
            "Cache protection: preserving downloaded file %s for installation",
            os.path.basename(file_path),
        )
        return False

    # Failed installation - preserve for 7 days for retry
    if state == CacheState.FAILED:
        lock_file = _lock_path(file_path)
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                lock_data = json.load(f)
            updated_at = lock_data.get("updated_at", 0)
            days_old = (time.time() - updated_at) / 86400
            if days_old < 7:
                logger.info(
                    "Cache protection: preserving failed install file %s (%.1f days old, expires in %.1f days)",
                    os.path.basename(file_path),
                    days_old,
                    7 - days_old,
                )
                return False
            logger.info(
                "Cache protection: allowing cleanup of stale failed file %s (%.1f days old)",
                os.path.basename(file_path),
                days_old,
            )
        except (OSError, json.JSONDecodeError):
            pass
        return True

    # Unknown state - allow deletion
    return True


def safe_delete_folder(folder_path: str) -> bool:
    """Delete a folder, but only remove files that are safe to delete.

    This is a drop-in replacement for system.delete_folder() that
    respects cache locks. Files with active cache locks are preserved.

    Args:
        folder_path: Path to the folder to clean up.

    Returns:
        True if the folder was fully cleaned (all files removed),
        False if some files were preserved due to cache locks.
    """
    if not os.path.isdir(folder_path):
        return True

    preserved_files = []

    for root, dirs, files in os.walk(folder_path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)

            # Skip lock files themselves - they'll be cleaned with their data files
            if file_path.endswith(".cache_lock"):
                continue

            if is_safe_to_delete(file_path):
                try:
                    os.remove(file_path)
                    remove_cache_lock(file_path)
                except OSError as ex:
                    logger.warning("Failed to remove %s: %s", file_path, ex)
            else:
                preserved_files.append(file_path)

        # Only remove directories if they're empty
        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except OSError:
                pass  # Directory not empty, skip

    if preserved_files:
        logger.info(
            "Cache protection: preserved %d file(s) in %s for retry",
            len(preserved_files),
            folder_path,
        )
        return False

    # If all files were removed, remove the folder itself
    try:
        if os.path.isdir(folder_path) and not os.listdir(folder_path):
            os.rmdir(folder_path)
    except OSError:
        pass

    return True
