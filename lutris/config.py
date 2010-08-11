# -*- coding:Utf-8 -*-
###############################################################################
## Lutris
##
## Copyright (C) 2009 Mathieu Comandon strycore@gmail.com
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

import yaml
import os
import logging
import lutris.constants as constants

class LutrisConfig():
    def __init__(self, runner = None, game = None):
        #Check if configuration directories exists and create them if needed.
        config_paths = [
            constants.lutris_config_path,
            constants.runner_config_path,
            constants.game_config_path,
            constants.cover_path,
            constants.tmp_path,
            constants.cache_path
        ]
        for config_path in config_paths:
            if not os.path.exists(config_path):
                os.mkdir(config_path)

        #Initialize configuration
        self.config = {}
        self.game_config = {}
        self.runner_config = {}
        self.system_config = {}

        self.game = None
        self.runner = None

        #By default config type is system, it can also be runner and game
        #this means that when you call lutris_config_instance["key"] is will
        #pick up the right configuration depending of config_type
        self.config_type = "system"
        if runner:
            self.runner = runner
            self.config_type = "runner"
        elif game:
            self.game = game
            self.config_type = "game"

        #Read system configuration
        if os.path.exists(constants.system_config_full_path):
            self.system_config = yaml.load(file(constants.system_config_full_path, 'r').read())
            if self.system_config is None:
                self.system_config = {}
        else:
            file(constants.system_config_full_path, "w+")

        if self.game:
            game_config_full_path = os.path.join(constants.game_config_path,
                                                 self.game + constants.config_extension)
            if os.path.exists(game_config_full_path):
                try:
                    self.game_config = yaml.load(file(game_config_full_path, 'r').read())
                    self.runner = self.game_config["runner"]
                except yaml.scanner.ScannerError:
                    logging.debug("error parsing config file %s" % game_config_full_path)
                except KeyError:
                    logging.debug("Runner key is mandatory !")

        if self.runner:
            runner_config_full_path = os.path.join(constants.runner_config_path,
                                                   self.runner + constants.config_extension)
            if os.path.exists(runner_config_full_path):
                self.runner_config = yaml.load(file(runner_config_full_path, 'r').read())
        self.update_global_config()

    def __getitem__(self, key):
        """Allows to access config data directly by keys"""
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

    def remove(self, game_name):
        logging.debug("removing %s" % game_name)
        os.remove(os.path.join(constants.game_config_path, game_name + constants.config_extension))

    def save(self, type = None):
        """Save configuration file
        The way to save config files can be set by the type argument
        or with self.config_type"""

        self.update_global_config()
        logging.debug("Saving config (type %s)" % type)
        logging.debug(self.config)
        if type is None:
            type = self.config_type
        yaml_config = yaml.dump(self.config, default_flow_style = False)

        if type == "system":
            file(constants.system_config_full_path, "w").write(yaml_config)
        elif type == "runner":
            runner_config_path = os.path.join(constants.runner_config_path, self.runner + constants.config_extension)
            file(runner_config_path, "w").write(yaml_config)
        elif type == "game":
            if not self.game:
                self.game = self.config["runner"] + "-" + self.config["realname"].replace(" ", "_")
            self.game_config_path = os.path.join(constants.game_config_path,
                                                 self.game.replace('/', '_') + constants.config_extension)
            config_file = file(self.game_config_path, "w")
            config_file.write(yaml_config)
            return self.game
        else:
            print "Config type is %s or %s" % (self.config_type, type)
            print "i don't know how to save this yet"


    def get_path(self, runner = None, default = None):
        """Gets the path to install games for a given runner"""

        if "system" in self.config:
            if "game_path" in self.config["system"]:
                return self.config["system"]["game_path"]
        logging.debug("Fail !")
        return os.path.expanduser("~")

if  __name__ == "__main__":
    logging.basicConfig(level = logging.DEBUG)
    logging.debug('logging enabled')
    lc = LutrisConfig(runner = "wine")
    print "system config : "
    print lc.system_config
    print "runner config : "
    print lc.runner_config
    print "global config"
    print lc.config

    print ("*****************")
    print ("* testing games *")
    print ("*****************")

    lc = LutrisConfig(game = "wine-Ghostbusters")
    print "system config : "
    print lc.system_config
    print ("-----------------------")
    print "runner config : "
    print lc.runner_config
    print ("-----------------------")
    print "game config :"
    print lc.game_config
    print ("-----------------------")
    print "global config"
    print lc.config


