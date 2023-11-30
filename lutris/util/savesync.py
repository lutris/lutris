import json
import os
import platform
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
SAVE_TYPES = ["saves", "logs", "configs", "screenshots"]
SYNC_TYPES = ["saves", "configs"]


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


def get_webdav_client():
    if not WEBDAV_AVAILABLE:
        logger.error("Python package 'webdav4' not installed.")
        return
    webdav_host = settings.read_setting("webdav_host")
    if not webdav_host:
        logger.error("No remote host set (webdav_host)")
        return
    webdav_user = settings.read_setting("webdav_user")
    if not webdav_user:
        logger.error("No remote username set (webdav_user)")
        return
    webdav_pass = settings.read_setting("webdav_pass")
    if not webdav_pass:
        logger.error("No remote password set (webdav_pass)")
        return
    return Client(webdav_host, auth=(webdav_user, webdav_pass), timeout=50)


def get_existing_saves(client, game_base_dir):
    if not client.exists(game_base_dir):
        return []
    base_dir_content = client.ls(game_base_dir)
    saves = []
    for save_folder in base_dir_content:
        if save_folder["type"] != "directory":
            continue
        local_save_info = os.path.join(settings.CACHE_DIR, "%s.json" % os.path.basename(save_folder["name"]))
        client.download_file(os.path.join(save_folder["name"], "saveinfo.json"), local_save_info)
        saves.append(local_save_info)
    return saves


def upload_save(game, sections=SYNC_TYPES):
    save_config = game.config.game_level["game"].get("save_config")
    if not save_config:
        logger.error("%s has no save configuration")
        return
    print("Uploading save for %s" % game)
    webdav_saves_path = settings.read_setting("webdav_saves_path")
    if not webdav_saves_path:
        logger.error("No save path for the remote host (webdav_saves_path setting)")
        return
    client = get_webdav_client()
    if not client:
        return

    # game_base_dir = os.path.join(webdav_saves_path, game.slug)
    # existing_saves = get_existing_saves(client, game_base_dir)
    # for save in existing_saves:
    #     print(save)
    #     os.remove(save)
    basedir = get_basedir(game)
    save_info = get_save_info(basedir, save_config)
    max_time = 0
    for section in sections:
        for save_file in save_info[section]["files"]:
            if int(save_file["modified"]) > max_time:
                max_time = int(save_file["modified"])

    save_id = f"{platform.node()}-{max_time}"
    save_dest_dir = os.path.join(webdav_saves_path, game.slug, save_id)
    create_dirs(client, save_dest_dir)

    save_info = get_save_info(basedir, save_config)
    save_info_name = "saveinfo.json"
    save_info_path = os.path.join(settings.CACHE_DIR, save_info_name)
    with open(save_info_path, "w", encoding="utf-8") as save_info_file:
        json.dump(save_info, save_info_file, indent=2)
    client.upload_file(save_info_path, os.path.join(save_dest_dir, save_info_name))
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


def load_save_info(save_info_path):
    with open(save_info_path, "r", encoding="utf-8") as save_info_file:
        save_info = json.load(save_info_file)
    return save_info


def parse_save_info(save_info_path):
    save_info_name, _ext = os.path.splitext(os.path.basename(save_info_path))
    hostname, ts = save_info_name.rsplit("-", maxsplit=1)
    return {"hostname": hostname, "datetime": datetime.fromtimestamp(int(ts))}


def save_check(game):
    save_config = game.config.game_level["game"].get("save_config")
    if not save_config:
        logger.error("%s has no save configuration")
        return
    print("Checking sync of save for %s" % game)
    webdav_saves_path = settings.read_setting("webdav_saves_path")
    if not webdav_saves_path:
        logger.error("No save path for the remote host (webdav_saves_path setting)")
        return
    client = get_webdav_client()
    if not client:
        return
    basedir = get_basedir(game)
    remote_basedir = os.path.join(webdav_saves_path, game.slug)
    existing_saves = get_existing_saves(client, remote_basedir)
    current_save_info = get_save_info(basedir, save_config)
    for save_path in existing_saves:
        save_info_meta = parse_save_info(save_path)
        host = save_info_meta["hostname"]
        print("Host: %s (%s)" % (host, save_info_meta["datetime"].strftime("%c")))
        save_info = load_save_info(save_path)
        unsynced = {}
        for section in SAVE_TYPES:
            if section not in current_save_info:
                continue
            files = {file_info["file"]: file_info for file_info in save_info[section]["files"]}
            local_files = {file_info["file"]: file_info for file_info in current_save_info[section]["files"]}
            unsynced[section] = {"unsynced": [], "newer": [], "older": [], "missing": []}

            for filename, file_info in local_files.items():
                remote_file = files.get(filename)
                if not remote_file:
                    unsynced[section]["unsynced"].append(filename)
                files[filename]["seen"] = True
                if file_info["modified"] > files[filename]["modified"]:
                    print("Local file %s is newer" % filename)
                    unsynced[section]["newer"].append(filename)
                if file_info["modified"] < files[filename]["modified"]:
                    print("Local file %s is older" % filename)
                    unsynced[section]["older"].append(filename)
            for filename, file_info in files.items():
                if file_info.get("seen"):
                    continue
                unsynced[section]["missing"].append(filename)

        out_of_sync = False
        for section in SAVE_TYPES:
            if section not in unsynced:
                continue
            for _key, value in unsynced[section].items():
                if value:
                    out_of_sync = True
        if not out_of_sync:
            print("🟢 Save %s synced with local game" % os.path.basename(save_path))
        else:
            print("🟠 Save %s out of sync with local game" % os.path.basename(save_path))
            print(unsynced)

        os.remove(save_path)
