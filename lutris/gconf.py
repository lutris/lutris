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
""" Convinience wrapper around the GConf module. """
import os
import subprocess
from gi.repository import GConf

from lutris.util.log import logger


class GConfSetting(object):
    """ GConf wrapper class. """
    def __init__(self, key, _type):
        self._key = key
        self._type = _type

        assert(self._type in (str, bool))

        self._client = GConf.Client.get_default()
        self._cmd_cache = {}

        self.gconf_path = os.path.join(os.path.expanduser("~"), ".gconf")
        self.client = GConf.Client()

    def get_value(self):
        if self._type == bool:
            return self._client.get_bool(self._key)
        elif self._type == str:
            return self._client.get_string(self._key)
        else:
            raise TypeError

    def _run_gconftool(self, command):
        if command not in self._cmd_cache:
            p = subprocess.Popen(
                ["gconftool-2", command, self._key],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)
            stdout, stderr = p.communicate()
            if p.returncode == 0:
                self._cmd_cache[command] = stdout.strip()
            else:
                self._cmd_cache[command] = "ERROR: %s" % stderr.strip()

        logger.debug("Caching gconf: %s (%s)" % (self, command))
        return self._cmd_cache[command]

    def schema_get_summary(self):
        return self._run_gconftool("--short-docs") or \
                self._key.split("/")[-1].replace("_", " ").title()

    def schema_get_description(self):
        return self._run_gconftool("--long-docs")

    def schema_get_all(self):
        return {"summary": self.schema_get_summary(),
                "description": self.schema_get_description()}

    def set_value(self, value):
        logger.debug("Change: %s -> %s", self._key, value)

        if self._type == bool:
            self._client.set_bool(self._key, value)
        elif self._type == str:
            self._client.set_string(self._key, value)
        else:
            raise TypeError

    def set_key(self, key, value, override_type=False):
        """ Sets the GConf key to value. """
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
