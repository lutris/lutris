import os
import re
import time

from gi.repository import GLib, Gio
from collections import OrderedDict
from lutris.util.log import logger


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
            try:
                config[line_elements[1]] = line_elements[3]
            except IndexError:
                logger.error("Malformed config file: %s", line)
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


def set_winesteam_directwrite(prefix_dir, wine_path, enable=True):
    from lutris.runners import wine
    # Since Wine 1.7.50, DirectWrite has been fixed
    wine.set_regedit("HKEY_CURRENT_USER\Software\Valve\Steam",
                     'DWriteEnable', '1' if enable else '0', 'REG_DWORD',
                     wine_path=wine_path,
                     prefix=prefix_dir)


class SteamWatcher:
    def __init__(self, steamapps_paths, callback=None):
        self.monitors = []
        self.callback = callback
        for steam_path in steamapps_paths:
            path = Gio.File.new_for_path(steam_path)
            try:
                monitor = path.monitor_directory(Gio.FileMonitorFlags.NONE)
                logger.debug('Watching Steam folder %s', steam_path)
                monitor.connect('changed', self._on_directory_changed)
                self.monitors.append(monitor)
            except GLib.Error as e:
                logger.exception(e)

    def _on_directory_changed(self, monitor, _file, other_file, event_type):
        path = _file.get_path()
        if not path.endswith('.acf'):
            return
        logger.debug('Detected file change ({}) to {}'.format(
            Gio.FileMonitorEvent(event_type).value_name, path)
        )
        self.callback(event_type, path)
