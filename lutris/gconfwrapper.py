# -*- coding:Utf-8 -*-

###############################################################################
## GConfWrapper.py
##
## Copyright (c) 2010 Mathieu Comandon <strycore@gmail.com>
##
## Author: Mathieu Comandon <strycore@gmail.com>
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


import os
import glib
from lutris.exceptions import GConfBindingsUnavailable

try:
    import gconf
except ImportError:
    raise GConfBindingsUnavailable('Install python-gconf')

class GconfWrapper():
    def __init__(self):
        self.gconf_path = os.path.join(os.path.expanduser("~"), ".gconf")
        self.client = gconf.client_get_default ()

    def has_key(self, key):
        key = self.client.get_string(key)
        if key:
            return True
        else:
            return False

    def get_key(self, key):
        try:
            key = self.client.get_string(key)
        except glib.GError, err:
            if "Type mismatch" in err[0]:
                if "got `bool' for key" in err[0]:
                    key = self.client.get_bool(key)
                elif "got `int' for key" in err[0]:
                    key = self.client.get_int(key)
                else:
                    print err
                    raise TypeError, "Wrong type"
        return key

    def get_key_type(self, key):
        value = self.get_key(key)
        return type(value)

    def all_dirs(self, base_dir):
        """The same thing as gconftool --all-dirs <dir>"""
        if base_dir[0] == "/":
            base_dir = base_dir[1:]
        path = os.path.join(self.gconf_path, base_dir)
        dirs = os.listdir(path)
        dirs.remove("%gconf.xml")
        return dirs


    def set_key(self, key, value, override_type = False):
        try:
            success = True
            #Get method according to incoming type
            if isinstance(value, str):
                method = self.client.set_string
            elif isinstance(value, bool):
                method = self.client.set_bool
            elif isinstance(value, int):
                method = self.client.set_int
            else:
                print type(value)
                raise TypeError, "Unknown type"
            if not override_type:
                if not self.get_key_type(key) == type(value):
                    raise TypeError, "Type mismatch: use type_override to force your way or leave it the way it is!"
            method(key, value)
        except Exception, err:
            print err
            success = False
        return success




