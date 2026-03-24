"""Scanner for games installed via Playtron GameOS"""

import json
import os
from typing import Dict, List, Optional, Tuple

from lutris import settings
from lutris.api import get_api_games
from lutris.config import write_game_config
from lutris.database import sql
from lutris.database.games import add_or_update, get_game_by_field, get_games
from lutris.services.lutris import download_lutris_media
from lutris.util.log import logger
from lutris.util.strings import slugify

# Playtron stores game metadata in this file
PLAYTRON_INFO_FILE = "playtron_info_v3.json"

# Default Playtron paths relative to install root
DEFAULT_APPS_DIR = "playtron/apps"
DEFAULT_PREFIXES_DIR = "playtron/wine_prefixes"

# GameOS (OSTree) uses a different home structure
GAMEOS_DATA_DIR = "var/home/playtron/.local/share"

# Providers we import (Steam is already managed by Lutris)
SUPPORTED_PROVIDERS = {"epic", "epicgames", "gog", "local"}

# Map Playtron provider names to Lutris service IDs
PROVIDER_TO_SERVICE = {
    "gog": "gog",
    "epic": "egs",
    "epicgames": "egs",
}

# Filesystems that typically contain user data
DATA_FILESYSTEMS = {"ext4", "ext3", "xfs", "btrfs", "ntfs", "vfat", "exfat", "fuseblk", "ntfs3"}

# System paths to skip when scanning mounts
SKIP_MOUNT_PREFIXES = ("/sys", "/proc", "/dev", "/run/user", "/boot", "/snap", "/var/lib")


def scan_all_libraries() -> List[str]:
    """Scan all detected Playtron libraries and import games"""
    added_games = []
    library_paths = _get_library_paths()

    if not library_paths:
        logger.info("No Playtron libraries found")
        return added_games

    for library_path in library_paths:
        logger.info("Scanning Playtron library: %s", library_path)
        added_games.extend(_import_games_from_library(library_path))

    if added_games:
        _sync_media_for_games(added_games)

    logger.info("Imported %d games from Playtron", len(added_games))
    return added_games


def _get_library_paths() -> List[str]:
    """Return all potential Playtron library paths (home + mounted drives)"""
    paths = []

    # $XDG_DATA_HOME directory
    home_data = settings.XDG_DATA_DIR
    if os.path.isdir(os.path.join(home_data, DEFAULT_APPS_DIR)):
        paths.append(home_data)

    # All mount points
    for mount_path in _get_mount_points():
        _check_path_for_playtron(mount_path, paths)

    return paths


def _get_mount_points() -> List[str]:
    """Get user-accessible mount points from /proc/mounts"""
    mount_points = []

    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue

                mount_path, fs_type = parts[1], parts[2]

                if fs_type not in DATA_FILESYSTEMS:
                    continue
                if mount_path == "/":
                    continue
                if any(mount_path.startswith(prefix) for prefix in SKIP_MOUNT_PREFIXES):
                    continue
                if os.path.isdir(mount_path):
                    mount_points.append(mount_path)
    except OSError:
        pass

    return mount_points


def _check_path_for_playtron(path: str, paths: List[str]) -> None:
    """Check a path for Playtron libraries (standard and GameOS layouts)"""
    if not os.path.isdir(path):
        return

    # Standard layout: <path>/playtron/apps
    if os.path.isdir(os.path.join(path, DEFAULT_APPS_DIR)):
        paths.append(path)
        return

    # GameOS layout: <path>/var/home/playtron/.local/share/playtron/apps
    gameos_data = os.path.join(path, GAMEOS_DATA_DIR)
    if os.path.isdir(os.path.join(gameos_data, DEFAULT_APPS_DIR)):
        paths.append(gameos_data)


def _import_games_from_library(install_root: str) -> List[str]:
    """Scan a Playtron library and import games to Lutris"""
    added_games = []
    apps_base = os.path.join(install_root, DEFAULT_APPS_DIR)

    if not os.path.isdir(apps_base):
        return added_games

    for game_install_root, game_path, info in _scan_library(install_root):
        game_id = _import_game(game_install_root, game_path, info)
        if game_id:
            added_games.append(game_id)

    return added_games


def _scan_library(install_root: str) -> List[Tuple[str, str, Dict]]:
    """Scan a Playtron library for games.

    Returns a list of (install_root, game_path, info) tuples. game_path is
    the local directory containing the playtron_info_v3.json file, which may
    differ from install_config.install_folder when importing from a mounted
    GameOS drive.
    """
    games = []
    apps_base = os.path.join(install_root, DEFAULT_APPS_DIR)

    for provider in os.listdir(apps_base):
        if provider.lower() not in SUPPORTED_PROVIDERS:
            continue

        provider_path = os.path.join(apps_base, provider)
        if not os.path.isdir(provider_path):
            continue

        for game_folder in os.listdir(provider_path):
            game_path = os.path.join(provider_path, game_folder)
            info_file = os.path.join(game_path, PLAYTRON_INFO_FILE)

            if not os.path.isfile(info_file):
                continue

            info = _parse_playtron_info(info_file)
            if info:
                games.append((install_root, game_path, info))

    return games


def _import_game(install_root: str, game_path: str, info: Dict) -> Optional[str]:
    """Import a single game to Lutris, returns game ID or None"""
    game_data = _create_game_config(install_root, info, game_path)
    if not game_data:
        return None

    slug = game_data["slug"]
    name = game_data["name"]
    provider = game_data["provider"]

    # Skip if already installed
    if get_games(filters={"slug": slug, "installed": "1"}):
        logger.debug("Game '%s' already exists, skipping", name)
        return None

    installer_slug = f"{slug}-playtron-{provider}"
    if get_games(filters={"installer_slug": installer_slug, "installed": "1"}):
        logger.debug("Game '%s' already imported from Playtron, skipping", name)
        return None

    logger.info("Importing Playtron game: %s (%s)", name, provider)

    configpath = write_game_config(slug, game_data["config"])

    service = PROVIDER_TO_SERVICE.get(provider)
    provider_id = game_data.get("provider_id")

    db_data = {
        "name": name,
        "runner": game_data["runner"],
        "slug": slug,
        "platform": game_data["platform"],
        "directory": game_data["directory"],
        "installed": 1,
        "installer_slug": installer_slug,
        "configpath": configpath,
    }

    if service and provider_id:
        db_data["service"] = service
        db_data["service_id"] = provider_id

    if game_data.get("lastplayed"):
        db_data["lastplayed"] = game_data["lastplayed"]
    if game_data.get("installed_at"):
        db_data["installed_at"] = game_data["installed_at"]

    game_id = add_or_update(**db_data)

    if game_id:
        logger.info("Added game: %s (ID: %s)", name, game_id)

    return game_id


def _create_game_config(install_root: str, info: Dict, game_path: str = "") -> Optional[Dict]:
    """Create a Lutris game config from Playtron info"""
    owned_app = info.get("owned_app", {})
    install_config = info.get("install_config", {})

    name = owned_app.get("name")
    if not name:
        return None

    provider = owned_app.get("provider", "").lower()
    provider_id = owned_app.get("provider_id", "")
    platform = install_config.get("platform", "windows")
    install_folder = install_config.get("install_folder", "")

    # install_folder from the JSON is an absolute path from the original system.
    # When importing from a mounted GameOS drive it won't exist locally; fall
    # back to game_path which is the resolved local directory for this game.
    if install_folder and not os.path.isdir(install_folder) and game_path and os.path.isdir(game_path):
        install_folder = game_path

    # Timestamps (Playtron uses milliseconds)
    launched_at = info.get("launched_at")
    downloaded_at = info.get("downloaded_at")
    lastplayed = int(launched_at / 1000) if launched_at else None
    installed_at = int(downloaded_at / 1000) if downloaded_at else None

    executable = install_config.get("executable", "")
    working_dir = install_config.get("workingdir")
    arguments = install_config.get("arguments")

    # GOG games store executable info in goggame-*.info
    if not executable and provider == "gog" and provider_id and install_folder:
        gog_info = _get_gog_game_info(install_folder, provider_id)
        if gog_info:
            executable = gog_info.get("executable", "")
            working_dir = working_dir or gog_info.get("workingdir")
            arguments = arguments or gog_info.get("arguments")

    info_install_root = install_config.get("install_root") or install_root
    runner = "linux" if platform.lower() == "linux" else "wine"

    # Build full executable path
    full_exe_path = os.path.join(install_folder, executable) if executable and install_folder else executable

    config = {
        "game": {"exe": full_exe_path},
        "system": {},
    }

    # Resolve working directory
    if working_dir:
        if not os.path.isabs(working_dir):
            working_dir = os.path.join(install_folder, working_dir)
        config["game"]["working_dir"] = working_dir

    if arguments:
        config["game"]["args"] = arguments

    # Wine prefix - try install_root from the JSON first, then the local
    # install_root. The JSON path is absolute from the original system and
    # won't exist when importing from a mounted GameOS drive.
    if runner == "wine" and provider_id:
        for root in dict.fromkeys([info_install_root, install_root]):
            prefix_path = _get_wine_prefix_path(root, provider, provider_id)
            if os.path.isdir(prefix_path):
                config["game"]["prefix"] = prefix_path
                break

    return {
        "name": name,
        "slug": slugify(name),
        "runner": runner,
        "platform": "Linux" if runner == "linux" else "Windows",
        "directory": install_folder,
        "config": config,
        "provider": provider,
        "provider_id": provider_id,
        "lastplayed": lastplayed,
        "installed_at": installed_at,
    }


def _get_wine_prefix_path(install_root: str, provider: str, provider_id: str) -> str:
    """Compute the Wine prefix path for a Playtron game"""
    prefix_base = os.path.join(install_root, DEFAULT_PREFIXES_DIR, provider, provider_id)
    pfx_path = os.path.join(prefix_base, "pfx")
    return pfx_path if os.path.isdir(pfx_path) else prefix_base


def _get_gog_game_info(install_folder: str, provider_id: str) -> Optional[Dict]:
    """Parse GOG game info file to get executable details.

    Tries the exact goggame-{provider_id}.info first, then falls back to
    scanning for any goggame-*.info files in the install folder.
    """
    info = _load_gog_info_file(os.path.join(install_folder, f"goggame-{provider_id}.info"))

    # Fallback: scan for any goggame-*.info files
    if info is None and os.path.isdir(install_folder):
        for filename in os.listdir(install_folder):
            if filename.startswith("goggame-") and filename.endswith(".info"):
                info = _load_gog_info_file(os.path.join(install_folder, filename))
                if info and info.get("playTasks"):
                    break
        else:
            info = None

    if not info:
        return None

    return _extract_gog_primary_task(info)


def _load_gog_info_file(info_file: str) -> Optional[Dict]:
    """Load and parse a goggame-*.info JSON file"""
    try:
        with open(info_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return None


def _extract_gog_primary_task(info: Dict) -> Optional[Dict]:
    """Extract executable info from GOG playTasks.

    Prefers the task marked isPrimary, falls back to the first FileTask.
    """
    first_file_task = None

    for task in info.get("playTasks", []):
        if task.get("type") != "FileTask":
            continue
        result = {
            "executable": task.get("path", "").replace("\\", "/"),
            "arguments": task.get("arguments"),
            "workingdir": task.get("workingDir", "").replace("\\", "/") if task.get("workingDir") else None,
        }
        if task.get("isPrimary"):
            return result
        if first_file_task is None:
            first_file_task = result

    return first_file_task


def _parse_playtron_info(filepath: str) -> Optional[Dict]:
    """Parse a playtron_info_v3.json file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as ex:
        logger.warning("Failed to parse %s: %s", filepath, ex)
        return None


def _sync_media_for_games(game_ids: List[str]) -> None:
    """Resolve canonical Lutris slugs via service appids and download media.

    The locally generated slug (from slugify) may not match the Lutris API due
    to normalization differences (NFD vs NFKD). By looking up games through the
    service-specific API endpoint using the store appid, we get the canonical
    slug and can download artwork reliably.
    """
    from lutris import settings

    # Group games by service
    games_by_service: Dict[str, List[Tuple[str, str, str]]] = {}
    for game_id in game_ids:
        game = get_game_by_field(game_id, "id")
        if not game or not game.get("service") or not game.get("service_id"):
            # No service info; try slug-based media download as fallback
            if game:
                download_lutris_media(game["slug"])
            continue
        service = game["service"]
        games_by_service.setdefault(service, []).append((game_id, game["slug"], game["service_id"]))

    for service, games in games_by_service.items():
        appids = [g[2] for g in games]
        api_games = get_api_games(appids, service=service)
        if not api_games:
            # Fallback to slug-based download
            for _game_id, slug, _ in games:
                download_lutris_media(slug)
            continue

        # Build appid -> api_game lookup from the provider_games in the API response
        appid_to_api = {}
        for api_game in api_games:
            for service_info in api_game.get("provider_games", []):
                if service_info.get("service") == service:
                    appid_to_api[str(service_info.get("slug", ""))] = api_game
            # Also check direct appid field
            if "appid" in api_game:
                appid_to_api[str(api_game["appid"])] = api_game

        for game_id, local_slug, appid in games:
            api_game = appid_to_api.get(appid)
            if api_game and api_game.get("slug") and api_game["slug"] != local_slug:
                # Update the game's slug to the canonical Lutris slug
                logger.info("Updating slug for game %s: %s -> %s", game_id, local_slug, api_game["slug"])
                sql.db_update(settings.DB_PATH, "games", {"slug": api_game["slug"]}, {"id": game_id})
                download_lutris_media(api_game["slug"])
            else:
                download_lutris_media(api_game["slug"] if api_game else local_slug)
