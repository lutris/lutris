"""GOG Cloud Save hooks for game lifecycle integration.

Provides functions to synchronize cloud saves before game launch
(download from cloud) and after game quit (upload to cloud).

These hooks check if the game is a GOG game, resolve cloud save
locations from the remote config API, and trigger synchronization.
When a conflict is detected the user is prompted via a GTK dialog.
"""

import os
from typing import TYPE_CHECKING, Any, List, Optional

from lutris.services.gog_cloud import (
    GOGCloudSync,
    SyncAction,
    SyncResult,
    get_cloud_save_locations,
    get_game_client_credentials,
    get_game_scoped_token,
    resolve_save_path,
)
from lutris.util.log import logger

if TYPE_CHECKING:
    from lutris.game import Game


def _get_gog_service() -> Optional[Any]:
    """Return an authenticated GOGService instance, or None if unavailable."""
    try:
        from lutris.services.gog import GOGService  # noqa: PLC0415

        service = GOGService()
        if service.is_authenticated():
            logger.info("GOG service authenticated successfully")
            return service
        logger.warning("GOG service not authenticated")
    except Exception as ex:
        logger.error("Could not create GOG service: %s", ex)
    return None


def _get_game_runner_info(game: "Game") -> dict:
    """Extract runner-related info needed for cloud save resolution.

    Returns a dict with keys:
        - is_native: True if the game runs natively on Linux.
        - platform: 'linux' or 'windows' (lowercase for GOG APIs).
        - wine_prefix: Wine prefix path, or None.
        - wine_user: Wine user name, or None.
        - install_path: Game install directory.
    """
    runner_name = getattr(game, "runner_name", "") or ""
    is_native = runner_name == "linux"
    # Use lowercase platform names for GOG APIs (builds API expects lowercase)
    platform = "linux" if is_native else "windows"

    wine_prefix = None
    wine_user = None

    if not is_native and hasattr(game, "runner") and game.runner:
        wine_prefix = getattr(game.runner, "prefix_path", None)
        # Wine user defaults to the OS user
        if wine_prefix:
            wine_user = os.environ.get("USER")

    install_path = getattr(game, "directory", "") or ""

    return {
        "is_native": is_native,
        "platform": platform,
        "wine_prefix": wine_prefix,
        "wine_user": wine_user,
        "install_path": install_path,
    }


def _resolve_save_locations(
    game: "Game",
    service: Any,
) -> List[dict]:
    """Resolve all cloud save locations for a GOG game.

    Returns a list of dicts with 'name' and 'save_path' keys.
    """
    logger.info("Resolving save locations for game %s (appid=%s)", game.name, game.appid)
    try:
        token = service.load_token()
        logger.info("GOG token loaded successfully")
    except Exception as ex:
        logger.error("Failed to load GOG token for cloud sync: %s", ex)
        return []

    # Get game client credentials (clientId, clientSecret from build manifest)
    try:
        logger.info("Fetching game client credentials...")
        client_id, client_secret = get_game_client_credentials(token, game.appid)
        logger.info("Got client credentials: clientId=%s", client_id[:16] + "...")
    except Exception as ex:
        logger.warning("Could not get game client credentials for %s: %s", game.appid, ex)
        return []

    # Get game-scoped token
    try:
        logger.info("Getting game-scoped token...")
        game_token = get_game_scoped_token(token["refresh_token"], client_id, client_secret)
        access_token = game_token.get("access_token", "")
        logger.info("Got game-scoped token")
    except Exception as ex:
        logger.warning("Could not get game-scoped token for %s: %s", game.appid, ex)
        return []

    if not access_token:
        logger.warning("Empty access token received")
        return []

    # Get cloud save locations from remote config
    info = _get_game_runner_info(game)
    platform = info["platform"]
    logger.info("Fetching cloud save locations for platform=%s", platform)
    locations = get_cloud_save_locations(access_token, client_id, platform)
    if not locations:
        logger.info("No cloud save locations configured for game %s", game.appid)
        return []

    logger.info("Found %d cloud save location(s)", len(locations))
    # Resolve each location to a filesystem path
    result = []
    for loc in locations:
        save_path = resolve_save_path(
            loc,
            info["install_path"],
            info["is_native"],
            info["wine_prefix"],
            info["wine_user"],
        )
        if save_path:
            logger.info("Resolved location '%s' to path: %s", loc.name, save_path)
            result.append({"name": loc.name, "save_path": save_path, "platform": platform})

    return result


def _show_conflict_dialog(game_name: str, location_name: str) -> Optional[str]:
    """Show a GTK conflict resolution dialog and return the user's choice.

    Returns:
        ``"download"``, ``"upload"``, or ``None`` (skip).
    """
    try:
        from lutris.gui.dialogs.cloud_sync import CloudSyncConflictDialog  # noqa: PLC0415

        dialog = CloudSyncConflictDialog(game_name, location_name)
        return dialog.action
    except Exception as ex:
        logger.debug("Could not show conflict dialog: %s", ex)
        return None


def _sync_location(
    sync: GOGCloudSync,
    game: "Game",
    loc: dict,
    preferred_action: str,
    direction_label: str,
) -> SyncResult:
    """Sync a single save location, handling conflicts via dialog."""
    result = sync.sync_saves(
        game.appid,
        loc["save_path"],
        loc["name"],
        loc["platform"],
        preferred_action=preferred_action,
    )

    if result.action == SyncAction.CONFLICT:
        logger.info("Cloud save conflict for %s (%s)", loc["name"], direction_label)
        user_choice = _show_conflict_dialog(game.name, loc["name"])
        if user_choice:
            logger.info("User chose '%s' for conflict on %s", user_choice, loc["name"])
            # Convert "upload"/"download" to "forceupload"/"forcedownload" for conflict resolution
            force_action = f"force{user_choice}"
            result = sync.sync_saves(
                game.appid,
                loc["save_path"],
                loc["name"],
                loc["platform"],
                preferred_action=force_action,
            )
        else:
            logger.info("User skipped sync for %s", loc["name"])

    # Log the final outcome
    if result.error:
        logger.error("Cloud sync error for %s: %s", loc["name"], result.error)
    elif result.action == SyncAction.DOWNLOAD:
        logger.info("Downloaded %d cloud saves for %s", len(result.downloaded), loc["name"])
    elif result.action == SyncAction.UPLOAD:
        logger.info("Uploaded %d saves for %s", len(result.uploaded), loc["name"])
    elif result.action == SyncAction.NONE:
        logger.debug("Saves up to date for %s", loc["name"])

    return result


def sync_before_launch(game: "Game") -> List[SyncResult]:
    """Sync cloud saves before launching a GOG game (download direction).

    This fetches any newer saves from GOG cloud storage to the local
    filesystem before the game starts.  If a conflict is detected,
    a dialog is shown so the user can choose which version to keep.

    Args:
        game: The Game instance about to be launched.

    Returns:
        A list of SyncResult objects (one per save location).
        Returns an empty list if the game is not a GOG game or sync
        is not available.
    """
    if getattr(game, "service", None) != "gog" or not getattr(game, "appid", None):
        return []

    logger.info("GOG cloud sync: checking saves before launch for %s", game.name)

    service = _get_gog_service()
    if not service:
        logger.warning("GOG service not available for cloud sync")
        return []

    save_locations = _resolve_save_locations(game, service)
    if not save_locations:
        logger.info("No save locations found, skipping sync")
        return []

    logger.info("Starting sync for %d location(s)", len(save_locations))
    sync = GOGCloudSync(service)
    results = []

    for loc in save_locations:
        logger.info("Cloud sync (pre-launch): %s -> %s", loc["name"], loc["save_path"])
        result = _sync_location(sync, game, loc, "download", "pre-launch")
        results.append(result)

    return results


def sync_after_quit(game: "Game") -> List[SyncResult]:
    """Sync cloud saves after a GOG game quits (upload direction).

    This uploads any newer local saves to GOG cloud storage after
    the game has exited.  If a conflict is detected, a dialog is
    shown so the user can choose which version to keep.

    Args:
        game: The Game instance that just quit.

    Returns:
        A list of SyncResult objects (one per save location).
        Returns an empty list if the game is not a GOG game or sync
        is not available.
    """
    if getattr(game, "service", None) != "gog" or not getattr(game, "appid", None):
        return []

    logger.info("GOG cloud sync: checking saves after quit for %s", game.name)

    service = _get_gog_service()
    if not service:
        logger.warning("GOG service not available for cloud sync")
        return []

    save_locations = _resolve_save_locations(game, service)
    if not save_locations:
        logger.info("No save locations found, skipping sync")
        return []

    logger.info("Starting sync for %d location(s)", len(save_locations))
    sync = GOGCloudSync(service)
    results = []

    for loc in save_locations:
        logger.info("Cloud sync (post-exit): %s -> %s", loc["name"], loc["save_path"])
        result = _sync_location(sync, game, loc, "upload", "post-exit")
        results.append(result)

    return results
