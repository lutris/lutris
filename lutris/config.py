#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Handle the basic configuration of Lutris."""

import os
import sys
import yaml
import logging
from os.path import join

from gi.repository import Gio

from lutris import pga
from lutris.util.log import logger
from lutris.util.strings import slugify
from lutris.settings import PGA_DB, CONFIG_DIR, DATA_DIR, CACHE_DIR


def register_handler():
    """ Register the lutris: protocol to open with the application. """
    logger.debug("registering protocol")
    executable = os.path.abspath(sys.argv[0])
    base_key = "desktop.gnome.url-handlers.lutris"
    schema_directory = "/usr/share/glib-2.0/schemas/"
    schema_source = Gio.SettingsSchemaSource.new_from_directory(
        schema_directory, None, True
    )
    schema = schema_source.lookup(base_key, True)
    if schema:
        settings = Gio.Settings.new(base_key)
        settings.set_string('command', executable)
    else:
        logger.warning("Schema not installed, cannot register url-handler")


def check_config(force_wipe=False):
    """Check if initial configuration is correct."""
    directories = [CONFIG_DIR,
                   join(CONFIG_DIR, "runners"),
                   join(CONFIG_DIR, "games"),
                   DATA_DIR,
                   join(DATA_DIR, "covers"),
                   join(DATA_DIR, "icons"),
                   join(DATA_DIR, "banners"),
                   join(DATA_DIR, "runners"),
                   join(DATA_DIR, "lib"),
                   CACHE_DIR,
                   join(CACHE_DIR, "installer"),
                   join(CACHE_DIR, "tmp")]
    for directory in directories:
        if not os.path.exists(directory):
            logger.debug("creating directory %s" % directory)
            os.mkdir(directory)

    if force_wipe:
        os.remove(PGA_DB)
    pga.syncdb()


def read_yaml_from_file(filename):
    """Read filename and return parsed yaml"""
    if not os.path.exists(filename):
        return {}
    try:
        content = file(filename, 'r').read()
        yaml_content = yaml.load(content) or {}
    except (yaml.scanner.ScannerError, yaml.parser.ParserError):
        logger.error("error parsing file %s", filename)
        yaml_content = {}
    return yaml_content


class LutrisConfig(object):
    """Class where all the configuration handling happens.

    Lutris configuration uses a cascading mecanism where
    each higher, more specific level override the lower ones.

    The config files are stored in a YAML format and are easy to edit manually.

    """
    def __init__(self, runner=None, game=None):
        #Initialize configuration
        self.config = {'system': {}}
        self.game_config = {}
        self.runner_config = {}
        self.system_config = {}

        self.game = None
        self.runner = None

        #By default config type is system, it can also be runner and game
        #this means that when you call lutris_config_instance["key"] it will
        #pick up the right configuration depending of config_type
        if game:
            self.game = game
            self.config_type = "game"
        elif runner:
            self.runner = runner
            self.config_type = "runner"
        else:
            self.config_type = "system"

        #Read system configuration
        self.system_config = read_yaml_from_file(join(CONFIG_DIR,
                                                      "system.yml"))
        if runner:
            self.runner_config = read_yaml_from_file(join(CONFIG_DIR,
                                                          "runners/%s.yml"
                                                          % runner))
        else:
            self.runner_config = {}
        if self.game:
            game_config_path = join(CONFIG_DIR, "games/%s.yml" % self.game)
            if os.path.exists(game_config_path):
                self.game_config = read_yaml_from_file(game_config_path)
                self.runner = self.game_config.get("runner")
        self.update_global_config()

    def __str__(self):
        return str(self.config)

    def __getitem__(self, key, default=None):
        """Allow to access config data directly by keys."""
        if key in ('game', 'runner', 'system'):
            return self.config[key]
        try:
            if self.config_type == "game":
                value = self.game_config[key]
            elif self.config_type == "runner":
                value = self.runner_config[key]
            else:
                value = self.system_config[key]
        except KeyError:
            value = default
        return value

    def __setitem__(self, key, value):
        if self.config_type == "game":
            self.game_config[key] = value
        elif self.config_type == "runner":
            self.runner_config[key] = value
        elif self.config_type == "system":
            self.system_config = value
        self.update_global_config()

    def get(self, key, default=None):
        return self.__getitem__(key)

    @property
    def game_config_file(self):
        return join(CONFIG_DIR, "games/%s.yml" % self.game)

    def get_system(self, key):
        """Return the value of 'key' for system config"""
        try:
            value = self.config["system"][key]
            if str(value).lower() in ("false", "none", "no"):
                value = False
        except KeyError:
            value = None
        return value

    def update_global_config(self):
        """Update the global config dict."""
        for key in self.system_config.keys():
            if key in self.config:
                self.config[key].update(self.system_config[key])
            else:
                self.config[key] = self.system_config[key]

        for key in self.runner_config.keys():
            if key in self.config:
                self.config[key].update(self.runner_config[key])
            else:
                self.config[key] = self.runner_config[key]

        for key in self.game_config.keys():
            if key in self.config:
                if type(self.config[key]) is dict:
                    self.config[key].update(self.game_config[key])
            else:
                self.config[key] = self.game_config[key]

    def get_name(self):
        """Return name of game"""
        name = self.config["realname"]
        return name

    def remove(self, game=None):
        """Delete the configuration file from disk."""
        if game is None:
            game = self.game
        logging.debug("removing config for %s", game)
        if os.path.exists(self.game_config_file):
            os.remove(self.game_config_file)
        else:
            logger.debug("No config file at %s" % self.game_config_file)

    def is_valid(self):
        """Check the config data and return True if config is ok."""
        return "runner" in self.game_config

    def save(self, config_type=None):
        """Save configuration file

        The way to save config files can be set by the type argument
        or with self.config_type
        """

        self.update_global_config()
        logging.debug("Saving config (type %s)", config_type)
        logging.debug(self.config)
        if config_type is None:
            config_type = self.config_type
        yaml_config = yaml.dump(self.config, default_flow_style=False)

        if config_type == "system":
            filename = join(CONFIG_DIR, "system.yml")
            self.write_to_disk(filename, yaml_config)
        elif config_type == "runner":
            runner_config_path = join(CONFIG_DIR,
                                      "runners/%s.yml" % self.runner)
            self.write_to_disk(runner_config_path, yaml_config)

        elif config_type == "game":
            if not self.game:
                self.game = slugify(self.config['realname'])
            self.write_to_disk(self.game_config_file, yaml_config)
            return self.game
        else:
            print("Config type is %s or %s" % (self.config_type, type))
            print("i don't know how to save this yet")

    def write_to_disk(self, filepath, content):
        with open(filepath, "w") as filehandler:
            filehandler.write(content)

    def get_path(self, default=None):
        """Get the path to install games for a given runner.

        Return False if it can't find an installation path
        """

        if "system" in self.config and "game_path" in self.config["system"]:
            return self.config["system"]["game_path"]
        if not default or not os.path.exists(default):
            return False
        else:
            return default
