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

from os.path import join, expanduser
from xdg import BaseDirectory

PROTOCOL_VERSION = 1
CONFIG_EXTENSION = ".yml"


LUTRIS_CONFIG_PATH = join(BaseDirectory.xdg_config_home, 'lutris')
LUTRIS_DATA_PATH = join(BaseDirectory.xdg_data_home, 'lutris')
LUTRIS_CACHE_PATH = join(BaseDirectory.xdg_cache_home, 'lutris')

RUNNER_CONFIG_PATH = join(LUTRIS_CONFIG_PATH, 'runners')
GAME_CONFIG_PATH = join(LUTRIS_CONFIG_PATH, 'games')
COVER_PATH = join(LUTRIS_CONFIG_PATH, 'covers')
BANNER_PATH = join(LUTRIS_CONFIG_PATH, 'banners')
ICON_PATH = join(expanduser('~'), '.icons')
TMP_PATH = join(LUTRIS_CACHE_PATH, 'tmp')
