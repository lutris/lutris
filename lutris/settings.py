"""Settings module"""
from os.path import join
from xdg import BaseDirectory

PROJECT = "Lutris"
VERSION = "0.2.7"
WEBSITE = "http://lutris.net"
COPYRIGHT = "(c) 2010 Lutris Gaming Platform"
AUTHORS = ["Mathieu Comandon <strycore@gmail.com>"]
ARTISTS = ["Ludovic Soulié <contact@yudoh.com>"]

CONFIG_DIR = join(BaseDirectory.xdg_config_home, 'lutris')
DATA_DIR = join(BaseDirectory.xdg_data_home, 'lutris')
CACHE_DIR = join(BaseDirectory.xdg_cache_home, 'lutris')

PGA_DB = join(DATA_DIR, 'pga.db')

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
