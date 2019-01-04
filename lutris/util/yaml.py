"""Utility functions for YAML handling"""
# pylint: disable=no-member
import yaml

from lutris.util.log import logger
from lutris.util.system import path_exists


def read_yaml_from_file(filename):
    """Read filename and return parsed yaml"""
    if not path_exists(filename):
        return {}

    with open(filename, "r") as yaml_file:
        try:
            yaml_content = yaml.safe_load(yaml_file) or {}
        except (yaml.scanner.ScannerError, yaml.parser.ParserError):
            logger.error("error parsing file %s", filename)
            yaml_content = {}

    return yaml_content


def write_yaml_to_file(filepath, config):
    if not filepath:
        raise ValueError("Missing filepath")
    yaml_config = yaml.dump(config, default_flow_style=False)
    with open(filepath, "w") as filehandler:
        filehandler.write(yaml_config)
