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
    def __init__(self,runner=None,game=None):
        #Check if configuration directories exists and create them if needed.
        config_paths = [constants.lutris_config_path, \
                        constants.runner_config_path, \
                        constants.game_config_path, \
                        constants.cover_path, \
                        constants.tmp_path ]
        for config_path in config_paths:
            if not os.path.exists(config_path):
                os.mkdir(config_path)

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

        #Check if system configuration file exists.
        self.system_config = None
        if os.path.exists(constants.system_config_full_path):
            self.system_config = yaml.load(file(constants.system_config_full_path, 'r').read())
        else:
            #Create empty configuration file
            file(constants.system_config_full_path,"w+")

        if not self.system_config:
            self.system_config = {}

        #Initialize configuration directory
        self.config = {}

        #A bit tricky here,if we have a game argument but no runner, we will
        #still need to get the runner from the game configuration. We have to
        #load runner info after the game config but have to merge the runner
        #config before the game's. If you give both game and runner args, the
        #runner arg will get ignored
        self.game_identifier = None
        if game:
            self.game_identifier = game
            game_config_full_path = os.path.join(constants.game_config_path,game+constants.config_extension)
            if os.path.exists(game_config_full_path):
                
                try:
                    self.game_config = yaml.load(file(game_config_full_path,'r').read())
                    runner = self.game_config["runner"]
                except yaml.scanner.ScannerError:
                    print "error parsing "+game_config_full_path
                except KeyError:
                    print "Runner key is mandatory !"
            else:
                self.game_config = {}
        else:
            self.game_config = {}
        self.config.update(self.game_config)
        if runner:
            runner_config_full_path = os.path.join(constants.runner_config_path,runner+constants.config_extension)
            if os.path.exists(runner_config_full_path):
                self.lutris_config = yaml.load(file(runner_config_full_path,'r').read())
            else:
                self.lutris_config = {}
            self.config.update(self.lutris_config)
            if runner in self.game_config:
                self.config[runner].update(self.game_config[runner])
            if "system" in self.config:
                if self.config["system"] is None:
                    self.config["system"] = {}
                self.config["system"].update(self.config["system"])

    def __getitem__(self,key):
        """Allows to access config data directly by keys"""
        if self.config_type == "game":
            value = self.game_config[key]
        elif self.config_type == "runner":
            value = self.lutris_config[key]
        else:
            value = self.system_config[key]
        return value

    def __setitem__(self,key,value):
        if self.config_type == "game":
            self.game_config[key] = value
        elif self.config_type == "runner":
            self.config[self.runner][key] = value
        else:
            if self.config["system"] is None:
                self.config["system"] = {}
            print self.config
            self.config["system"][key] = value
            

    def has_key(self, key, create = False):
        """
        Check is a key is present in the config, keys/can/be/given/in/paths/like/that
        If create is set, the missing keys will be created and always return True
        """
        logging.debug("I dont think this function is useful anymore")
        keys = key.split("/")
        past_keys = ""
        for key in keys:
            generate_key_pointer = "self.lutris_config"+past_keys+".has_key('" +  key + "')"
            logging.debug(generate_key_pointer)
            if not eval(generate_key_pointer):
                if not create:
                    return False
                else:
                    create_key = "self.lutris_config"+past_keys+"['"+key+"'] = {}"
                    exec(create_key)
            past_keys = past_keys + "['" + key + "']"
        return True

    def remove(self,game_name):
        logging.debug("removing %s" % game_name)
        os.remove(os.path.join(constants.game_config_path,game_name+constants.config_extension))

    def save(self,type=None):
        """Save configuration file
        The way to save config files can be set by the type argument
        or with self.config_type"""
        if type is None:
            type = self.config_type
        yaml_config = yaml.dump(self.config,default_flow_style=False)
        print "Saving config (type %s)" % type
        print yaml_config
        if type == "system":
            file(constants.system_config_full_path,"w").write(yaml_config)
        elif type == "runner":
            runner_config_path = os.path.join(constants.runner_config_path,self.runner+constants.config_extension)
            file(runner_config_path,"w").write(yaml_config)
        elif type == "game":
            if not self.game_identifier:
                self.game_identifier = self.config["runner"] + "-" + self.config["realname"].replace(" ","_")
            self.game_config_path = os.path.join(constants.game_config_path,self.game_identifier+constants.config_extension)
            file(self.game_config_path,"w").write(yaml_config)
            return self.game_identifier
        else:
            print "Config type is %s or %s" % (self.config_type, type)
            print "i don't know how to save this yet"
    
    
    def get_path(self,runner):
        if runner in self.config:
            if "game_path" in self.config[runner]:
                return self.config[runner]["game_path"]
        if "game_path" in self.config:
            return self.config["game_path"]
        return os.path.expanduser("~")
