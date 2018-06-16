"""Utility module for creating an application wide logger."""
import os
import logging
import logging.handlers
from gi.repository import GLib


CACHE_DIR = os.path.realpath(
    os.path.join(GLib.get_user_cache_dir(), "lutris")
)
if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

LOG_FILENAME = os.path.join(CACHE_DIR, "lutris.log")
loghandler = logging.handlers.RotatingFileHandler(LOG_FILENAME,
                                                  maxBytes=20971520,
                                                  backupCount=5)
# Format
log_format = '[%(levelname)s:%(asctime)s:%(module)s]: %(message)s'
logformatter = logging.Formatter(log_format)
loghandler.setFormatter(logformatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(loghandler)

# Set the logging level to show debug messages.
console = logging.StreamHandler()
fmt = '%(levelname)-8s %(asctime)s [%(module)s.%(funcName)s]:%(message)s'
formatter = logging.Formatter(fmt)
console.setFormatter(formatter)
logger.addHandler(console)
logger.setLevel(logging.INFO)
