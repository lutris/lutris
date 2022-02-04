import os

from lutris.api import get_api_games, get_game_installers
from lutris.database.games import get_games
from lutris.installer.errors import MissingGameDependency
from lutris.installer.interpreter import ScriptInterpreter
from lutris.util.log import logger
from lutris.util.strings import slugify


def get_game_slugs_and_folders(dirname):
    """Scan a directory for games previously installed with lutris"""
    folders = os.listdir(dirname)
    game_folders = {}
    for folder in folders:
        if not os.path.isdir(os.path.join(dirname, folder)):
            continue
        game_folders[slugify(folder)] = folder
    return game_folders


def find_game_folder(dirname, api_game, slugs_map):
    if api_game["slug"] in slugs_map:
        game_folder = os.path.join(dirname, slugs_map[api_game["slug"]])
        if os.path.exists(game_folder):
            return game_folder
    for alias in api_game["aliases"]:
        if alias["slug"] in slugs_map:
            game_folder = os.path.join(dirname, slugs_map[alias["slug"]])
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


def install_game(installer, game_folder):
    interpreter = ScriptInterpreter(installer)
    interpreter.target_path = game_folder
    interpreter.installer.save()


def scan_directory(dirname):
    slugs_map = get_game_slugs_and_folders(dirname)
    directories = get_used_directories()
    api_games = get_api_games(list(slugs_map.keys()))
    slugs_seen = set()
    slugs_installed = set()
    for api_game in api_games:
        if api_game["slug"] in slugs_seen:
            continue
        slugs_seen.add(api_game["slug"])
        game_folder = find_game_folder(dirname, api_game, slugs_map)
        if game_folder in directories:
            slugs_installed.add(api_game["slug"])
            continue
        full_path, installer = find_game(game_folder, api_game)
        if full_path:
            logger.info("Found %s in %s", api_game["name"], full_path)
            try:
                install_game(installer, game_folder)
            except MissingGameDependency as ex:
                logger.error("Skipped %s: %s", api_game["name"], ex)
            slugs_installed.add(api_game["slug"])

    installed_map = {slug: folder for slug, folder in slugs_map.items() if slug in slugs_installed}
    missing_map = {slug: folder for slug, folder in slugs_map.items() if slug not in slugs_installed}
    return installed_map, missing_map
