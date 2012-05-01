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
""" Convinience wrapper around the gconf module. """
import os
import gconf

from glib import GError

from lutris.util.log import logger


class GconfWrapper(object):
    """ Gconf wrapper class. """
    def __init__(self):
        self.gconf_path = os.path.join(os.path.expanduser("~"), ".gconf")
        self.client = gconf.client_get_default()

    def has(self, key):
        """ Test if key exists in gconf. """
        key = self.client.get_string(key)
        if key:
            return True
        else:
            return False

    def get_key(self, key):
        """ Return gconf key. """
        try:
            key = self.client.get_string(key)
        except GError, err:
            if "Type mismatch" in err[0]:
                if "got `bool' for key" in err[0]:
                    key = self.client.get_bool(key)
                elif "got `int' for key" in err[0]:
                    key = self.client.get_int(key)
                else:
                    logger.log.error(err)
                    raise TypeError("Wrong type")
        return key

    def get_key_type(self, key):
        """ Return key's type """
        value = self.get_key(key)
        return type(value)

    def all_dirs(self, base_dir):
        """ The same thing as gconftool --all-dirs <dir> """
        if base_dir[0] == "/":
            base_dir = base_dir[1:]
        path = os.path.join(self.gconf_path, base_dir)
        if os.path.exists(path):
            dirs = os.listdir(path)
            dirs.remove("%gconf.xml")
            return dirs
        else:
            return False

    def set_key(self, key, value, override_type=False):
        """ Sets the gconf key to value. """
        success = True
        #Get method according to incoming type
        if isinstance(value, str):
            method = self.client.set_string
        elif isinstance(value, bool):
            method = self.client.set_bool
        elif isinstance(value, int):
            method = self.client.set_int
        else:
            logger.log("Unknown type for %s" % value)
            raise TypeError
        if not override_type:
            if not self.get_key_type(key) == type(value):
                logger.log.error("Type mismatch for key %s : "\
                                + "use override_type to force your way"\
                                + "or leave it the way it is!" % key)
                raise TypeError
        method(key, value)
        return success
