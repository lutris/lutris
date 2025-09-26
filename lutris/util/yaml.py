"""Utility functions for YAML handling"""

import os

# pylint: disable=no-member
import yaml
from gi.repository import Gtk

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


def save_yaml_as(config: dict, default_name: str) -> None:
    dialog = Gtk.FileChooserNative.new(
        title="Save as", parent=None, action=Gtk.FileChooserAction.SAVE, accept_label="_Save", cancel_label="_Cancel"
    )
    dialog.set_current_name(default_name)
    dialog.set_do_overwrite_confirmation(True)
    _yaml = Gtk.FileFilter()
    _yaml.set_name("YAML files")
    _yaml.add_pattern("*.yaml")
    _yaml.add_pattern("*.yml")
    dialog.add_filter(_yaml)

    try:
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            if file := dialog.get_file():
                write_yaml_to_file(config, file.get_path())
    finally:
        dialog.destroy()
