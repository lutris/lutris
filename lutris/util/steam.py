import os
from lutris.util.log import logger
from collections import OrderedDict


def get_default_acf(appid, name):
    userconfig = OrderedDict()
    userconfig['name'] = name
    userconfig['gameid'] = appid

    appstate = OrderedDict()
    appstate['appID'] = appid
    appstate['Universe'] = "1"
    appstate['StateFlags'] = "4"
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


def read_config(path_prefix):
    config_filename = os.path.join(path_prefix, 'config/config.vdf')
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


def get_steamapps_path(rootdir):
    """Return an existing SteamApps path."""
    if os.path.exists(rootdir):
        return rootdir
    elif os.path.exists(rootdir.replace('steamapps', 'SteamApps')):
        return rootdir.replace('steamapps', 'SteamApps')
    else:
        logger.debug("SteamApps not found in %s" % rootdir)


def get_path_from_appmanifest(steamapps_path, appid):
    if not steamapps_path:
        raise ValueError("steamapps_path is mandatory")
    if not os.path.exists(steamapps_path):
        raise IOError("steamapps_path must be a valid directory")
    if not appid:
        raise ValueError("Missing mandatory appid")
    appmanifest_path = os.path.join(steamapps_path,
                                    "appmanifest_%s.acf" % appid)
    if not os.path.exists(appmanifest_path):
        return

    with open(appmanifest_path, "r") as appmanifest_file:
        config = vdf_parse(appmanifest_file, {})
    installdir = config.get('AppState', {}).get('installdir')
    logger.debug("Game %s should be in %s", appid, installdir)
    install_path = os.path.join(steamapps_path, "common", installdir)
    if installdir and os.path.exists(install_path):
        return install_path
