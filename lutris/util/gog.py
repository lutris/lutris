import json
import os

from lutris.util.log import logger


def get_gog_game_path(target_path):
    """Return the absolute path where a GOG game is installed"""
    gog_game_path = os.path.join(target_path, "drive_c/GOG Games/")
    if not os.path.exists(gog_game_path):
        logger.warning("No 'GOG Games' folder in %s", target_path)
        return None
    games = os.listdir(gog_game_path)
    if len(games) > 1:
        logger.warning("More than 1 game found, this is currently unsupported")
    return os.path.join(gog_game_path, games[0])


def get_gog_config(gog_game_path):
    """Extract runtime information such as executable paths from GOG files"""
    config_filename = [
        fn
        for fn in os.listdir(gog_game_path)
        if fn.startswith("goggame") and fn.endswith(".info")
    ]
    if not config_filename:
        logger.error("No config file found in %s", gog_game_path)
        return
    gog_config_path = os.path.join(gog_game_path, config_filename[0])
    with open(gog_config_path, encoding='utf-8') as gog_config_file:
        gog_config = json.loads(gog_config_file.read())
    return gog_config


def get_game_config(task, gog_game_path):
    config = {}
    exe = task["path"]
    exe_abspath = os.path.join(gog_game_path, exe)
    if os.path.exists(exe_abspath):
        exe = exe_abspath
    else:
        logger.warning("No executable found at %s", exe_abspath)
    config["exe"] = exe
    if task.get("workingDir"):
        config["working_dir"] = task["workingDir"]
    if task.get("arguments"):
        config["args"] = task["arguments"]
    if task.get("name"):
        config["name"] = task["name"]
    return config


def convert_gog_config_to_lutris(gog_config, gog_game_path):
    play_tasks = gog_config["playTasks"]
    lutris_config = {"launch_configs": []}
    for task in play_tasks:
        config = get_game_config(task, gog_game_path)
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
