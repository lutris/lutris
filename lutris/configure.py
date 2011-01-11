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

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from lutris.gconfwrapper import GconfWrapper
    GCONF_CAPABLE = True
except GConfBindingsUnavailable:
    GCONF_CAPABLE = False

def register_lutris_handler():
    if not GCONF_CAPABLE:
        print "Can't find gconf bindings"
        return
    gconf = GconfWrapper()
    defaults = (('/desktop/gnome/url-handlers/lutris/command', "lutris '%s'"),
                ('/desktop/gnome/url-handlers/lutris/enabled', True),
                ('/desktop/gnome/url-handlers/lutris/needs-terminal', False),)

    for key, value in defaults:
        if not gconf.has_key(key):
            gconf.set_key(key, value, override_type = True)

if __name__ == '__main__':
    register_lutris_handler()

