import os
import re
import gi


gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GnomeDesktop", "3.0")

from lutris.config import write_game_config
from lutris.util.log import logger
from lutris.database.games import get_games, add_game
from lutris.api import get_api_games, get_game_installers
from lutris.services.lutris import download_lutris_media

def get_game_slugs(dirname):
    """Scan a directory for games previously installed with lutris"""
    folders = os.listdir(dirname)
    game_folders = []
    for folder in folders:
        if not os.path.isdir(os.path.join(dirname, folder)):
            continue
        if not re.match(r"^[a-z0-9-]*$", folder):
            logger.info("Skipping non matching folder %s", folder)
            continue
        game_folders.append(folder)
    return game_folders


def find_game_folder(dirname, api_game):
    game_folder = os.path.join(dirname, api_game["slug"])
    if os.path.exists(game_folder):
        return game_folder
    for alias in api_game["aliases"]:
        game_folder = os.path.join(dirname, alias["slug"])
        if os.path.exists(game_folder):
            return game_folder


def detect_game_from_installer(game_folder, installer):
    try:
        exe_path = installer["script"]["game"].get("exe")
    except KeyError:
        exe_path = installer["script"].get("exe")
    if not exe_path:
        return
    exe_path = exe_path.replace("$GAMEDIR/", "")
    full_path = os.path.join(game_folder, exe_path)
    if os.path.exists(full_path):
        return full_path


def find_game(game_folder, api_game):
    installers = get_game_installers(api_game["slug"])
    for installer in installers:
        full_path = detect_game_from_installer(game_folder, installer)
        if full_path:
            return full_path, installer
    return None, None

def get_used_directories():
    directories = set()
    for game in get_games():
        if game['directory']:
            directories.add(game['directory'])
    return directories


def install_game(installer, game_folder, full_path):
    game_config = {"game": {}}
    if "system" in installer["script"]:
        game_config["system"] = installer["script"]["system"]
    if installer["runner"] in installer["script"]:
        game_config[installer["runner"]] = installer["script"][installer["runner"]]
    if "game" in installer["script"]:
        game_config["game"] = installer["script"]["game"]
    game_config["game"]["exe"] = full_path
    configpath = write_game_config(installer["slug"], game_config)
    game_id = add_game(
        name=installer["name"],
        runner=installer["runner"],
        slug=installer["game_slug"],
        directory=game_folder,
        installed=1,
        installer_slug=installer["slug"],
        configpath=configpath,
    )
    return game_id

def scan_directory(dirname):
    slugs = get_game_slugs(dirname)
    directories = get_used_directories()
    api_games = get_api_games(slugs)
    slugs_seen = set()
    for api_game in api_games:
        if api_game["slug"] in slugs_seen:
            continue
        slugs_seen.add(api_game["slug"])
        game_folder = find_game_folder(dirname, api_game)
        if game_folder in directories:
            continue
        full_path, installer = find_game(game_folder, api_game)
        if full_path:
            print("Found %s in %s" % (api_game["name"], full_path))
            install_game(installer, game_folder, full_path)
            download_lutris_media(installer["game_slug"])


def download_all_media():
    slugs = {game["slug"] for game in get_games()}
    for slug in slugs:
        download_lutris_media(slug)
