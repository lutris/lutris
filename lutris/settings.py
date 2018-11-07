# -*- coding:Utf-8 -*-
"""Internal settings."""
import os
from gi.repository import GLib
from lutris.util.settings import SettingsIO

PROJECT = "Lutris"
VERSION = "0.4.23"
COPYRIGHT = "(c) 2010-2018 Lutris Gaming Platform"
AUTHORS = ["Mathieu Comandon <strycore@gmail.com>",
           "Pascal Reinhard (Xodetaetl) <dev@xod.me"]
ARTISTS = ["Ludovic Soulié <contact@ludal.net>"]

# Paths
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), 'lutris')
CONFIG_FILE = os.path.join(CONFIG_DIR, "lutris.conf")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), 'lutris')
RUNNER_DIR = os.path.join(DATA_DIR, "runners")
RUNTIME_DIR = os.path.join(DATA_DIR, "runtime")
CACHE_DIR = os.path.join(GLib.get_user_cache_dir(), 'lutris')
GAME_CONFIG_DIR = os.path.join(CONFIG_DIR, 'games')

TMP_PATH = os.path.join(CACHE_DIR, 'tmp')
BANNER_PATH = os.path.join(DATA_DIR, 'banners')
ICON_PATH = os.path.join(GLib.get_user_data_dir(),
                         'icons', 'hicolor', '32x32', 'apps')

sio = SettingsIO(CONFIG_FILE)
PGA_DB = sio.read_setting('pga_path') or os.path.join(DATA_DIR, 'pga.db')
SITE_URL = sio.read_setting("website") or "https://lutris.net"

INSTALLER_URL = SITE_URL + '/api/installers/%s'
INSTALLER_REVISION_URL = SITE_URL + '/api/installers/games/%s/revisions/%s'
GAME_URL = SITE_URL + '/games/%s/'
ICON_URL = SITE_URL + '/games/icon/%s.png'
BANNER_URL = SITE_URL + '/games/banner/%s.jpg'
RUNTIME_URL = "https://lutris.net/api/runtime"

# Default config options
GAME_VIEW = 'grid'
ICON_TYPE_GRIDVIEW = 'banner'
ICON_TYPE_LISTVIEW = 'icon'

read_setting = sio.read_setting
write_setting = sio.write_setting
