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
    """ Given a steam configuration steam, parse the content and return it as
        a dict.
    """
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
    """ Convert a dictionnary to Steam config file format. """
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
    return config['InstallConfigStore']['Software']['Valve']['Steam']


def get_game_data_path(config, appid):
    """ Given a steam config, return path for game 'appid' """
    if not config:
        return False
    game_config = config["apps"].get(appid)
    if not game_config:
        return False
    if game_config.get('HasAllLocalContent'):
        installdir = game_config['installdir'].replace("\\\\", "/")
        if not installdir:
            return False
        if installdir.startswith('C'):
            installdir = os.path.join(os.path.expanduser('~'),
                                      '.wine/drive_c', installdir[3:])
        elif installdir[1] == ':':
            # Trim Windows path
            installdir = installdir[2:]
        logger.debug("Steam game found at %s" % installdir)
        if os.path.exists(installdir):
            return installdir
        elif os.path.exists(installdir.replace('steamapps', 'SteamApps')):
            return installdir.replace('steamapps', 'SteamApps')
        else:
            logger.debug("Path %s not found" % installdir)
    return False
