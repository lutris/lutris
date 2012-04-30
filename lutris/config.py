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
import yaml
import logging
from os.path import join

import lutris.pga as pga
import lutris.constants as constants

from lutris.util import log
from lutris.gconfwrapper import GconfWrapper
from lutris.settings import PGA_DB, CONFIG_DIR, DATA_DIR, CACHE_DIR
from lutris.constants import GAME_CONFIG_PATH


def register_handler():
    gconf = GconfWrapper()
    defaults = (('/desktop/gnome/url-handlers/lutris/command', "lutris '%s'"),
                ('/desktop/gnome/url-handlers/lutris/enabled', True),
                ('/desktop/gnome/url-handlers/lutris/needs-terminal', False),)

    for key, value in defaults:
        log.logger.debug("registering gconf key %s" % key)
        gconf.set_key(key, value, override_type=True)


def check_config(force_wipe=False):
    """Check if initial configuration is correct."""
    directories = [CONFIG_DIR,
                   CACHE_DIR,
                   DATA_DIR,
                   join(CONFIG_DIR, "runners"),
                   join(CONFIG_DIR, "games"),
                   join(DATA_DIR, "covers"),
                   join(DATA_DIR, "icons"),
                   join(DATA_DIR, "banners"),
                   join(CACHE_DIR, "installer")]
    if not os.path.exists(CONFIG_DIR) or force_wipe:
        first_run = True
    else:
        first_run = False
    for directory in directories:
        if not os.path.exists(directory):
            log.logger.debug("creating directory %s" % directory)
            os.mkdir(directory)

    if force_wipe:
        os.remove(PGA_DB)

    if not os.path.isfile(PGA_DB) or force_wipe:
        log.logger.debug("creating PGA database in %s" % PGA_DB)

        pga.create()
    if first_run:
        register_handler


class LutrisConfig():
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
        #this means that when you call lutris_config_instance["key"] is will
        #pick up the right configuration depending of config_type
        if runner:
            self.runner = runner
            self.config_type = "runner"
        elif game:
            self.game = game
            self.config_type = "game"
        else:
            self.config_type = "system"

        #Read system configuration
        if os.path.exists(constants.system_config_full_path):
            content = file(constants.system_config_full_path, 'r').read()
            self.system_config = yaml.load(content)
            if self.system_config is None:
                self.system_config = {}
        else:
            file(constants.system_config_full_path, "w+")

        if self.game:
            game_config_full_path = join(GAME_CONFIG_PATH,
                                         self.game + ".yml")
            if os.path.exists(game_config_full_path):
                try:
                    content = file(game_config_full_path, 'r').read()
                    self.game_config = yaml.load(content)
                    self.runner = self.game_config["runner"]
                except yaml.scanner.ScannerError:
                    logging.debug("error parsing config file %s",
                                  game_config_full_path)
                except yaml.parser.ParserError:
                    logging.debug("error parsing config file %s",
                                  game_config_full_path)
                except KeyError:
                    logging.debug("Runner key is mandatory !")

        if self.runner:
            runner_config_full_path = join(constants.runner_config_path,
                                           self.runner + ".yml")
            if os.path.exists(runner_config_full_path):
                yaml_content = file(runner_config_full_path, 'r').read()
                self.runner_config = yaml.load(yaml_content)
        self.update_global_config()

    def __getitem__(self, key):
        """Allow to access config data directly by keys."""
        if self.config_type == "game":
            value = self.game_config[key]
        elif self.config_type == "runner":
            value = self.runner_config[key]
        else:
            value = self.system_config[key]
        return value

    def __setitem__(self, key, value):
        if self.config_type == "game":
            self.game_config[key] = value
        elif self.config_type == "runner":
            self.runner_config[key] = value
        elif self.config_type == "system":
            self.system_config = value
        self.update_global_config()

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

    def get_real_name(self):
        """Return the real name of a game."""

        return self.config["realname"]

    def remove(self, game_name):
        """Delete the configuration file from disk."""

        logging.debug("removing %s", game_name)
        os.remove(join(GAME_CONFIG_PATH,
                       game_name + ".yml"))

    def is_valid(self):
        """Check the config data and return True if config is ok."""

        if "runner" in self.game_config:
            return True
        else:
            print "Error in %s config file : No runner" % self.game
            return False

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
            file(constants.system_config_full_path, "w").write(yaml_config)
        elif config_type == "runner":
            runner_config_path = join(constants.runner_config_path,
                                      self.runner + ".yml")
            file(runner_config_path, "w").write(yaml_config)
        elif config_type == "game":
            if not self.game:
                self.game = self.config["runner"] \
                        + "-" + self.config["realname"].replace(" ", "_")
            game_config_path = join(GAME_CONFIG_PATH,
                                    self.game.replace('/', '_') + ".yml")
            config_file = file(game_config_path, "w")
            config_file.write(yaml_config)
            return self.game
        else:
            print "Config type is %s or %s" % (self.config_type, type)
            print "i don't know how to save this yet"

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
