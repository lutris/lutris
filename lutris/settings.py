# -*- coding:Utf-8 -*-
"""Settings module"""
import os
import sys
import ConfigParser
from xdg import BaseDirectory

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


def get_config():
    config = ConfigParser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read([CONFIG_FILE])
    return config


def read_setting(key, section='lutris'):
    config = get_config()
    if not config:
        return
    try:
        value = config.get(section, key)
    except ConfigParser.NoOptionError:
        value = None
    except ConfigParser.NoSectionError:
        value = None
    return value


def write_setting(key, value, section='lutris'):
    config = get_config()
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, value)

    with open(CONFIG_FILE, 'wb') as config_file:
        config.write(config_file)

PGA_DB = read_setting('pga_path') or os.path.join(DATA_DIR, 'pga.db')
SITE_URL = read_setting("website") or "http://lutris.net/"

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
