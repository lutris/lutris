# -*- coding:Utf-8 -*-
"""Settings module"""
import os
import sys
from xdg import BaseDirectory
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = "0.3.2"
COPYRIGHT = "(c) 2010-2014 Lutris Gaming Platform"
AUTHORS = ["Mathieu Comandon <strycore@gmail.com>"]
ARTISTS = ["Ludovic Soulié <contact@ludal.net>"]

## Paths
CONFIG_DIR = os.path.join(BaseDirectory.xdg_config_home, 'lutris')
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
DATA_DIR = os.path.join(BaseDirectory.xdg_data_home, 'lutris')
RUNNER_DIR = os.path.join(DATA_DIR, "runners")
CACHE_DIR = os.path.join(BaseDirectory.xdg_cache_home, 'lutris')

TMP_PATH = os.path.join(CACHE_DIR, 'tmp')

sio = SettingsIO(CONFIG_FILE)
PGA_DB = sio.read_setting('pga_path') or os.path.join(DATA_DIR, 'pga.db')
SITE_URL = sio.read_setting("website") or "http://lutris.net/"

INSTALLER_URL = SITE_URL + "games/install/"
RUNNERS_URL = SITE_URL + "files/runners/"
LIB32_URL = SITE_URL + "files/lib32/"
LIB64_URL = SITE_URL + "files/lib64/"

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

## Default config options
KEEP_CACHED_ASSETS = True


read_setting = sio.read_setting
write_setting = sio.write_setting
