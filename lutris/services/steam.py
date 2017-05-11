import os
import re

from lutris import pga
from lutris.util.log import logger
from lutris.util.steam import get_appmanifests, vdf_parse
from lutris.util.system import fix_path_case
from lutris.util.strings import slugify
from lutris.config import make_game_config_id, LutrisConfig


APP_STATE_FLAGS = [
    "Invalid",
    "Uninstalled",
    "Update Required",
    "Fully Installed",
    "Encrypted",
    "Locked",
    "Files Missing",
    "AppRunning",
    "Files Corrupt",
    "Update Running",
    "Update Paused",
    "Update Started",
    "Uninstalling",
    "Backup Running",
    "Reconfiguring",
    "Validating",
    "Adding Files",
    "Preallocating",
    "Downloading",
    "Staging",
    "Committing",
    "Update Stopping"
]


class AppManifest:
    def __init__(self, appmanifest_path):
        self.steamapps_path, filename = os.path.split(appmanifest_path)
        self.steamid = re.findall(r'(\d+)', filename)[0]
        if os.path.exists(appmanifest_path):
            with open(appmanifest_path, "r") as appmanifest_file:
                self.appmanifest_data = vdf_parse(appmanifest_file, {})

    @property
    def app_state(self):
        return self.appmanifest_data.get('AppState') or {}

    @property
    def user_config(self):
        return self.app_state.get('UserConfig') or {}

    @property
    def name(self):
        _name = self.app_state.get('name')
        if not _name:
            _name = self.user_config.get('name')
        return _name

    @property
    def slug(self):
        return slugify(self.name)

    @property
    def installdir(self):
        return self.app_state.get('installdir')

    @property
    def states(self):
        """Return the states of a Steam game."""
        states = []
        state_flags = self.app_state.get('StateFlags', 0)
        state_flags = bin(int(state_flags))[:1:-1]
        for index, flag in enumerate(state_flags):
            if flag == '1':
                states.append(APP_STATE_FLAGS[index + 1])
        return states

    def is_installed(self):
        return 'Fully Installed' in self.states

    def get_install_path(self):
        if not self.installdir:
            return
        install_path = fix_path_case(os.path.join(self.steamapps_path, "common",
                                                  self.installdir))
        if install_path:
            return install_path

    def get_platform(self):
        steamapps_paths = get_steamapps_paths()
        if self.steamapps_path in steamapps_paths['linux']:
            return 'linux'
        elif self.steamapps_path in steamapps_paths['windows']:
            return 'windows'
        else:
            raise ValueError("Can't find %s in %s"
                             % (self.steamapps_path, steamapps_paths))

    def get_runner_name(self):
        platform = self.get_platform()
        if platform == 'linux':
            return 'steam'
        else:
            return 'winesteam'


def get_steamapps_paths(flat=False):
    from lutris.runners import winesteam, steam
    if flat:
        steamapps_paths = []
    else:
        steamapps_paths = {
            'linux': [],
            'windows': []
        }
    winesteam_runner = winesteam.winesteam()
    steam_runner = steam.steam()
    for folder in steam_runner.get_steamapps_dirs():
        if flat:
            steamapps_paths.append(folder)
        else:
            steamapps_paths['linux'].append(folder)
    for folder in winesteam_runner.get_steamapps_dirs():
        if flat:
            steamapps_paths.append(folder)
        else:
            steamapps_paths['windows'].append(folder)
    return steamapps_paths


def get_appmanifest_from_appid(steamapps_path, appid):
    """Given the steam apps path and appid, return the corresponding appmanifest"""
    if not steamapps_path:
        raise ValueError("steamapps_path is mandatory")
    if not os.path.exists(steamapps_path):
        raise IOError("steamapps_path must be a valid directory")
    if not appid:
        raise ValueError("Missing mandatory appid")
    appmanifest_path = os.path.join(steamapps_path, "appmanifest_%s.acf" % appid)
    if not os.path.exists(appmanifest_path):
        return
    return AppManifest(appmanifest_path)


def get_path_from_appmanifest(steamapps_path, appid):
    """Return the path where a Steam game is installed."""
    appmanifest = get_appmanifest_from_appid(steamapps_path, appid)
    if not appmanifest:
        return
    return appmanifest.get_install_path()


def mark_as_installed(steamid, runner_name, game_info):
    for key in ['name', 'slug']:
        assert game_info[key]
    logger.info("Setting %s as installed" % game_info['name'])
    config_id = (game_info.get('config_path') or make_game_config_id(game_info['slug']))
    game_id = pga.add_or_update(
        steamid=int(steamid),
        name=game_info['name'],
        runner=runner_name,
        slug=game_info['slug'],
        installed=1,
        configpath=config_id,
    )

    game_config = LutrisConfig(
        runner_slug=runner_name,
        game_config_id=config_id,
    )
    game_config.raw_game_config.update({'appid': steamid})
    game_config.save()
    return game_id


def mark_as_uninstalled(game_info):
    assert 'id' in game_info
    assert 'name' in game_info
    logger.info('Setting %s as uninstalled' % game_info['name'])
    game_id = pga.add_or_update(
        id=game_info['id'],
        runner='',
        installed=0
    )
    return game_id


def sync_with_lutris():
    steamapps_paths = get_steamapps_paths()
    steam_games_in_lutris = pga.get_steam_games()
    steamids_in_lutris = set([str(game['steamid']) for game in steam_games_in_lutris])
    seen_ids = set()
    for platform in steamapps_paths:
        for steamapps_path in steamapps_paths[platform]:
            appmanifests = get_appmanifests(steamapps_path)
            for appmanifest_file in appmanifests:
                steamid = re.findall(r'(\d+)', appmanifest_file)[0]
                seen_ids.add(steamid)
                game_info = None
                if steamid not in steamids_in_lutris and platform == 'linux':
                    appmanifest_path = os.path.join(steamapps_path, appmanifest_file)
                    try:
                        appmanifest = AppManifest(appmanifest_path)
                    except Exception:
                        logger.error("Unable to parse file %s", appmanifest_path)
                        continue
                    if appmanifest.is_installed():
                        game_info = {
                            'name': appmanifest.name,
                            'slug': appmanifest.slug,
                        }
                        mark_as_installed(steamid, 'steam', game_info)
                else:
                    for game in steam_games_in_lutris:
                        if str(game['steamid']) == steamid and not game['installed']:
                            game_info = game
                            break
                    if game_info:
                        appmanifest_path = os.path.join(steamapps_path, appmanifest_file)
                        try:
                            appmanifest = AppManifest(appmanifest_path)
                        except Exception:
                            logger.error("Unable to parse file %s", appmanifest_path)
                            continue
                        if appmanifest.is_installed():
                            runner_name = appmanifest.get_runner_name()
                            mark_as_installed(steamid, runner_name, game_info)
    unavailable_ids = steamids_in_lutris.difference(seen_ids)
    for steamid in unavailable_ids:
        for game in steam_games_in_lutris:
            if str(game['steamid']) == steamid \
               and game['installed'] \
               and game['runner'] in ('steam', 'winesteam'):
                mark_as_uninstalled(game)
