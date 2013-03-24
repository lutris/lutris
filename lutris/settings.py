# -*- coding:Utf-8 -*-
"""Settings module"""
import os
import sys
from xdg import BaseDirectory

PROJECT = "Lutris"
VERSION = "0.2.8"
WEBSITE = "http://lutris.net"
COPYRIGHT = "(c) 2010 Lutris Gaming Platform"
AUTHORS = ["Mathieu Comandon <strycore@gmail.com>"]
ARTISTS = ["Ludovic Soulié <contact@ludal.net>"]

SITE_URL = "http://dev.lutris.net/"
INSTALLER_URL = SITE_URL + "games/install/"
BANNER_URL = SITE_URL + "media/games/banners/"
ICONS_URL = SITE_URL + "media/games/icons/"


CONFIG_DIR = os.path.join(BaseDirectory.xdg_config_home, 'lutris')
DATA_DIR = os.path.join(BaseDirectory.xdg_data_home, 'lutris')
CACHE_DIR = os.path.join(BaseDirectory.xdg_cache_home, 'lutris')

PGA_DB = os.path.join(DATA_DIR, 'pga.db')

LICENSE_TEXT = """
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


def get_data_path():
    """docstring for get_data_path"""
    launch_path = os.path.realpath(sys.path[0])
    if launch_path.startswith("/usr/local"):
        data_path = '/usr/local/share/lutris'
    elif launch_path.startswith("/usr"):
        data_path = '/usr/share/lutris'
    elif os.path.exists(os.path.normpath(os.path.join(sys.path[0], 'data'))):
        data_path = os.path.normpath(os.path.join(sys.path[0], 'data'))
    else:
        import lutris
        data_path = os.path.dirname(lutris.__file__)
    if not os.path.exists(data_path):
        print("data_path can't be found at : %s" % data_path)
        exit()
    return data_path
