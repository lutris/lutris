"""Read and write VDF files"""
from lutris.util.log import logger


def vdf_parse(steam_config_file, config):
    """Parse a Steam config file and return the contents as a dict."""
    line = " "
    while line:
        try:
            line = steam_config_file.readline()
        except UnicodeDecodeError:
            logger.error(
                "Error while reading Steam VDF file %s. Returning %s",
                steam_config_file,
                config,
            )
            return config
        if not line or line.strip() == "}":
            return config
        while not line.strip().endswith('"'):
            nextline = steam_config_file.readline()
            if not nextline:
                break
            line = line[:-1] + nextline

        line_elements = line.strip().split('"')
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
    """Convert a dictionnary to Steam config file format"""
    vdf_data = ""
    for key in dict_data:
        value = dict_data[key]
        if isinstance(value, dict):
            vdf_data += '%s"%s"\n' % ("\t" * level, key)
            vdf_data += "%s{\n" % ("\t" * level)
            vdf_data += to_vdf(value, level + 1)
            vdf_data += "%s}\n" % ("\t" * level)
        else:
            vdf_data += '%s"%s"\t\t"%s"\n' % ("\t" * level, key, value)
    return vdf_data


def vdf_write(vdf_path, config):
    """Write a Steam configuration to a vdf file"""
    vdf_data = to_vdf(config)
    with open(vdf_path, "w") as vdf_file:
        vdf_file.write(vdf_data)
