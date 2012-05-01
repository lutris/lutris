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
""" Constants module, soon to be deprecated. Replaced by settings module. """

from os.path import realpath, normpath, dirname, join, exists, expanduser
from xdg import BaseDirectory
import sys

name = "Lutris"
version = "0.2.6"
website = "http://lutris.net"
protocol_version = 1
INSTALLER_URL = "http://lutris.net/media/installers/"
#installer_prefix = "http://localhost:8000/media/installers/"
CONFIG_EXTENSION = ".yml"
license_id = 'GPL-3'
copyright = "(c) 2010 Lutris Gaming Platform"
authors = ["Mathieu Comandon <strycore@gmail.com>"]
artists = ["Ludovic Soulié <contact@yudoh.com>"]
license_text = """
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

LAUNCH_PATH = realpath(sys.path[0])
if LAUNCH_PATH.startswith('/usr'):
    DATA_PATH = '/usr/share/lutris'
elif exists(normpath(join(sys.path[0], 'data'))):
    DATA_PATH = normpath(join(sys.path[0], 'data'))
else:
    import lutris
    DATA_PATH = dirname(lutris.__file__)
if not exists(DATA_PATH):
    print "DATA_PATH can't be found at : %s" % DATA_PATH
    exit

LUTRIS_ICON = join(DATA_PATH, "media/logo.svg")
LUTRIS_CONFIG_PATH = join(BaseDirectory.xdg_config_home, 'lutris')
LUTRIS_DATA_PATH = join(BaseDirectory.xdg_data_home, 'lutris')
LUTRIS_CACHE_PATH = join(BaseDirectory.xdg_cache_home, 'lutris')

runner_config_path = join(LUTRIS_CONFIG_PATH, 'runners')
GAME_CONFIG_PATH = join(LUTRIS_CONFIG_PATH, 'games')
COVER_PATH = join(LUTRIS_CONFIG_PATH, 'covers')
BANNER_PATH = join(LUTRIS_CONFIG_PATH, 'banners')
ICON_PATH = join(expanduser('~'), '.icons')
TMP_PATH = join(LUTRIS_CACHE_PATH, 'tmp')
