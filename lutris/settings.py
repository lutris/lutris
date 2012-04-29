"""Settings module"""
from os.path import join
from xdg import BaseDirectory

CONFIG_DIR = join(BaseDirectory.xdg_config_home, 'lutris')
DATA_DIR = join(BaseDirectory.xdg_data_home, 'lutris')
CACHE_DIR = join(BaseDirectory.xdg_cache_home, 'lutris')

PGA_DB = join(DATA_DIR, 'pga.db')
