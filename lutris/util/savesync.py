import json
import os
import platform
import time
from datetime import datetime

try:
    from webdav4.client import Client
    WEBDAV_AVAILABLE = True
except ImportError:
    WEBDAV_AVAILABLE = False

from lutris import settings
from lutris.util.log import logger
from lutris.util.strings import human_size
from lutris.util.wine.prefix import find_prefix

DIR_CREATE_CACHE = []


def get_dir_info(path):
    path_files = {}
    path = path.rstrip("/")
    if os.path.isfile(path):
        path_files[os.path.basename(path)] = os.stat(path)
        return path_files
    for root, _dirs, files in os.walk(path):
        basedir = root[len(path) + 1:]
        for path_file in files:
            path_files[os.path.join(basedir, path_file)] = os.stat(os.path.join(root, path_file))
    return path_files


def format_dir_info(path):
    path_files = get_dir_info(path)
    output = []
    for path_file in sorted(path_files, key=lambda k: path_files[k].st_mtime, reverse=True):
        fstats = path_files[path_file]
        output.append({
            "file": path_file,
            "size": fstats.st_size,
            "modified": fstats.st_mtime,
        })
    return output


def print_dir_details(title, path):
    save_files = get_dir_info(path)
    if not save_files:
        return
    print(title)
    print("=" * len(title))
    total_size = 0
    for save_file in sorted(save_files, key=lambda k: save_files[k].st_mtime, reverse=True):
        fstats = save_files[save_file]
        total_size += fstats.st_size
        print("%s (%s)\t\t%s" % (save_file, human_size(fstats.st_size),
              datetime.fromtimestamp(fstats.st_mtime).strftime("%c")))
    print("Total size: %s" % human_size(total_size))


def get_basedir(game):
    save_config = game.config.game_level["game"]["save_config"]
    basedir = save_config.get("basedir") or game.directory
    if not basedir:
        logger.error("No save directory found")
    prefix_path = os.path.dirname(game.config.game_config.get("exe"))
    username = os.getenv("USER") or "steamuser"

    if game.runner_name == "wine":
        prefix_path = game.config.game_config.get("prefix", "")
        if prefix_path and not prefix_path.startswith("/"):
            prefix_path = os.path.join(game.directory, prefix_path)
        exe = game.config.game_config.get("exe", "")
        if exe and not exe.startswith("/"):
            exe = os.path.join(game.directory, exe)
        if not prefix_path:
            prefix_path = find_prefix(exe)
        if "$GAMEDIR" in basedir:
            basedir = basedir.replace("$GAMEDIR", game.directory or prefix_path)
        if "$USERDIR" in basedir:
            basedir = basedir.replace("$USERDIR", os.path.join(prefix_path, "drive_c/users/%s" % username))
    else:
        if "$GAMEDIR" in basedir:
            basedir = basedir.replace("$GAMEDIR", game.directory)
        if "$USERDIR" in basedir:
            basedir = os.path.expanduser(basedir.replace("$USERDIR", "~"))
    return basedir


def get_save_info(basedir, save_config):
    results = {"basedir": basedir, "config": save_config}
    for section in ["saves", "logs", "config", "screenshots"]:
        if section in save_config:
            results[section] = {}
            path = os.path.join(basedir, save_config[section])
            results[section]["path"] = path
            results[section]["files"] = format_dir_info(path)
    return results


def show_save_stats(game, output_format="text"):
    save_config = game.config.game_level["game"].get("save_config")
    if not save_config:
        logger.error("%s has no save configuration")
        return
    basedir = get_basedir(game)
    if output_format == "json":
        print(json.dumps(get_save_info(basedir, save_config), indent=2))
    else:
        if "saves" in save_config:
            print_dir_details("Saves", os.path.join(basedir, save_config["saves"]))
        if "logs" in save_config:
            print_dir_details("Logs", os.path.join(basedir, save_config["logs"]))
        if "config" in save_config:
            print_dir_details("Config", os.path.join(basedir, save_config["config"]))


def create_dirs(client, path):
    parts = path.split("/")
    for i in range(len(parts)):
        relpath = os.path.join(*parts[:i + 1])
        if relpath in DIR_CREATE_CACHE:
            continue
        if not client.exists(relpath):
            logger.debug("Creating Webdav folder %s", relpath)
            client.mkdir(relpath)
        DIR_CREATE_CACHE.append(relpath)


def upload_save(game):
    save_config = game.config.game_level["game"].get("save_config")
    if not save_config:
        logger.error("%s has no save configuration")
        return
    print("Uploading save for %s" % game)
    if not WEBDAV_AVAILABLE:
        logger.error("Python package 'webdav4' not installed.")
        return
    webdav_host = settings.read_setting("webdav_host")
    webdav_user = settings.read_setting("webdav_user")
    webdav_pass = settings.read_setting("webdav_pass")
    webdav_saves_path = settings.read_setting("webdav_saves_path")
    client = Client(webdav_host, auth=(webdav_user, webdav_pass), timeout=50)
    save_id = f"{platform.node()}-{int(time.time())}"
    save_dest_dir = os.path.join(webdav_saves_path, game.slug, save_id)
    create_dirs(client, save_dest_dir)
    basedir = get_basedir(game)
    save_info = get_save_info(basedir, save_config)
    basepath = save_info["saves"]["path"]
    if os.path.isfile(basepath):
        basepath = os.path.dirname(basepath)
    relpath = basepath[len(save_info["basedir"]) + 1:]
    create_dirs(client, os.path.join(save_dest_dir, relpath))
    for save_file in save_info["saves"]["files"]:
        upload_file_source = os.path.join(basepath, save_file["file"])
        upload_file_dest = os.path.join(save_dest_dir, relpath, save_file["file"])
        print(upload_file_source, ">", upload_file_dest)
        client.upload_file(upload_file_source, upload_file_dest)
