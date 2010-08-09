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
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lutris.gconfwrapper import GconfWrapper

def register_lutris_handler():
    gconf = GconfWrapper()
    defaults = (
        ('/desktop/gnome/url-handlers/lutris/command', "lutris '%s'"),
        ('/desktop/gnome/url-handlers/lutris/enabled', True),
        ('/desktop/gnome/url-handlers/lutris/needs-terminal', False),
    )

    for key, value in defaults:
        if not gconf.has_key(key):
            gconf.set_key(key, value, override_type = True)

if __name__ == '__main__':
    register_lutris_handler()





