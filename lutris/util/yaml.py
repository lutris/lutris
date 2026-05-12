"""Utility functions for YAML handling"""

import os
import tempfile
from typing import Any

import yaml
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from lutris.util.log import logger
from lutris.util.system import path_exists


def read_yaml_from_file(filename: str) -> dict[str, Any]:
    """Read filename and return parsed yaml"""
    if not path_exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as yaml_file:
        try:
            yaml_content = yaml.safe_load(yaml_file) or {}
        except (ScannerError, ParserError):
            logger.error("error parsing file %s", filename)
            yaml_content = {}
    return yaml_content


def write_yaml_to_file(config: dict[str, Any], filepath: str) -> None:
    yaml_config = yaml.safe_dump(config, default_flow_style=False)

    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(yaml_config)
        os.replace(temp_path, filepath)
    finally:
        if os.path.isfile(temp_path):
            os.unlink(temp_path)
