"""Utility functions for YAML handling"""

import os

# pylint: disable=no-member
import yaml

from lutris.util.log import logger
from lutris.util.system import path_exists


def read_yaml_from_file(filename: str) -> dict:
    """Read filename and return parsed yaml"""
    if not path_exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as yaml_file:
        try:
            yaml_content = yaml.safe_load(yaml_file) or {}
        except (yaml.scanner.ScannerError, yaml.parser.ParserError):
            logger.error("error parsing file %s", filename)
            yaml_content = {}
    return yaml_content


def write_yaml_to_file(config: dict, filepath: str) -> None:
    yaml_config = yaml.safe_dump(config, default_flow_style=False)

    temp_path = filepath + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as filehandler:
            filehandler.write(yaml_config)
        os.rename(temp_path, filepath)
    finally:
        if os.path.isfile(temp_path):
            os.unlink(temp_path)
