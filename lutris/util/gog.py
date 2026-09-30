import glob
import json
import os

from lutris.util import system
from lutris.util.log import logger


def has_primary_executable(info_path):
    """Whether the game's main executable, as a goggame-*.info file names it, sits next to that
    file. GOG's installer also leaves copies of the .info file elsewhere (ProgramData)."""
    try:
        with open(info_path, encoding="utf-8") as info_file:
            play_tasks = json.load(info_file).get("playTasks", [])
    except (OSError, ValueError):
        return False
    folder = os.path.dirname(info_path)
    for task in play_tasks:
        if task.get("isPrimary") and task.get("path"):
            path = task["path"].replace("\\", "/").lstrip("/")
            return os.path.exists(system.fix_path_case(os.path.join(folder, path)))
    return False


def find_gog_info_dir(drive_c, gog_id=None):
    """Return the folder under a Wine prefix's drive_c where the GOG game is installed, found by
    its goggame-*.info file wherever the GOG installer was told to put it. With a GOG product id,
    only that product's file counts. The 'windows' and 'users' folders are skipped (the latter
    links to $HOME)."""
    max_depth = drive_c.rstrip(os.sep).count(os.sep) + 4
    for root, dirs, files in os.walk(drive_c):
        if root == drive_c:
            dirs[:] = [d for d in dirs if d.casefold() not in ("windows", "users")]
        if root.count(os.sep) >= max_depth:
            dirs[:] = []
        for filename in files:
            if not (filename.startswith("goggame-") and filename.endswith(".info")):
                continue
            if gog_id and filename != "goggame-%s.info" % gog_id:
                continue
            if has_primary_executable(os.path.join(root, filename)):
                return root
    return None


def get_gog_game_path(target_path, gog_id=None):
    """Return the absolute path where a GOG game is installed"""
    drive_c = os.path.join(target_path, "drive_c")
    if os.path.isdir(drive_c):
        info_dir = find_gog_info_dir(drive_c, gog_id) or (gog_id and find_gog_info_dir(drive_c))
        if info_dir:
            return info_dir
    gog_game_path = os.path.join(target_path, "drive_c/GOG Games/")
    if not os.path.exists(gog_game_path):
        logger.warning("No GOG game found in %s", target_path)
        return None
    games = os.listdir(gog_game_path)
    if len(games) > 1:
        logger.warning("More than 1 game found, this is currently unsupported")
    return os.path.join(gog_game_path, games[0])


def get_gog_config(gog_game_path):
    """Extract runtime information such as executable paths from GOG files"""
    config_files = glob.glob(os.path.join(gog_game_path, "goggame-*.info"))
    if not config_files:
        logger.error("No config file found in %s", gog_game_path)
        return
    gog_config_path = config_files[0]
    with open(gog_config_path, encoding="utf-8") as gog_config_file:
        gog_config = json.loads(gog_config_file.read())
    return gog_config


def get_game_config(task, gog_game_path):
    def resolve_path(path):
        """GOG's paths are relative to the gog_game_path, not relative to each other,
        so we resolve them all to absolute paths and fix casing issues. If required,
        we'll replace backslashes with slashes."""
        resolved = system.fix_path_case(os.path.join(gog_game_path, path))
        if os.path.exists(resolved):
            return resolved

        fixed = path.replace("\\", "/")
        if fixed.startswith("/"):
            fixed = fixed[1:]
        resolved = system.fix_path_case(os.path.join(gog_game_path, fixed))
        if os.path.exists(resolved):
            return resolved

        logger.warning("GOG configuration path '%s' could not be resolved", path)
        return path

    config = {}
    if "path" not in task:
        return

    config["exe"] = resolve_path(task["path"])
    if task.get("workingDir"):
        config["working_dir"] = resolve_path(task["workingDir"])
    if task.get("arguments"):
        config["args"] = task["arguments"]
    if task.get("name"):
        config["name"] = task["name"]
    return config


def convert_gog_config_to_lutris(gog_config, gog_game_path):
    play_tasks = gog_config.get("playTasks", [])
    lutris_config = {"launch_configs": []}
    for task in play_tasks:
        config = get_game_config(task, gog_game_path)
        if not config:
            continue
        if task.get("isPrimary"):
            lutris_config.update(config)
        else:
            lutris_config["launch_configs"].append(config)
    return lutris_config


def get_gog_config_from_path(target_path):
    """Return the GOG configuration for a root path"""
    gog_game_path = get_gog_game_path(target_path)
    if gog_game_path:
        return get_gog_config(gog_game_path)


def find_gog_config_dir(install_dir):
    """Return the directory containing goggame-*.info files, or None.

    Windows installs place the .info file directly in the install root;
    Linux offline installs nest it under 'game/'; Linux depot installs nest
    it under '<gameName>/game/'. We check those locations and one level of
    subdirectories' 'game/' folders. We deliberately don't recurse further
    to avoid following symlink cycles inside any Wine prefix that may live
    under the install dir."""
    if not install_dir or not os.path.isdir(install_dir):
        return None

    def has_info(path):
        return os.path.isdir(path) and any(f.startswith("goggame-") and f.endswith(".info") for f in os.listdir(path))

    candidates = [install_dir, os.path.join(install_dir, "game")]
    for entry in os.listdir(install_dir):
        sub = os.path.join(install_dir, entry)
        if os.path.isdir(sub):
            candidates.extend([sub, os.path.join(sub, "game")])

    for candidate in candidates:
        if has_info(candidate):
            return candidate
    return None


def find_installed_product_ids(install_dir):
    """Return the GOG product IDs of all goggame-*.info files in the install.

    GOG writes one .info file per installed product (base game + each DLC),
    named goggame-<productId>.info. The returned set includes the base
    game's id; callers that only want DLCs should subtract it."""
    config_dir = find_gog_config_dir(install_dir)
    if not config_dir:
        return set()
    ids = set()
    for filename in os.listdir(config_dir):
        if filename.startswith("goggame-") and filename.endswith(".info"):
            product_id = filename[len("goggame-") : -len(".info")]
            if product_id.isdigit():
                ids.add(product_id)
    return ids


def apply_gog_config(installer):
    """Post-install hook: read GOG config from the install target and merge into the game script."""
    target_path = installer.interpreter.target_path
    gog_id = installer.service_appid if installer.service and installer.service.id == "gog" else None
    if (
        (gog_game_path := get_gog_game_path(target_path, gog_id))
        and (gog_config := get_gog_config(gog_game_path))
        and "game" in installer.script
    ):
        lutris_config = convert_gog_config_to_lutris(gog_config, gog_game_path)
        installer.script["game"].update(lutris_config)
