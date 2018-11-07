import os
import time

from collections import OrderedDict
from gi.repository import GLib, Gio
from lutris.util.log import logger
from lutris.util import system


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
        try:
            line = steam_config_file.readline()
        except UnicodeDecodeError:
            logger.error("Error while reading Steam VDF file %s. Returning %s", steam_config_file, config)
            return config
        if not line or line.strip() == "}":
            return config
        while not line.strip().endswith("\""):
            nextline = steam_config_file.readline()
            if not nextline:
                break
            line = line[:-1] + nextline

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
    if not system.path_exists(config_filename):
        return None
    with open(config_filename, "r") as steam_config_file:
        config = vdf_parse(steam_config_file, {})
    try:
        config = config['InstallConfigStore']['Software']['Valve']['Steam']
    except KeyError as e:
        logger.error("Steam config %s is empty: %s", config_filename, e)
        return None
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
        self.callback(event_type, path)
