from os.path import realpath, normpath, dirname, join, exists, expanduser
from xdg import BaseDirectory
import sys

LUTRIS_CONFIG_PATH = join(BaseDirectory.xdg_config_home, 'lutris')
LUTRIS_DATA_PATH = join(BaseDirectory.xdg_data_home, 'lutris')
LUTRIS_CACHE_PATH = join(BaseDirectory.xdg_cache_home, 'lutris')

PGA_PATH = join(LUTRIS_DATA_PATH, 'pga.db')
