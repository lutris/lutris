"""Utility module for creating an application wide logger."""
import logging
import logging.handlers
import xdg.BaseDirectory

from os import makedirs
from os.path import join, isdir, realpath

CACHE_DIR = realpath(join(xdg.BaseDirectory.xdg_cache_home, "lutris"))
if not isdir(CACHE_DIR):
    makedirs(CACHE_DIR)

LOG_FILENAME = join(CACHE_DIR, "lutris.log")
loghandler = logging.handlers.RotatingFileHandler(LOG_FILENAME,
                                                  maxBytes=20971520,
                                                  backupCount=5)
logger = logging.getLogger(__name__)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logformatter = logging.Formatter(log_format)
loghandler.setFormatter(logformatter)
logger.setLevel(logging.INFO)
logger.addHandler(loghandler)
