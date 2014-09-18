# -*- coding:Utf-8 -*-
"""Settings module"""
import os
from xdg import BaseDirectory
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = "0.3.6"
COPYRIGHT = "(c) 2010-2014 Lutris Gaming Platform"
AUTHORS = ["Mathieu Comandon <strycore@gmail.com>"]
ARTISTS = ["Ludovic Soulié <contact@ludal.net>"]

# Paths
CONFIG_DIR = os.path.join(BaseDirectory.xdg_config_home, 'lutris')
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
DATA_DIR = os.path.join(BaseDirectory.xdg_data_home, 'lutris')
RUNNER_DIR = os.path.join(DATA_DIR, "runners")
CACHE_DIR = os.path.join(BaseDirectory.xdg_cache_home, 'lutris')
GAME_CONFIG_DIR = os.path.join(CONFIG_DIR, 'games')

TMP_PATH = os.path.join(CACHE_DIR, 'tmp')
BANNER_PATH = os.path.join(DATA_DIR, 'banners')
ICON_PATH = os.path.join(BaseDirectory.xdg_data_home,
                         'icons/hicolor/32x32/apps')

sio = SettingsIO(CONFIG_FILE)
PGA_DB = sio.read_setting('pga_path') or os.path.join(DATA_DIR, 'pga.db')
SITE_URL = sio.read_setting("website") or "https://lutris.net/"

INSTALLER_URL = SITE_URL + 'games/install/%s/'
ICON_URL = SITE_URL + 'games/icon/%s.png'
BANNER_URL = SITE_URL + 'games/banner/%s.jpg'
RUNNERS_URL = SITE_URL + "files/runners/"
LIB32_URL = SITE_URL + "files/lib32/"
LIB64_URL = SITE_URL + "files/lib64/"

# Default config options
KEEP_CACHED_ASSETS = True
GAME_VIEW = 'grid'
ICON_TYPE_GRIDVIEW = 'banner'
ICON_TYPE_LISTVIEW = 'icon'

read_setting = sio.read_setting
write_setting = sio.write_setting
