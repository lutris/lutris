import os
import re
import time
import threading
import pyinotify
from lutris.util.log import logger
from collections import OrderedDict
from lutris.util.system import fix_path_case


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


def get_default_acf(appid, name):
    userconfig = OrderedDict()
    userconfig['name'] = name
    userconfig['gameid'] = appid

    appstate = OrderedDict()
    appstate['appID'] = appid
    appstate['Universe'] = "1"
    appstate['StateFlags'] = "1026"
    appstate['installdir'] = name
    appstate['UserConfig'] = userconfig
    return {'AppState': appstate}


def vdf_parse(steam_config_file, config):
    """Parse a Steam config file and return the contents as a dict."""
    line = " "
    while line:
        line = steam_config_file.readline()
        if not line or line.strip() == "}":
            return config
        line_elements = line.strip().split("\"")
        if len(line_elements) == 3:
            key = line_elements[1]
            steam_config_file.readline()  # skip '{'
            config[key] = vdf_parse(steam_config_file, {})
        else:
            config[line_elements[1]] = line_elements[3]
    return config


def to_vdf(dict_data, level=0):
    """Convert a dictionnary to Steam config file format."""
    vdf_data = ""
    for key in dict_data:
        value = dict_data[key]
        if isinstance(value, dict):
            vdf_data += "%s\"%s\"\n" % ("\t" * level, key)
            vdf_data += "%s{\n" % ("\t" * level)
            vdf_data += to_vdf(value, level + 1)
            vdf_data += "%s}\n" % ("\t" * level)
        else:
            vdf_data += "%s\"%s\"\t\t\"%s\"\n" % ("\t" * level, key, value)
    return vdf_data


def vdf_write(vdf_path, config):
    vdf_data = to_vdf(config)
    with open(vdf_path, "w") as vdf_file:
        vdf_file.write(vdf_data)


def read_config(steam_data_dir):
    config_filename = os.path.join(steam_data_dir, 'config/config.vdf')
    if not os.path.exists(config_filename):
        return
    with open(config_filename, "r") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    try:
        config = config['InstallConfigStore']['Software']['Valve']['Steam']
    except KeyError as e:
        logger.debug("Steam config empty: %s" % e)
        return
    else:
        return config


def get_manifest_info(steamapps_path, appid):
    """Given the steam apps path and appid, return the corresponding
    appmanifest info."""
    if not steamapps_path:
        raise ValueError("steamapps_path is mandatory")
    if not os.path.exists(steamapps_path):
        raise IOError("steamapps_path must be a valid directory")
    if not appid:
        raise ValueError("Missing mandatory appid")
    appmanifest_path = os.path.join(steamapps_path,
                                    "appmanifest_%s.acf" % appid)
    if not os.path.exists(appmanifest_path):
        return {}
    with open(appmanifest_path, "r") as appmanifest_file:
        config = vdf_parse(appmanifest_file, {})
    return config


def get_path_from_appmanifest(steamapps_path, appid):
    """Return the path where a Steam game is installed."""
    config = get_manifest_info(steamapps_path, appid)
    if not config:
        return
    installdir = config.get('AppState', {}).get('installdir')
    install_path = fix_path_case(os.path.join(steamapps_path, "common",
                                              installdir))
    if install_path and os.path.exists(install_path):
        return install_path


def get_app_states(steamapps_path, appid):
    """Return the states of a Steam game."""
    states = []
    if not steamapps_path:
        return states
    manifest_info = get_manifest_info(steamapps_path, appid)
    state_flags = manifest_info.get('AppState', {}).get('StateFlags', 0)
    state_flags = bin(int(state_flags))[:1:-1]
    for index, flag in enumerate(state_flags):
        if flag == '1':
            states.append(APP_STATE_FLAGS[index + 1])
    return states


def _get_last_content_log(steam_data_dir):
    """Return the last block from content_log.txt"""
    if not steam_data_dir:
        return []
    path = os.path.join(steam_data_dir, "logs/content_log.txt")
    log = []
    try:
        with open(path, 'r') as f:
            line = f.readline()
            while line:
                # Strip old logs
                if line == "\r\n" and f.readline() == "\r\n":
                    log = []
                    line = f.readline()
                else:
                    log.append(line)
                    line = f.readline()
    except IOError:
        return []
    return log


def get_app_log(steam_data_dir, appid, start_time=None):
    """Return all log entries related to appid from the latest Steam run.

    :param start_time: Time tuple, log entries older than this are dumped.
    """
    if start_time:
        start_time = time.strftime('%Y-%m-%d %T', start_time)

    app_log = []
    for line in _get_last_content_log(steam_data_dir):
        if start_time and line[1:20] < start_time:
            continue
        if " %s " % appid in line[22:]:
            app_log.append(line)
    return app_log


def get_app_state_log(steam_data_dir, appid, start_time=None):
    """Return state entries for appid from latest block in content_log.txt.

    "Fully Installed, Running" means running.
    "Fully Installed" means stopped.

    :param start_time: Time tuple, log entries older than this are dumped.
    """
    state_log = []
    for line in get_app_log(steam_data_dir, appid, start_time):
        line = line.split(' : ')
        if len(line) == 1:
            continue
        if line[0].endswith("state changed"):
            state_log.append(line[1][:-2])
    return state_log


def get_appmanifests(steamapps_path):
    """Return the list for all appmanifest files in a Steam library folder"""
    return [f for f in os.listdir(steamapps_path)
            if re.match(r'^appmanifest_\d+.acf$', f)]


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


class SteamWatchHandler(pyinotify.ProcessEvent):
    def process_IN_MODIFY(self, event):
        path = event.pathname
        if not path.endswith('.acf'):
            return
        logger.info('MODIFY %s', path)

    def process_IN_CREATE(self, event):
        path = event.pathname
        if not path.endswith('.acf'):
            return
        logger.info('CREATE %s', path)

    def process_IN_DELETE(self, event):
        path = event.pathname
        if not path.endswith('.acf'):
            return
        logger.info('DELETE %s', path)


class SteamWatcher(threading.Thread):
    def __init__(self, steamapps_paths):
        self.steamapps_paths = steamapps_paths
        super(SteamWatcher, self).__init__()
        self.start()

    def run(self):
        watch_manager = pyinotify.WatchManager()
        event_handler = SteamWatchHandler()
        mask = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
        notifier = pyinotify.Notifier(watch_manager, event_handler)
        logger.info(self.steamapps_paths)
        for steamapp_path in self.steamapps_paths:
            logger.info('Watching Steam folder %s', steamapp_path)
            watch_manager.add_watch(steamapp_path, mask, rec=True)
        notifier.loop()


class AppManifest:
    def __init__(self, appmanifest_path):
        filename = os.path.basename(appmanifest_path)
        self.steamid = re.findall(r'(\d+)', filename)[0]
        with open(appmanifest_path, "r") as appmanifest_file:
            self.appmanifest_data = vdf_parse(appmanifest_file, {})

    @property
    def app_state(self):
        return self.appmanifest_data.get('AppState') or {}

    @property
    def name(self):
        return self.app_state.get('name')

    @property
    def is_installed(self):
        last_owner = self.appstate.get('LastOwner') or '0'
        return last_owner != '0'
